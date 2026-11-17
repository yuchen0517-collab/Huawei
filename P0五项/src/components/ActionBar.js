import { escapeHTML } from './ui.js';

/**
 * 只负责画。可用性、reason、used（当前选中或已使用）全部由 store.baseActions 计算。
 */
export function ActionBar({ actions = [] }) {
  const buttons = actions.map(action => {
    const disabled = Boolean(action.disabled);
    const used = Boolean(action.used);
    const primary = Boolean(action.primary);
    const tip = disabled ? action.reason : action.hint;
    return `<button type="button" class="action-bar-btn${used ? ' is-used' : ''}${primary ? ' is-primary' : ''}" data-action="base-action" data-kind="${escapeHTML(action.id)}" aria-pressed="${used}"${disabled ? ' disabled' : ''}${tip ? ` title="${escapeHTML(tip)}" aria-label="${escapeHTML(action.label)}：${escapeHTML(tip)}"` : ` aria-label="${escapeHTML(action.label)}"`}>${escapeHTML(action.label)}</button>`;
  }).join('');
  return `<div class="action-bar" role="toolbar" aria-label="基础行动">${buttons}</div>`;
}