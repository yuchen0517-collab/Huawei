import { escapeHTML, icon, PanelHeading } from './ui.js';
import { CoachPanel } from './CoachPanel.js';

export function StrategyCard({ strategy, selected = false }) {
  return `<button class="strategy-card${strategy.recommended ? ' recommended' : ''}${selected ? ' selected' : ''}" data-action="toggle-strategy" data-strategy-id="${escapeHTML(strategy.id)}" aria-pressed="${selected}">
    <span class="card-cost">${strategy.cost}</span><span class="card-content"><small>${escapeHTML(strategy.type)}</small><strong>${escapeHTML(strategy.name)}</strong><p>${escapeHTML(strategy.description)}</p><span class="card-effect">${escapeHTML(strategy.effect)}</span></span>${strategy.recommended ? '<em>顾问建议</em>' : ''}<span class="select-mark">${icon('check')}</span>
  </button>`;
}

export function StrategyCards({ strategies, selectedIds = [] }) {
  return strategies.map(strategy => StrategyCard({ strategy, selected: selectedIds.includes(strategy.id) })).join('');
}

/**
 * 手牌底部：高度恒定的一行。选卡不改变这里的结构，
 * 否则草稿提示一出现就会把行动点顶上去（旧版的表现）。
 */
export function HandFooterContent({ used, total, canEndTurn, anim = null, phase = 'ready', draftCount = 0 }) {
  const remaining = total - used;
  const from = anim ? anim.from : remaining;
  const exhausted = remaining === 0 && from > 0;
  const loading = phase === 'loading';
  const diamonds = Array.from({ length: total }, (_, index) => {
    if (anim && anim.kind === 'spend' && !exhausted && index >= remaining && index < from) {
      return `<i class="out" style="--pd:${(from - 1 - index) * 55}ms"></i>`;
    }
    if (anim && anim.kind === 'restore' && index >= from && index < remaining) {
      return `<i class="filled in" style="--pd:${(index - from) * 55}ms"></i>`;
    }
    return `<i${index < remaining ? ' class="filled"' : ''}></i>`;
  }).join('');
  return `<div class="action-points"${draftCount > 0 ? ` title="已选 ${draftCount} 张策略卡 · 草稿保留"` : ''}><span>行动点</span><div class="point-diamonds${exhausted ? ' exhausted' : ''}" aria-hidden="true">${diamonds}</div><strong>${remaining} / ${total}</strong></div>
    <button class="end-turn" data-action="end-turn"${canEndTurn || loading ? '' : ' disabled'}${loading ? ' aria-busy="true"' : ''}>${loading ? '提交中…' : '结束本轮'}${loading ? '' : icon('chevron')}</button>`;
}

/**
 * 策略卡区。基础行动条（接受 / 拒绝 / 维持 / 最后报价 / 退出）暂不上屏，
 * 需要时把 ActionBar 放回 #strategyCards 上方即可，其余逻辑不变。
 */
export function StrategyPanel({ strategies, selectedIds, used, total, canEndTurn, version = 1, phase = 'ready', coach = null, coachStatus = 'idle', coachCollapsed = true }) {
  return `<aside class="side-panel strategy-panel" id="strategyPanel" aria-label="策略卡区" tabindex="-1">
    ${PanelHeading({ title: '策略卡区', collapseAction: 'collapse-strategy', collapseLabel: '收起策略卡区' })}
    <div class="strategy-cards" id="strategyCards">${StrategyCards({ strategies, selectedIds })}</div>
    <div class="coach-slot" id="coachSlot">${CoachPanel({ coach, status: coachStatus, collapsed: coachCollapsed, version })}</div>
    <div class="hand-footer" id="handFooter">${HandFooterContent({ used, total, canEndTurn, phase, draftCount: selectedIds.length })}</div>
  </aside><button class="reopen-rail reopen-left" data-action="reopen-strategy" aria-label="展开策略卡区" aria-expanded="false">${icon('chevron')}<span>策略</span></button>`;
}
