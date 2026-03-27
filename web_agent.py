"""
Web UI Agent - 基于 Playwright + OpenAI 的极简网页自动化智能体

架构说明（三大核心模块）：
  1. 感知模块 (Perception)  - get_interactive_elements(page)
     通过 JS 注入提取页面上可见且可交互的元素，过滤掉无关噪声。
  2. 大脑模块 (Decision)    - ask_llm(instruction, dom_context)
     调用 OpenAI 大模型，根据当前任务指令和 DOM 上下文决定下一步动作。
  3. 执行与主循环 (Execution & Loop) - run_agent(instruction, start_url)
     驱动 Playwright 浏览器，循环执行"感知 → 决策 → 执行"，直到任务完成。

依赖安装：
    pip install playwright openai
    playwright install chromium

运行示例：
    python web_agent.py
"""

import asyncio
import json
import os

from openai import AsyncOpenAI
from playwright.async_api import async_playwright

# ──────────────────────────────────────────────
# 全局配置
# ──────────────────────────────────────────────

# OpenAI API Key：从环境变量读取，未设置时抛出异常以避免静默失败
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("请设置环境变量 OPENAI_API_KEY，例如：export OPENAI_API_KEY='sk-...'")


# 使用的模型名称
MODEL_NAME = os.environ.get("OPENAI_MODEL", "gpt-4o")

# 每次操作后等待页面加载的秒数
ACTION_DELAY_SECONDS = 2

# 防止无限循环的最大步骤数
MAX_STEPS = 20


# ══════════════════════════════════════════════
# 模块一：感知模块 (Perception)
# ══════════════════════════════════════════════

async def get_interactive_elements(page) -> str:
    """
    从当前页面中提取可见且可交互的元素，返回供 LLM 阅读的文本描述。

    优化策略（DOM 降噪过滤）：
      - 仅关注 <button>、<a>、<input> 三种标签，忽略装饰性 HTML。
      - 通过检测元素的 offsetParent、offsetWidth、offsetHeight 以及
        getComputedStyle().visibility / display 来过滤不可见元素。
      - 为每个可见可交互元素分配全局自增 ID，方便 LLM 通过 ID 引用。

    参数：
        page: Playwright 的 Page 对象

    返回：
        str: 格式化的元素列表文本，示例：
             [1] button: "登录"
             [2] input: "请输入用户名"
    """

    # 通过 page.evaluate() 在浏览器内执行 JavaScript，避免大量 HTML 传输
    elements = await page.evaluate("""
        () => {
            const results = [];
            let globalId = 1;  // 全局自增 ID 计数器

            // 只抓取三类可交互标签
            const selectors = ['button', 'a', 'input'];

            selectors.forEach(tag => {
                const nodes = document.querySelectorAll(tag);

                nodes.forEach(el => {
                    // ── 可见性检测 ──────────────────────────────────
                    // 1. offsetParent 为 null 表示元素被隐藏（display:none 的父级）
                    //    注意：position:fixed 的元素 offsetParent 也是 null，
                    //    所以额外检查 offsetWidth / offsetHeight
                    if (el.offsetParent === null && el.offsetWidth === 0 && el.offsetHeight === 0) {
                        return;  // 跳过不可见元素
                    }

                    // 2. 通过计算样式进一步过滤
                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                        return;  // 跳过样式隐藏的元素
                    }

                    // ── 提取元素描述文本 ────────────────────────────
                    // 优先级：innerText > placeholder > value > type > href 片段
                    let label = (el.innerText || el.placeholder || el.value || el.type || '').trim();

                    // 对 <a> 标签，若无文字则尝试截取 href
                    if (tag === 'a' && !label && el.href) {
                        label = el.href.substring(0, 50);
                    }

                    // 去掉过长文字，防止 prompt 过大
                    if (label.length > 80) {
                        label = label.substring(0, 77) + '...';
                    }

                    results.push({
                        id: globalId++,
                        tag: tag,
                        label: label
                    });
                });
            });

            return results;
        }
    """)

    if not elements:
        return "（页面上未检测到可交互元素）"

    # 将 JS 返回的对象列表格式化为易读文本
    lines = []
    for elem in elements:
        tag = elem["tag"]
        label = elem["label"] or "(无文字)"
        lines.append(f'[{elem["id"]}] {tag}: "{label}"')

    return "\n".join(lines)


