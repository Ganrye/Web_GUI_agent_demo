import asyncio
import json
import os
from typing import Dict

from dotenv import load_dotenv
from openai import AsyncOpenAI
from playwright.async_api import async_playwright

# 加载 .env 文件中的环境变量
load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY")
                         ,base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
                         )
model = "qwen-plus"

# 全局自增 ID 计数器，确保跨轮次唯一
NEXT_ELEMENT_ID = 0


async def get_interactive_elements(page) -> str:
    """
    感知模块：提取可见且可交互的元素，并写入 data-agent-id 属性。
    仅返回文本字符串，同时更新页面中的元素 ID。
    """
    global NEXT_ELEMENT_ID

    js_code = """
    (startId) => {
        const isVisible = (el) => {
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            if (style.display === 'none') return false;
            if (style.visibility === 'hidden') return false;
            if (parseFloat(style.opacity) === 0) return false;
            if (rect.width <= 0 || rect.height <= 0) return false;
            return true;
        };

        const isInteractive = (el) => {
            if (el.tagName === 'INPUT') {
                const type = (el.getAttribute('type') || '').toLowerCase();
                if (type === 'hidden') return false;
            }
            if (el.tagName === 'A') {
                return el.hasAttribute('href') || el.getAttribute('role') === 'button';
            }
            return true;
        };

        const elements = [];
        let currentId = startId;
        const nodes = document.querySelectorAll('button, a, input,textarea');
        for (const el of nodes) {
            if (!isVisible(el)) continue;
            if (!isInteractive(el)) continue;

            currentId += 1;
            el.setAttribute('data-agent-id', String(currentId));

            const tag = el.tagName.toLowerCase();
            const text = (el.innerText || '').trim();
            const value = (el.value || '').trim();
            const placeholder = (el.getAttribute('placeholder') || '').trim();
            const ariaLabel = (el.getAttribute('aria-label') || '').trim();

            const label = text || value || placeholder || ariaLabel || '(无文本)';
            elements.push({ id: currentId, tag, label });
        }

        return { elements, nextId: currentId };
    }
    """

    result = await page.evaluate(js_code, NEXT_ELEMENT_ID)
    NEXT_ELEMENT_ID = result["nextId"]

    lines = []
    for item in result["elements"]:
        lines.append(f"[{item['id']}] {item['tag']}: \"{item['label']}\"")

    return "\n".join(lines)


async def ask_llm(instruction: str, dom_context: str) -> str:
    """
    大脑模块：调用 OpenAI 接口，严格要求 JSON 输出。
    """
    system_prompt = (
        "你是一个 Web UI 自动化智能体。\n"
        "你将根据用户指令和 DOM 交互元素列表做出下一步操作。\n"
        "【极其重要的规则】：如果你通过观察当前页面的元素，发现用户的目标已经达成（例如：用户要求搜索天气，而页面上已经出现了天气预报相关的元素或链接；或者你发现刚才已经执行过提交动作，没必要重复执行），你必须果断停止，将 action 设置为 'done'！\n"
        "你必须且只能输出 JSON 字符串，格式固定如下：\n"
        "{\n"
        "  \"thought\": \"分析当前页面状态，判断任务是否已完成。如果未完成，说明下一步为什么这么做\",\n"
        "  \"action\": \"click 或 fill 或 done\",\n"
        "  \"element_id\": 1,\n"
        "  \"value\": \"要输入的内容\"\n"
        "}\n"
        "如果 action 是 done，则 element_id 和 value 必须为 null。"
    )

    user_prompt = (
        f"用户指令：{instruction}\n\n"
        f"当前可交互元素：\n{dom_context}\n\n"
        "请给出下一步操作。"
    )

    response = await client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    return response.choices[0].message.content


async def run_agent(instruction: str, start_url: str) -> None:
    """
    主循环：感知 -> 决策 -> 执行。
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(start_url)
        await asyncio.sleep(3)  # 等待页面加载
        while True:
            dom_context = await get_interactive_elements(page)
            llm_output = await ask_llm(instruction, dom_context)

            try:
                decision = json.loads(llm_output)
            except json.JSONDecodeError:
                print("JSON 解析失败，模型返回：", llm_output)
                await asyncio.sleep(2)

                continue

            thought = decision.get("thought", "")
            action = decision.get("action", "")
            element_id = decision.get("element_id")
            value = decision.get("value")

            print("思考：", thought)
            try:
                if action == "click" and element_id is not None:
                    locator = page.locator(f"[data-agent-id=\"{element_id}\"]")
                    await locator.click()
                elif action == "fill" and element_id is not None:
                    locator = page.locator(f"[data-agent-id=\"{element_id}\"]")
                    await locator.fill(value or "")
                elif action == "done":
                    print("任务完成")
                    break
                else:
                    print("未知或无效的 action：", llm_output)
            except Exception as e:
                print(f"执行动作失败，大模型可能猜错了ID。准备重试... 错误: {e}")

            await asyncio.sleep(2)

        await browser.close()


if __name__ == "__main__":
    # 示例用法：修改为你的指令与目标网址
    user_instruction = "在页面上搜索今天天气怎么样并提交"
    start_url = "https://www.baidu.com"

    asyncio.run(run_agent(user_instruction, start_url))
