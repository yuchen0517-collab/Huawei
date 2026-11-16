import { escapeHTML, icon, PanelHeading } from './ui.js';

export function StrategyCard({ strategy, selected = false }) {
  return `<button class="strategy-card${strategy.recommended ? ' recommended' : ''}${selected ? ' selected' : ''}" data-action="toggle-strategy" data-strategy-id="${escapeHTML(strategy.id)}" aria-pressed="${selected}">
    <span class="card-cost">${strategy.cost}</span><span class="card-content"><small>${escapeHTML(strategy.type)}</small><strong>${escapeHTML(strategy.name)}</strong><p>${escapeHTML(strategy.description)}</p><span class="card-effect">${escapeHTML(strategy.effect)}</span></span>${strategy.recommended ? '<em>顾问建议</em>' : ''}<span class="select-mark">${icon('check')}</span>
  </button>`;
}

export function StrategyCards({ strategies, selectedIds = [] }) {
  return strategies.map(strategy => StrategyCard({ strategy, selected: selectedIds.includes(strategy.id) })).join('');
}

export function HandFooterContent({ used, total, canEndTurn }) {
  const diamonds = Array.from({ length: total }, (_, index) => `<i${index < used ? ' class="filled"' : ''}></i>`).join('');
  return `<div class="action-points"><span>行动点</span><div class="point-diamonds" aria-hidden="true">${diamonds}</div><strong>${used} / ${total}</strong></div>
    <button class="end-turn" data-action="end-turn"${canEndTurn ? '' : ' disabled'}>结束本轮${icon('chevron')}</button>`;
}

export function StrategyPanel({ strategies, selectedIds, used, total, canEndTurn }) {
  return `<aside class="side-panel strategy-panel" id="strategyPanel" aria-label="策略卡区">
    ${PanelHeading({ kicker: 'STRATEGY HAND', title: '策略卡区', collapseAction: 'collapse-strategy', collapseLabel: '收起策略卡区' })}
    <div class="strategy-cards" id="strategyCards">${StrategyCards({ strategies, selectedIds })}</div>
    <div class="hand-footer" id="handFooter">${HandFooterContent({ used, total, canEndTurn })}</div>
  </aside><button class="reopen-rail reopen-left" data-action="reopen-strategy" aria-label="展开策略卡区">${icon('chevron')}<span>策略</span></button>`;
}
