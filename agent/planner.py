"""规划模块：调用 LLM 决策下一步"""

import json
from openai import AsyncOpenAI
from .models import PlannerOutput
from .memory import Memory


class Planner:
    """规划模块：调用 LLM 决策下一步"""
    
    def __init__(self, client: AsyncOpenAI, model: str):
        self.client = client
        self.model = model
    
    async def decide(self, instruction: str, dom_summary: str, memory: Memory) -> PlannerOutput:
        """
        根据指令 + DOM 摘要 + 内存，输出决策。
        """
        system_prompt = (
            "你是一个 Web UI 自动化智能体。\n"
            "你将根据用户指令和 DOM 交互元素列表做出下一步操作。\n"
            "【极其重要的规则】：\n"
            "1. 如果你观察当前页面，发现用户的目标已经达成（出现预期结果、已提交等），立即设置 action='done'。\n"
            "2. 不要重复执行相同操作。参考 Memory 中的历史步骤。\n"
            "你必须且只能输出 JSON 字符串，格式如下：\n"
            "{\n"
            "  \"thought\": \"分析当前页面状态，判断任务进度，说明为什么选择此 action\",\n"
            "  \"plan\": [\"step1_desc\", \"step2_desc\"],\n"
            "  \"action\": \"click|fill|press|scroll|wait|back|done\",\n"
            "  \"element_id\": 1,\n"
            "  \"value\": \"要输入的内容（仅 fill 时需要）\"\n"
            "}\n"
            "如果 action 是 done，element_id 和 value 必须为 null。"
        )
        
        memory_str = memory.format_history()
        user_prompt = (
            f"用户指令：{instruction}\n\n"
            f"当前可交互元素：\n{dom_summary}\n\n"
            f"历史步骤：\n{memory_str}\n\n"
            "请给出下一步操作。"
        )
        
        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        
        output_str = response.choices[0].message.content
        try:
            data = json.loads(output_str)
            return PlannerOutput(
                thought=data.get("thought", ""),
                plan=data.get("plan", []),
                action=data.get("action", "done"),
                element_id=data.get("element_id"),
                value=data.get("value")
            )
        except json.JSONDecodeError as e:
            print(f"JSON 解析失败: {e}, 原始输出: {output_str}")
            raise
