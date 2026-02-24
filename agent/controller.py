"""执行模块：执行 LLM 决策的动作"""

import asyncio
from typing import List
from playwright.async_api import Page
from .models import ElementSnapshot, PlannerOutput


class Controller:
    """执行模块：执行 LLM 决策的动作"""
    
    def __init__(self, page: Page):
        self.page = page
    
    async def execute(self, decision: PlannerOutput, snapshots: List[ElementSnapshot]) -> bool:
        """
        执行决策，返回是否成功。
        """
        action = decision.action
        element_id = decision.element_id
        value = decision.value
        
        if action == "done":
            print("✓ 任务完成")
            return True
        
        if action == "click" and element_id is not None:
            return await self._click(element_id, snapshots)
        elif action == "fill" and element_id is not None:
            return await self._fill(element_id, value, snapshots)
        elif action == "press":
            return await self._press(value)
        elif action == "scroll":
            return await self._scroll(value)
        elif action == "wait":
            return await self._wait(value)
        elif action == "back":
            return await self._back()
        else:
            print(f"❌ 未知 action: {action}")
            return False
    
    async def _click(self, element_id: int, snapshots: List[ElementSnapshot]) -> bool:
        """点击元素"""
        try:
            snap = next((s for s in snapshots if s.id == element_id), None)
            if not snap:
                print(f"❌ 找不到元素 ID {element_id}")
                return False
            
            locator = self.page.locator(f"[data-agent-id=\"{element_id}\"]")
            
            # 检查可见性和启用状态
            if not await locator.is_visible():
                print(f"❌ 元素 {element_id} 不可见")
                return False
            
            if not await locator.is_enabled():
                print(f"❌ 元素 {element_id} 被禁用")
                return False
            
            await locator.click()
            print(f"✓ 点击 [{element_id}] {snap.label}")
            await asyncio.sleep(1.5)
            return True
        
        except Exception as e:
            print(f"❌ 点击失败: {e}")
            return False
    
    async def _fill(self, element_id: int, value: str, snapshots: List[ElementSnapshot]) -> bool:
        """填充输入框"""
        try:
            snap = next((s for s in snapshots if s.id == element_id), None)
            if not snap:
                print(f"❌ 找不到元素 ID {element_id}")
                return False
            
            locator = self.page.locator(f"[data-agent-id=\"{element_id}\"]")
            
            if not await locator.is_visible():
                print(f"❌ 元素 {element_id} 不可见")
                return False
            
            await locator.fill(value or "")
            print(f"✓ 填充 [{element_id}] {snap.label} = '{value}'")
            await asyncio.sleep(1)
            return True
        
        except Exception as e:
            print(f"❌ 填充失败: {e}")
            return False
    
    async def _press(self, key: str) -> bool:
        """按键"""
        try:
            await self.page.keyboard.press(key)
            print(f"✓ 按键 {key}")
            await asyncio.sleep(1)
            return True
        except Exception as e:
            print(f"❌ 按键失败: {e}")
            return False
    
    async def _scroll(self, direction: str) -> bool:
        """滚动"""
        try:
            if direction == "down":
                await self.page.keyboard.press("PageDown")
            elif direction == "up":
                await self.page.keyboard.press("PageUp")
            else:
                await self.page.evaluate(f"window.scrollBy(0, {direction})")
            print(f"✓ 滚动 {direction}")
            await asyncio.sleep(1)
            return True
        except Exception as e:
            print(f"❌ 滚动失败: {e}")
            return False
    
    async def _wait(self, duration: str) -> bool:
        """等待"""
        try:
            wait_ms = int(duration) if duration else 2000
            await asyncio.sleep(wait_ms / 1000)
            print(f"✓ 等待 {wait_ms}ms")
            return True
        except Exception as e:
            print(f"❌ 等待失败: {e}")
            return False
    
    async def _back(self) -> bool:
        """返回"""
        try:
            await self.page.go_back()
            print(f"✓ 返回")
            await asyncio.sleep(2)
            return True
        except Exception as e:
            print(f"❌ 返回失败: {e}")
            return False
