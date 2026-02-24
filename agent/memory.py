"""记忆模块：保存历史步骤和访问记录"""

from typing import List, Optional
from .models import MemoryRecord


class Memory:
    """记忆模块：保存历史步骤和访问记录"""
    
    def __init__(self):
        self.history: List[MemoryRecord] = []
        self.visited_urls: List[str] = []
        self.failed_elements: List[int] = []
        self.step_counter = 0
    
    def record(self, action: str, element_id: Optional[int], element_label: Optional[str], result: str):
        """记录单步操作"""
        self.step_counter += 1
        record = MemoryRecord(
            step_num=self.step_counter,
            action=action,
            element_id=element_id,
            element_label=element_label,
            result=result
        )
        self.history.append(record)
        
        if result == "failed" and element_id is not None:
            self.failed_elements.append(element_id)
    
    def record_url(self, url: str):
        """记录访问过的 URL"""
        if url not in self.visited_urls:
            self.visited_urls.append(url)
    
    def is_repeated_action(self, action: str, element_id: Optional[int], threshold: int = 2) -> bool:
        """判断最近是否重复执行了相同动作"""
        recent = self.history[-threshold:]
        count = sum(1 for r in recent if r.action == action and r.element_id == element_id)
        return count >= threshold
    
    def format_history(self, last_n: int = 5) -> str:
        """格式化内存中的历史记录"""
        if not self.history:
            return "(无历史)"
        
        lines = []
        for rec in self.history[-last_n:]:
            label_str = f" ({rec.element_label})" if rec.element_label else ""
            lines.append(f"Step {rec.step_num}: {rec.action}{label_str} → {rec.result}")
        
        return "\n".join(lines)
