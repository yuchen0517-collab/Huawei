import { Avatar, escapeHTML, icon } from './ui.js';
import { parties } from '../domain/negotiation.js';

export function Speech({ party = 'us', label, text = '', html = null, badge = '', advisor = '' }) {
  const delegation = parties[party];
  const self = Boolean(delegation.self);
  return `<article class="speech${self ? ' self-speech' : ''}">
    ${Avatar({ party: delegation })}<div class="speech-body"><div class="speech-meta"><strong>${escapeHTML(delegation.name)}</strong><span>${escapeHTML(label)}</span>${badge ? `<em>${escapeHTML(badge)}</em>` : ''}</div><p>${html ?? escapeHTML(text)}</p>${advisor ? `<div class="advisor-reading"><span>顾问研判</span>${escapeHTML(advisor)}</div>` : ''}</div>
  </article>`;
}

export function DialogueMessages({ speeches }) {
  return `<div class="opening-notice"><span>NEGOTIATION COMMENCED</span><strong>谈判开始 · 请陈述我方立场</strong><small>每一张牌都是一次信号，每一次让步都应换来对价。</small></div>${speeches.map(speech => Speech(speech)).join('')}`;
}

export function DialogueStage({ speeches }) {
  return `<section class="main-stage" aria-label="谈判会场">
    <div class="stage-heading"><div><span>PUBLIC NEGOTIATION</span><strong>公开会场</strong></div><span class="stage-status"><i></i>对方在线</span></div>
    <div class="dialogue-scroll" id="dialogueScroll" aria-live="polite">${DialogueMessages({ speeches })}</div>
    <button class="report-fab" data-action="show-report" aria-label="打开谈判战报" title="谈判战报"><span class="report-image"><img src="/report-logo.png" alt=""></span><span>战报</span></button>
  </section>`;
}