# ══════════════════════════════════════════════
# 模块二：大脑模块 (Decision)
# ══════════════════════════════════════════════

# 构造 OpenAI 异步客户端（全局复用，避免重复创建）
_openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# System Prompt 模板：告诉 LLM 它的角色与输出格式规范
SYSTEM_PROMPT = """你是一个网页自动化操作助手。
你的任务是根据用户给定的操作指令以及当前页面上可交互元素的列表，决定下一步应该执行什么操作。

你必须且只能返回如下严格格式的 JSON 字符串，不要包含任何额外解释或 markdown 代码块：
{
  "thought": "用一句话解释你为什么这么做",
  "action": "click 或 fill 或 done",
  "element_id": 1,
  "value": null
}

字段说明：
- thought: 简要说明本步骤的理由（中文）。
- action: 必须是以下三个值之一：
    "click"  —— 点击指定元素
    "fill"   —— 在指定元素中输入文字
    "done"   —— 任务已完成，退出循环
- element_id: 要操作的元素 ID（整数）；若 action 为 "done" 则填 null。
- value: 仅当 action 为 "fill" 时填写要输入的文字；其他情况填 null。
"""


async def ask_llm(instruction: str, dom_context: str) -> dict:
    """
    调用 OpenAI 大模型，根据任务指令和当前页面元素列表决定下一步动作。

    参数：
        instruction  (str): 用户的自然语言任务指令，例如"在搜索框输入 Python 并点击搜索"
        dom_context  (str): 感知模块返回的可交互元素文本描述

    返回：
        dict: 包含 thought / action / element_id / value 四个字段的字典
              若解析失败则返回默认的 done 动作以安全退出
    """

    # 构造用户消息，将指令和当前 DOM 状态拼接在一起
    user_message = f"""当前任务指令：{instruction}

当前页面可交互元素列表：
{dom_context}

请根据以上信息，决定下一步操作。"""

    print("\n[LLM] 正在调用大模型决策...")

    try:
        response = await _openai_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ],
            temperature=0.0,      # 设为 0 使输出尽量稳定、可预测
            response_format={"type": "json_object"},  # 强制 JSON 输出（需 gpt-4o / gpt-4-turbo 等支持该参数的模型）
        )

        raw_text = response.choices[0].message.content.strip()
        print(f"[LLM] 原始响应：{raw_text}")

        # 解析 JSON
        decision = json.loads(raw_text)
        return decision

    except json.JSONDecodeError as e:
        # JSON 格式错误：打印警告并安全退出
        print(f"[警告] JSON 解析失败：{e}，将终止任务。")
        return {"thought": "JSON 解析失败，安全退出", "action": "done", "element_id": None, "value": None}

    except Exception as e:
        # 其他异常（网络、API 错误等）
        print(f"[错误] 调用 LLM 时发生异常：{e}，将终止任务。")
        return {"thought": f"发生异常：{e}", "action": "done", "element_id": None, "value": None}


# ══════════════════════════════════════════════
# 模块三：执行与主循环 (Execution & Loop)
# ══════════════════════════════════════════════

