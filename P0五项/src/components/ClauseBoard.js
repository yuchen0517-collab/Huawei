import { escapeHTML } from './ui.js';
import { CLAUSE_STATUS } from '../domain/clauses.js';

const STANCES = [
  { value: 'hold', label: '维持现立场' },
  { value: 'accept', label: '接受对方版本' },
  { value: 'modify', label: '提出修改' },
  { value: 'reject', label: '拒绝该条' }
];

/**
 * 对方给出的数值按 kind 分别渲染：比例给百分比（带进度条），
 * 周期/数量给准确数字 + 单位，未表态就是暂无数据。
 * 条款里本来就混着两类量，不能统一套成百分比。
 */
function valueHTML(value) {
  if (!value || value.kind === 'none') return '<span class="cb-val none">暂无数据</span>';
  if (value.kind === 'percent') {
    return `<span class="cb-val"><i class="cb-val-bar" aria-hidden="true"><u style="width:${value.num}%"></u></i>${value.num}%</span>`;
  }
  return `<span class="cb-val">${value.num}${value.unit ? escapeHTML(value.unit) : ''}</span>`;
}

/**
 * 协议签署板：报价板弹窗内使用。只负责画，草稿、计数、提交中状态全部由 props 传入。
 */
export function ClauseBoard({ clauses = [], drafts = {}, draftCount = 0, pendingCount = 0, submitting = false }) {
  const rows = clauses.map((clause, index) => {
    const selected = drafts[clause.id] || 'hold';
    return `<div class="cb-row">
      <span class="cb-no">${String(index + 1).padStart(2, '0')}</span>
      <div class="cb-clause"><strong>${escapeHTML(clause.name)}</strong><small>第 ${clause.changedRound} 轮更新</small></div>
      <select class="cb-select" data-action="stance-change" data-clause-id="${escapeHTML(clause.id)}" aria-label="${escapeHTML(clause.name)}我方立场">${STANCES.map(item => `<option value="${item.value}"${item.value === selected ? ' selected' : ''}>${item.label}</option>`).join('')}</select>
      <div class="cb-opponent"><span>${escapeHTML(clause.theirStance)}</span>${valueHTML(clause.theirValue)}</div>
      <span class="quote-status ${clause.status}">${CLAUSE_STATUS[clause.status] || clause.status}</span>
    </div>`;
  }).join('');

  return `<div class="clause-board">
    <div class="cb-head"><span>条款</span><span>我方立场</span><span>对方立场</span><span>状态</span></div>
    <div class="cb-list">${rows}</div>
    <div class="cb-foot"><span class="cb-foot-stat">已修订 ${draftCount} 条 · 未决 ${pendingCount} 条</span>${submitting ? '<small>提交中…</small>' : ''}</div>
  </div>`;
}
