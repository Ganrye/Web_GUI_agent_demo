# Web GUI Agent 项目结构说明

## 新的目录结构

```
Web_GUI_agent_demo/
├── web_ui_agent.py          # 主入口文件（包含配置和 main 函数）
├── agent/                   # Agent 核心包
│   ├── __init__.py         # 包初始化，导出所有公共类
│   ├── models.py           # 数据模型定义
│   ├── perception.py       # 感知模块 - 页面元素提取
│   ├── planner.py          # 规划模块 - LLM 决策
│   ├── controller.py       # 执行模块 - 动作执行
│   ├── memory.py           # 记忆模块 - 历史追踪
│   └── core.py             # 核心 Agent 类
├── .env                    # 环境配置（API Key 等）
├── .gitignore
├── README.md
└── tempCodeRunnerFile.py
```

## 各模块详解

### 1. **models.py** - 数据模型
定义三个核心数据类：
- `ElementSnapshot`: 页面元素快照（ID、标签、标签文本、坐标等）
- `PlannerOutput`: LLM 规划输出（思考、计划、动作、元素ID、值）
- `MemoryRecord`: 单步历史记录（步数、动作、结果）

### 2. **perception.py** - 感知模块
负责页面交互元素的提取与分析：
- `Perception` 类：通过 JavaScript 注入提取可见的交互元素
- 功能：获取元素属性、角色、禁用状态、位置信息、上下文等
- 输出：元素快照列表 + 供 LLM 分析的 DOM 摘要

### 3. **planner.py** - 规划模块
基于页面状态和用户指令做出决策：
- `Planner` 类：调用 LLM（阿里巴巴 Qwen）获取下一步行动
- 系统提示词包含规则：任务完成判断、避免重复操作等
- 输出：结构化的 JSON 决策（PlannerOutput）

### 4. **controller.py** - 执行模块
执行 LLM 决策的各种动作：
- `Controller` 类：处理点击、填充、按键、滚动、等待、返回等操作
- 包含元素可见性和启用状态检查
- 支持的操作：
  - `click`: 点击元素
  - `fill`: 填充输入框
  - `press`: 按键（Enter、Escape 等）
  - `scroll`: 页面滚动
  - `wait`: 等待延迟
  - `back`: 浏览器返回

### 5. **memory.py** - 记忆模块
追踪执行历史，防止死循环：
- `Memory` 类：维护历史记录、访问过的 URL、失败的元素等
- 功能：
  - 记录每一步的动作和结果
  - 检测重复操作（死循环检测）
  - 格式化历史供规划模块参考

### 6. **core.py** - 核心 Agent 类
整合所有模块的主控制器：
- `WebUIAgent` 类：编排整个自动化流程
- 主循环流程：
  1. **感知** - 提取当前页面元素
  2. **规划** - 调用 LLM 决策下一步
  3. **执行** - 执行 LLM 决策的动作
  4. **记忆** - 记录步骤和结果
  5. **判断** - 检查是否完成或死循环

### 7. **web_ui_agent.py** - 主入口
简洁的入口点：
- 加载环境变量（OPENAI_API_KEY）
- 初始化 OpenAI 客户端
- 定义用户指令和目标 URL
- 创建 Agent 实例并运行

## 使用方式

### 基础用法

```python
from agent import WebUIAgent
from openai import AsyncOpenAI
import asyncio

# 初始化客户端
client = AsyncOpenAI(api_key="your_key")

# 创建 Agent
agent = WebUIAgent(client, "qwen-max")

# 运行任务
asyncio.run(agent.run(
    instruction="搜索并提交天气查询",
    start_url="https://www.baidu.com",
    max_steps=20
))
```

### 灵活扩展

因为模块间解耦，你可以：

1. **自定义感知策略**
   ```python
   from agent import Perception
   class CustomPerception(Perception):
       async def extract_elements(self, page):
           # 自定义逻辑
   ```

2. **修改规划提示词**
   - 编辑 `planner.py` 的系统提示词

3. **添加新的执行动作**
   - 在 `controller.py` 的 `execute` 方法中添加新的 action 分支

## 优势

✅ **代码清晰** - 单一职责原则，每个模块专注一个功能  
✅ **易于维护** - 修改某个功能只需编辑对应模块  
✅ **易于扩展** - 添加新功能不影响现有代码  
✅ **便于测试** - 各模块可独立测试  
✅ **便于复用** - 可轻松导入特定模块到其他项目  

---

## 快速开始

1. 安装依赖
   ```bash
   pip install python-dotenv openai playwright
   ```

2. 配置 .env
   ```
   OPENAI_API_KEY=your_key
   ```

3. 运行
   ```bash
   python web_ui_agent.py
   ```
