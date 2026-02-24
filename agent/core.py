"""Web UI 自动化智能体核心类"""

import asyncio
from typing import Optional
from openai import AsyncOpenAI
from playwright.async_api import async_playwright, Page

from .perception import Perception
from .planner import Planner
from .controller import Controller
from .memory import Memory
from .models import ElementSnapshot


class WebUIAgent:
    """Web UI 自动化智能体"""
    
    def __init__(self, client: AsyncOpenAI, model: str):
        self.client = client
        self.model = model
        self.perception = Perception()
        self.planner = Planner(client, model)
        self.memory = Memory()
        self.controller: Optional[Controller] = None
        self.page: Optional[Page] = None
    
    async def run(self, instruction: str, start_url: str, max_steps: int = 20):
        """
        执行任务的主循环。
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            self.page = await browser.new_page()
            self.controller = Controller(self.page)
            
            await self.page.goto(start_url)
            self.memory.record_url(start_url)
            await asyncio.sleep(2)
            
            for step in range(max_steps):
                print(f"\n{'='*60}")
                print(f"Step {step + 1}/{max_steps}")
                print(f"{'='*60}")
                
                # 1. 感知
                snapshots, dom_summary = await self.perception.extract_elements(self.page)
                print(f"✓ 提取 {len(snapshots)} 个可交互元素")
                
                # 2. 规划
                decision = await self.planner.decide(instruction, dom_summary, self.memory)
                print(f"思考: {decision.thought}")
                print(f"计划: {' → '.join(decision.plan)}")
                print(f"动作: {decision.action} (element_id={decision.element_id})")
                
                # 3. 执行
                success = await self.controller.execute(decision, snapshots)
                self.memory.record(
                    action=decision.action,
                    element_id=decision.element_id,
                    element_label=next((s.label for s in snapshots if s.id == decision.element_id), None),
                    result="success" if success else "failed"
                )
                
                # 4. 判断是否完成
                if decision.action == "done":
                    print(f"\n✓✓✓ 任务完成 ✓✓✓")
                    break
                
                # 5. 检查死循环
                if self.memory.is_repeated_action(decision.action, decision.element_id, threshold=3):
                    print(f"⚠ 检测到重复操作，尝试回退...")
                    await self.controller._back()
                
                # 记录当前 URL
                current_url = self.page.url
                self.memory.record_url(current_url)
                
                await asyncio.sleep(1)
            
            await browser.close()
            print(f"\n✓ Agent 执行完成（共 {self.memory.step_counter} 步）")
