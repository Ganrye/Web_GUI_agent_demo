# Web GUI Agent Demo

一个基于 **Playwright（异步模式）** 和 **OpenAI** 的极简网页自动化智能体（Web UI Agent）示例。

给定一条自然语言指令，Agent 能自动感知网页、思考并执行点击、输入等操作，直到任务完成。

---

## 架构概览

```
感知 (Perception)  →  大脑 (Decision)  →  执行 (Execution)
   ↑                                            |
   └────────────── 循环直到 done ←──────────────┘
```

| 模块 | 函数 | 说明 |
|------|------|------|
| 感知 | `get_interactive_elements(page)` | 通过 JS 注入提取页面可见可交互元素，过滤 DOM 噪声 |
| 大脑 | `ask_llm(instruction, dom_context)` | 调用 OpenAI 大模型，返回严格 JSON 格式决策 |
| 执行 | `run_agent(instruction, start_url)` | 驱动 Playwright 浏览器，循环执行三步直到完成 |

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 配置 API Key

```bash
export OPENAI_API_KEY="your-api-key-here"
# 可选：指定模型（默认 gpt-4o）
export OPENAI_MODEL="gpt-4o"
```

### 3. 修改任务并运行

打开 `web_agent.py`，在文件末尾修改任务指令和起始 URL：

```python
TASK_INSTRUCTION = "在搜索框中输入 'Playwright' 并点击搜索按钮"
START_URL = "https://cn.bing.com"
```

然后运行：

```bash
python web_agent.py
```

---

## LLM 输出格式

大模型被约束只能返回如下 JSON，不含任何多余文字：

```json
{
  "thought": "用一句话解释你为什么这么做",
  "action": "click 或 fill 或 done",
  "element_id": 1,
  "value": null
}
```

---

## 文件说明

```
web_agent.py       # 核心 Agent 脚本（单文件，含详细中文注释）
requirements.txt   # Python 依赖清单
```
