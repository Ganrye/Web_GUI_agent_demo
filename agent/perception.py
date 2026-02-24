"""感知模块：提取页面中的可交互元素"""

from typing import List, Tuple
from playwright.async_api import Page
from .models import ElementSnapshot


class Perception:
    """
    感知模块：提取可见且可交互的元素，增强语义信息。
    对标 browser-use 的 DOM 提取能力。
    """
    
    def __init__(self):
        self.last_element_id = 0
    
    async def extract_elements(self, page: Page) -> Tuple[List[ElementSnapshot], str]:
        """
        从页面提取可交互元素，返回元素列表 + 文本摘要。
        
        增强点：
        - 更丰富的 label（aria/title/alt 聚合）
        - role 信息
        - disabled 状态
        - bbox（几何）
        - 上下文（最近 form、fieldset、父文本）
        """
        js_code = """
        (startId) => {
            const isVisible = (el) => {
                if (!el) return false;
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
                    const href = el.getAttribute('href');
                    const role = el.getAttribute('role');
                    return href || role === 'button';
                }
                return true;
            };

            // 聚合 label 的逻辑
            const getLabel = (el) => {
                const candidates = [
                    (el.innerText || '').trim(),
                    (el.value || '').trim(),
                    el.getAttribute('placeholder') || '',
                    el.getAttribute('aria-label') || '',
                    el.getAttribute('title') || '',
                    el.getAttribute('alt') || '',
                    el.getAttribute('name') || '',
                ];
                const chosen = candidates.find(c => c.length > 0);
                return chosen || '(无文本)';
            };

            // 获取上下文（最近的 form/fieldset 以及父元素文本）
            const getContext = (el) => {
                let form = el.closest('form');
                let fieldset = el.closest('fieldset');
                let legend = fieldset?.querySelector('legend');
                let parentText = (el.parentElement?.innerText || '').trim().split('\\n')[0];
                
                let parts = [];
                if (legend) parts.push('legend: ' + legend.innerText.trim());
                if (form?.id) parts.push('form: ' + form.id);
                if (parentText && parentText !== getLabel(el)) parts.push('parent: ' + parentText.slice(0, 30));
                
                return parts.length > 0 ? parts.join(' | ') : null;
            };

            const elements = [];
            let currentId = startId;
            const nodes = document.querySelectorAll('button, a, input, textarea, select');
            
            for (const el of nodes) {
                if (!isVisible(el)) continue;
                if (!isInteractive(el)) continue;

                currentId += 1;
                el.setAttribute('data-agent-id', String(currentId));

                const tag = el.tagName.toLowerCase();
                const role = el.getAttribute('role');
                const label = getLabel(el);
                const name = el.getAttribute('name') || el.id || null;
                const inputType = el.getAttribute('type') || null;
                const disabled = el.disabled || el.getAttribute('aria-disabled') === 'true';
                const bbox = el.getBoundingClientRect();
                const context = getContext(el);

                elements.push({
                    id: currentId,
                    tag,
                    role,
                    label,
                    name,
                    input_type: inputType,
                    disabled,
                    bbox: { x: bbox.x, y: bbox.y, width: bbox.width, height: bbox.height },
                    context
                });
            }

            return { elements, lastId: currentId };
        }
        """
        
        result = await page.evaluate(js_code, self.last_element_id)
        self.last_element_id = result["lastId"]
        
        # 转换为 ElementSnapshot 对象
        snapshots = [
            ElementSnapshot(
                id=item["id"],
                tag=item["tag"],
                role=item["role"],
                label=item["label"],
                name=item["name"],
                input_type=item["input_type"],
                disabled=item["disabled"],
                bbox=item["bbox"],
                context=item["context"]
            )
            for item in result["elements"]
        ]
        
        # 生成文本摘要（用于 LLM）
        summary = self._generate_summary(snapshots)
        
        return snapshots, summary
    
    def _generate_summary(self, snapshots: List[ElementSnapshot]) -> str:
        """生成 DOM 文本摘要，给 LLM 看"""
        lines = []
        for snap in snapshots:
            context_str = f" ({snap.context})" if snap.context else ""
            disabled_str = " [DISABLED]" if snap.disabled else ""
            lines.append(f"[{snap.id}] {snap.tag}: \"{snap.label}\"{disabled_str}{context_str}")
        return "\n".join(lines)
