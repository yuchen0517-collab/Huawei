import { escapeHTML } from './ui.js';

/**
 * 只接收 props。窗口未开时整条不渲染，调用方会把空串写回 slot。
 */
export function StatusStrip({ open = false, remaining = 0, transitionUsed = false }) {
  if (!open) return '';
  const urgent = remaining <= 0;
  const text = urgent ? '最后 1 轮，必须表态' : `剩 ${escapeHTML(String(Math.max(0, remaining)))} 轮`;
  return `<div class="status-strip${urgent ? ' urgent' : ''}" role="status">
    <span class="ss-dot" aria-hidden="true"></span><strong>待表态</strong>
    <span>${text}</span>
    <span class="ss-quota">过渡 ${transitionUsed ? 1 : 0}/1</span>
    <button type="button" class="ss-transition" data-action="use-transition"${transitionUsed ? ' disabled' : ''} title="${transitionUsed ? '本轮已使用过渡' : '把表态延后 1 轮'}">${transitionUsed ? '过渡已用' : '使用过渡'}</button>
  </div>`;
}