async def run_agent(instruction: str, start_url: str) -> None:
    """
    Agent 主函数：启动浏览器并进入"感知 → 决策 → 执行"循环，直到任务完成。

    参数：
        instruction (str): 自然语言任务指令
        start_url   (str): 任务起始网址
    """

    print(f"\n{'='*60}")
    print(f"[Agent] 任务指令：{instruction}")
    print(f"[Agent] 起始地址：{start_url}")
    print(f"{'='*60}\n")

    async with async_playwright() as playwright:
        # ── 启动浏览器 ──────────────────────────────────────────
        # headless=False 可以看到浏览器界面，便于调试；
        # 生产/测试时改为 headless=True 可无头运行
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # 访问起始 URL
        await page.goto(start_url)
        print(f"[Agent] 已打开页面：{start_url}")

        step = 0  # 当前步骤计数

        while True:
            step += 1
            print(f"\n{'─'*40}")
            print(f"[Agent] 第 {step} 步")

            # 防止无限循环
            if step > MAX_STEPS:
                print(f"[Agent] 已达到最大步骤数 {MAX_STEPS}，强制退出。")
                break

            # ── a. 感知：获取精简 DOM ──────────────────────────
            dom_text = await get_interactive_elements(page)
            print(f"[感知] 当前页面可交互元素：\n{dom_text}")

            # ── b. 决策：让 LLM 决定下一步 ────────────────────
            decision = await ask_llm(instruction, dom_text)

            # ── c. 解析并打印思考过程 ──────────────────────────
            thought     = decision.get("thought", "（无说明）")
            action      = decision.get("action", "done")
            element_id  = decision.get("element_id")
            value       = decision.get("value")

            print(f"[思考] {thought}")
            print(f"[动作] action={action}, element_id={element_id}, value={value}")

            # ── d. 执行动作 ────────────────────────────────────
            if action == "done":
                print("\n[Agent] ✅ 任务完成！")
                break

            elif action in ("click", "fill"):
                if element_id is None:
                    print("[警告] element_id 为空，跳过本步骤。")
                    continue

                # 通过注入 JS 定位之前编号的元素，
                # 使用与感知模块相同的遍历逻辑，根据全局 ID 找到对应节点
                target_element = await page.evaluate_handle(
                    """
                    (targetId) => {
                        const selectors = ['button', 'a', 'input'];
                        let globalId = 1;

                        for (const tag of selectors) {
                            const nodes = document.querySelectorAll(tag);
                            for (const el of nodes) {
                                // 与感知模块保持一致的可见性检测
                                if (el.offsetParent === null && el.offsetWidth === 0 && el.offsetHeight === 0) continue;
                                const style = window.getComputedStyle(el);
                                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;

                                if (globalId === targetId) {
                                    return el;  // 找到目标元素，返回给 Python 端
                                }
                                globalId++;
                            }
                        }
                        return null;  // 未找到
                    }
                    """,
                    element_id,
                )

                # 检查是否找到了目标元素
                # as_element() 当 JS 返回 null 时会返回 None，以此判断元素是否存在
                element = target_element.as_element()
                if element is None:
                    print(f"[警告] 未找到 ID 为 {element_id} 的元素，跳过本步骤。")
                    continue

                if action == "click":
                    # 执行点击操作
                    await element.click()
                    print(f"[执行] 已点击元素 [{element_id}]")

                elif action == "fill":
                    # 清空输入框后填入内容
                    await element.fill(value or "")
                    print(f"[执行] 已在元素 [{element_id}] 输入：{value}")

            else:
                print(f"[警告] 未知动作类型：{action}，跳过本步骤。")

            # ── e. 等待页面加载完成 ────────────────────────────
            print(f"[Agent] 等待 {ACTION_DELAY_SECONDS} 秒让页面响应...")
            await asyncio.sleep(ACTION_DELAY_SECONDS)

        # 关闭浏览器（离开 async with 块时自动关闭，此处显式关闭增加可读性）
        await browser.close()
        print("\n[Agent] 浏览器已关闭，Agent 运行结束。")


# ══════════════════════════════════════════════
# 程序入口
# ══════════════════════════════════════════════

if __name__ == "__main__":
    # ── 在此修改你的任务指令和起始 URL ──────────────────────────
    TASK_INSTRUCTION = "在搜索框中输入 'Playwright' 并点击搜索按钮"
    START_URL = "https://cn.bing.com"

    asyncio.run(run_agent(TASK_INSTRUCTION, START_URL))
