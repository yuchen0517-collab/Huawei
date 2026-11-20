export function escapeHTML(value = '') {
  return String(value).replace(/[&<>'"]/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[character]);
}

export function icon(name, className = '') {
  return `<svg${className ? ` class="${escapeHTML(className)}"` : ''} aria-hidden="true"><use href="#i-${escapeHTML(name)}"/></svg>`;
}

const FLAGS = {
  cn: '<svg viewBox="0 0 60 60" aria-hidden="true" focusable="false"><rect width="60" height="60" fill="#de2910"/><g fill="#ffde00"><path d="M0-6l1.8 4.1H6L2.7 1 3.8 5 0 2.5-3.8 5-2.7 1-6-1.9h4.2z" transform="translate(15 17) scale(1.35)"/><path d="M0-6l1.8 4.1H6L2.7 1 3.8 5 0 2.5-3.8 5-2.7 1-6-1.9h4.2z" transform="translate(29 8) rotate(22) scale(.43)"/><path d="M0-6l1.8 4.1H6L2.7 1 3.8 5 0 2.5-3.8 5-2.7 1-6-1.9h4.2z" transform="translate(34 17) rotate(42) scale(.43)"/><path d="M0-6l1.8 4.1H6L2.7 1 3.8 5 0 2.5-3.8 5-2.7 1-6-1.9h4.2z" transform="translate(33 27) rotate(58) scale(.43)"/><path d="M0-6l1.8 4.1H6L2.7 1 3.8 5 0 2.5-3.8 5-2.7 1-6-1.9h4.2z" transform="translate(27 35) rotate(28) scale(.43)"/></g></svg>',
  us: '<svg viewBox="0 0 60 60" aria-hidden="true" focusable="false"><rect width="60" height="60" fill="#fff"/><path d="M0 0h60v7H0zm0 14h60v7H0zm0 14h60v7H0zm0 14h60v7H0zm0 14h60v4H0z" fill="#b22234"/><rect width="29" height="32" fill="#3c3b6e"/><g fill="#fff"><circle cx="6" cy="7" r="1.3"/><circle cx="14" cy="7" r="1.3"/><circle cx="22" cy="7" r="1.3"/><circle cx="10" cy="14" r="1.3"/><circle cx="18" cy="14" r="1.3"/><circle cx="6" cy="21" r="1.3"/><circle cx="14" cy="21" r="1.3"/><circle cx="22" cy="21" r="1.3"/><circle cx="10" cy="28" r="1.3"/><circle cx="18" cy="28" r="1.3"/></g></svg>'
};

export function flagSVG(id) {
  return FLAGS[id] || '';
}

export function Avatar({ party, mini = false }) {
  if (mini) {
    return `<span class="mini-avatar avatar-${party.id}" role="img" aria-label="${escapeHTML(party.name)}">${flagSVG(party.id)}</span>`;
  }
  return `<div class="avatar avatar-${party.id}" role="img" aria-label="${escapeHTML(party.name)}">${flagSVG(party.id)}</div>`;
}

export function PanelHeading({ kicker = '', title, collapseAction, direction = 'back', collapseLabel }) {
  const kickerMarkup = kicker ? `<span>${escapeHTML(kicker)}</span>` : '';
  return `<div class="panel-heading"><div>${kickerMarkup}<h2>${escapeHTML(title)}</h2></div><button class="icon-button collapse-button" data-action="${escapeHTML(collapseAction)}" aria-label="${escapeHTML(collapseLabel)}" title="${escapeHTML(collapseLabel)}" aria-expanded="true">${icon(direction)}</button></div>`;
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