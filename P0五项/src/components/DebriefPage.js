import { escapeHTML } from './ui.js';
import { hasLeak } from '../services/coach.js';
import { CLAUSE_STATUS } from '../domain/clauses.js';

const KIND_LABEL = { strategy: '策略', base: '基础行动', revision: '修订', log: '记录' };
const SCORE_DIMS = [
  { key: 'position_clarity', label: '立场清晰' },
  { key: 'diplomatic_tact', label: '外交分寸' },
  { key: 'emotional_control', label: '情绪控制' },
  { key: 'substance_quality', label: '内容质量' }
];

function safeText(text) {
  return hasLeak(text) ? '' : text;
}

function valueText(value) {
  return value == null ? '—' : escapeHTML(String(value));
}

function metricBlock(title, items = []) {
  return `<div class="db-cell"><h5>${escapeHTML(title)}</h5>${items.map(item => `<span class="db-kv"><em>${escapeHTML(item.label)}</em><b>${valueText(item.value)}</b></span>`).join('')}</div>`;
}

function scoreHtml(debrief) {
  if (!debrief.speakerScorePresent) return '<p class="db-empty">终局评价待接入</p>';
  const score = debrief.speakerScore;
  if (!score) return '<p class="db-empty">首轮不计分</p>';
  const rows = SCORE_DIMS.map(dim => {
    const raw = Number(score[dim.key]);
    const value = Number.isFinite(raw) ? Math.max(0, Math.min(100, raw)) : null;
    return `<div class="db-score-row"><span>${dim.label}</span><div class="db-score-track">${value == null ? '' : `<i style="width:${value}%"></i>`}</div><b>${value == null ? '—' : value}</b></div>`;
  }).join('');
  const feedback = safeText(score.feedback);
  return `<div class="db-score">${rows}${feedback ? `<p class="db-empty">${escapeHTML(feedback)}</p>` : ''}</div>`;
}

function coachItemsHtml(coach) {
  const items = (coach && Array.isArray(coach.items) ? coach.items : [])
    .filter(item => !hasLeak(item.title) && !hasLeak(item.text));
  if (!items.length) return '<p class="db-empty">本轮暂无教练建议</p>';
  const group = (title, list) => list.length
    ? `<div class="db-group"><h5>${title}</h5>${list.map(item => `<div class="db-row"><strong>${escapeHTML(item.title)}</strong><span>${escapeHTML(item.text)}</span></div>`).join('')}</div>`
    : '';
  return `${group('阶段建议', items.filter(item => item.kind !== 'alternative'))}${group('替代行动', items.filter(item => item.kind === 'alternative'))}`;
}

export function DebriefPage({ debrief, coach = null }) {
  const verdict = debrief.verdict;
  const hero = verdict
    ? `<section class="debrief-hero status-strip ${escapeHTML(verdict.tone)}"><span class="db-kicker">${escapeHTML(verdict.kicker)}</span><h3>${escapeHTML(verdict.title)}</h3><p>${escapeHTML(verdict.summary)}</p><small>${escapeHTML(verdict.metricsHint || '')}</small></section>`
    : '<section class="debrief-hero status-strip tone-neutral"><h3>尚未终局</h3><p>本局还没有可复盘的终局结论。</p></section>';

  const turning = debrief.turningPoints.length
    ? debrief.turningPoints.map(point => `<div class="db-row"><button type="button" data-action="debrief-jump" data-round="${point.round}">第 ${point.round} 轮 · ${escapeHTML(point.label)}</button><small>${escapeHTML(KIND_LABEL[point.kind] || point.kind)}${point.version == null ? '' : ` · v${escapeHTML(String(point.version))}`}</small></div>`).join('')
    : '<p class="db-empty">暂无关键行动</p>';

  const unresolved = debrief.unresolved.length
    ? debrief.unresolved.map(clause => `<div class="db-row"><span>${escapeHTML(clause.name)}</span><span class="quote-status ${escapeHTML(clause.status)}">${escapeHTML(CLAUSE_STATUS[clause.status] || clause.status)}</span><small>v${escapeHTML(String(clause.changedVersion))}</small></div>`).join('')
    : '<p class="db-empty">全部条款已处理</p>';

  const evidence = debrief.evidence.length
    ? debrief.evidence.map(item => `<div class="db-row"><button type="button" data-action="debrief-jump" data-round="${item.round}">R${item.round} · ${escapeHTML(item.label)}</button><small>${escapeHTML(item.kind)}${item.clause ? ` · ${escapeHTML(item.clause)}` : ''}</small></div>`).join('')
    : '<p class="db-empty">暂无可追溯证据</p>';

  return `<div class="debrief-page" id="debriefPage">
    ${hero}
    <section class="debrief-section"><h4>三维评价</h4><div class="db-grid">${metricBlock('谈判结果', debrief.outcome)}${metricBlock('协议质量', debrief.quality)}${metricBlock('学习表现', debrief.learning)}</div></section>
    <details class="debrief-section"><summary data-action="toggle-debrief-section">教练复盘</summary>${scoreHtml(debrief)}${coachItemsHtml(coach)}</details>
    <details class="debrief-section"><summary data-action="toggle-debrief-section">关键转折</summary><div class="db-list">${turning}</div></details>
    <details class="debrief-section"><summary data-action="toggle-debrief-section">未决条款</summary><div class="db-list">${unresolved}</div></details>
    <details class="debrief-section"><summary data-action="toggle-debrief-section">证据链</summary><div class="db-list">${evidence}</div></details>
    <footer class="debrief-source">${escapeHTML(debrief.dataSource)}</footer>
  </div>`;
}