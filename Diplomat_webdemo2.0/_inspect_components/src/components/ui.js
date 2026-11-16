export function escapeHTML(value = '') {
  return String(value).replace(/[&<>'"]/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[character]);
}

export function icon(name, className = '') {
  return `<svg${className ? ` class="${escapeHTML(className)}"` : ''} aria-hidden="true"><use href="#i-${escapeHTML(name)}"/></svg>`;
}

export function Avatar({ party, mini = false }) {
  return mini
    ? `<span class="mini-avatar avatar-${party.id}" aria-hidden="true">${escapeHTML(party.code)}</span>`
    : `<div class="avatar avatar-${party.id}" aria-label="${escapeHTML(party.name)}"><span>${escapeHTML(party.code)}</span></div>`;
}

export function PanelHeading({ kicker, title, collapseAction, direction = 'back', collapseLabel }) {
  return `<div class="panel-heading"><div><span>${escapeHTML(kicker)}</span><h2>${escapeHTML(title)}</h2></div><button class="icon-button collapse-button" data-action="${escapeHTML(collapseAction)}" aria-label="${escapeHTML(collapseLabel)}" title="${escapeHTML(collapseLabel)}">${icon(direction)}</button></div>`;
}

export function FoldSection({ title, badge = '', open = false, content }) {
  return `<details class="fold-section"${open ? ' open' : ''}><summary>${escapeHTML(title)}${badge ? `<span>${escapeHTML(badge)}</span>` : ''}</summary>${content}</details>`;
}

export function Metric({ id, label, value, delta, tone = '', previous, negative = false }) {
  return `<div class="metric${tone ? ` ${tone}` : ''}"><div><span>${escapeHTML(label)}</span><strong data-metric-value="${id}">${value}<small${negative ? ' class="negative"' : ''}>${escapeHTML(delta)}</small></strong></div><div class="metric-track"><i data-metric-bar="${id}" style="width:${value}%"></i><b style="left:${previous}%"></b></div></div>`;
}

export function formatRound(round) {
  return String(round).padStart(2, '0');
}
