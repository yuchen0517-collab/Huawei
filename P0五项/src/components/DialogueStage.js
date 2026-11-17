import { Avatar, escapeHTML } from './ui.js';
import { parties } from '../domain/negotiation.js';
import { formatDiff } from '../domain/clauses.js';

export function Speech({ party = 'us', label, text = '', html = null, badge = '', advisor = '', clauseDiff = null, system = false }) {
  if (system) {
    return `<article class="speech system-speech"><div class="speech-body"><div class="speech-meta"><strong>系统提示</strong><span>${escapeHTML(label || '')}</span></div><p>${escapeHTML(text)}</p></div></article>`;
  }
  const delegation = parties[party];
  const self = Boolean(delegation.self);
  const diffText = clauseDiff ? formatDiff(clauseDiff) : '';
  const diffParts = diffText ? diffText.split(' · ') : [];
  const diffShort = diffParts.length > 3
    ? `${diffParts.slice(0, 3).join(' · ')} · +${diffParts.length - 3}`
    : diffText;
  const diffLine = diffText
    ? `<div class="clause-diff" role="note" title="${escapeHTML(diffText)}"><span>本轮条款变化</span><strong>${escapeHTML(diffShort)}</strong></div>`
    : '';
  return `<article class="speech${self ? ' self-speech' : ''}">
    ${Avatar({ party: delegation })}<div class="speech-body"><div class="speech-meta"><strong>${escapeHTML(delegation.name)}</strong><span>${escapeHTML(label)}</span>${badge ? `<em>${escapeHTML(badge)}</em>` : ''}</div>${diffLine}<p>${html ?? escapeHTML(text)}</p>${advisor ? `<div class="advisor-reading"><span>顾问研判</span>${escapeHTML(advisor)}</div>` : ''}</div>
  </article>`;
}

export function DialogueMessages({ speeches }) {
  return `<div class="opening-notice"><strong>谈判开始 · 请陈述我方立场</strong></div>${speeches.map(speech => Speech(speech)).join('')}`;
}

export function ReportFab() {
  return `<button class="report-fab" data-action="show-report" aria-label="打开谈判战报" title="谈判战报">
    <span class="fab-aura" aria-hidden="true"></span>
    <span class="fab-cast" aria-hidden="true"></span>
    <span class="fab-float" aria-hidden="true">
      <span class="fab-orb">
        <span class="fab-sheen"></span>
        <span class="fab-ring"></span>
        <span class="fab-gloss"></span>
        <svg class="fab-glyph" viewBox="0 0 24 24"><path d="M8.2 3.6h6.6l3.4 3.5v13.3H8.2z"/><path d="M14.6 3.6v3.6h3.4"/><path d="M10.7 11.2h4.9"/><path d="M10.7 14.4h4.9"/><path d="M10.7 17.6h3.1"/></svg>
      </span>
    </span>
  </button>`;
}

export function DialogueStage({ speeches, topic }) {
  return `<section class="main-stage" aria-label="谈判会场" tabindex="-1">
    <div class="stage-heading"><div><strong class="stage-topic">${escapeHTML(topic.title)}</strong></div></div>
    <div class="error-slot" id="errorSlot"></div>
    <div class="dialogue-scroll" id="dialogueScroll" aria-live="polite"><div class="status-strip-slot" id="statusStrip"></div>${DialogueMessages({ speeches })}</div>
  </section>`;
}