"""数据模型定义"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class ElementSnapshot:
    """单个可交互元素的快照"""
    id: int
    tag: str
    role: Optional[str]
    label: str
    name: Optional[str]
    input_type: Optional[str]
    disabled: bool
    bbox: Optional[Dict]  # {x, y, width, height}
    context: Optional[str]  # 上下文（如最近的 form legend 或父级文本）


@dataclass
class PlannerOutput:
    """Planner 输出的结构化决策"""
    thought: str
    plan: List[str]  # 多步计划
    action: str  # click|fill|press|scroll|wait|back|done
    element_id: Optional[int]
    value: Optional[str]


@dataclass
class MemoryRecord:
    """单条历史记录"""
    step_num: int
    action: str
    element_id: Optional[int]
    element_label: Optional[str]
    result: str  # success|failed
