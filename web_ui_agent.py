import asyncio
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI

from agent import WebUIAgent

# 加载 .env 文件中的环境变量
load_dotenv()
client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)
model = "qwen-max"


# ============== 主函数 ==============

if __name__ == "__main__":
    # 示例用法：修改为你的指令与目标网址
    user_instruction = "在页面上搜索今天天气怎么样并提交"
    start_url = "https://www.baidu.com"
    
    # 创建 Agent 实例并运行
    agent = WebUIAgent(client, model)
    asyncio.run(agent.run(user_instruction, start_url, max_steps=20))

