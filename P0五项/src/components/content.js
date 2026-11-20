import { escapeHTML, flagSVG, formatRound } from './ui.js';
import { ClauseBoard } from './ClauseBoard.js';
import { strategyCatalog } from '../domain/negotiation.js';

function summaryBlock(title, items = []) {
  return `<div class="report-block"><h5>${escapeHTML(title)}</h5>${items.map(item => `<span class="report-kv"><em>${escapeHTML(item.label)}</em><b>${item.value == null ? '—' : escapeHTML(String(item.value))}</b></span>`).join('')}</div>`;
}

/**
 * 报价板：协议签署板就在报价板里（谈判树只放谈判树）。
 * 条款数值按 kind 渲染，不再统一标成「估计值 / 可信度」。
 */
export function ReportContent({ topic, clauses = [], drafts = {}, draftCount = 0, pendingCount = 0, submitting = false, summary = null, version = 1 }) {
  const summaryHtml = summary
    ? `<div class="report-summary">
        ${summaryBlock('谈判结果', summary.outcome)}
        ${summaryBlock('协议质量', summary.quality)}
        ${summaryBlock('学习表现', summary.learning)}
      </div>`
    : '';

  return `<div class="quote-board">
    <div class="quote-meta"><em>${escapeHTML(topic.mode)} · ${topic.maxRounds} 轮</em></div>
    ${summaryHtml}
    <div class="board-head"><strong>协议签署板</strong><small>逐条选定我方立场，再提交本轮修订</small></div>
    <div id="reportBoard">${ClauseBoard({ clauses, drafts, draftCount, pendingCount, submitting })}</div>
    <div class="board-foot"><span>协议版本</span><em class="version-chip" id="bdVer">v${version}</em></div>
  </div>`;
}

function highlightStrategy(text) {
  let safe = escapeHTML(text);
  strategyCatalog.forEach(strategy => {
    safe = safe.split(strategy.name).join(`<strong>${strategy.name}</strong>`);
  });
  return safe;
}

function treeNode(item) {
  const text = item.text;
  const privateNode = text.includes('通过非正式渠道');
  const party = (text.startsWith('我方') || privateNode)
    ? { id: 'cn', name: '中国代表团' }
    : { id: 'us', name: '美国代表团' };
  const badge = privateNode ? { label: '非公开', cls: 'private' } : { label: '公开', cls: 'public' };
  return `<article class="tree-node-card node-${party.id}">
    <div class="tree-node-row"><span class="tree-avatar">${flagSVG(party.id)}</span>
      <div class="tree-node-body"><div class="tree-node-head"><strong>${escapeHTML(party.name)}</strong><em class="tree-badge ${badge.cls}">${badge.label}</em></div>
        <p>${highlightStrategy(text)}</p><button class="round-jump" type="button" data-action="jump-round" data-round="${item.round}" aria-label="回到第 ${formatRound(item.round)} 轮">第 ${formatRound(item.round)} 轮</button></div></div>
  </article>`;
}

export function TreeContent({ state, topic }) {
  const log = state.log || [];
  const currentRound = Math.min(state.round, topic.maxRounds);
  let flow = '';
  log.forEach((item, index) => {
    if (index > 0 && log[index - 1].round === item.round) flow += '<span class="tree-connector" aria-hidden="true"></span>';
    flow += treeNode(item);
  });
  const lastRound = log.length ? log[log.length - 1].round : null;
  const connector = lastRound === currentRound ? '<span class="tree-connector" aria-hidden="true"></span>' : '';
  const current = `<article class="tree-node-card node-current">
    <div class="tree-node-row"><span class="tree-avatar tree-avatar-current" aria-hidden="true">◆</span>
      <div class="tree-node-body"><div class="tree-node-head"><strong>当前决策点</strong><em class="tree-badge current">决策中</em></div>
        <p>选择策略组合，推进公共算力配额与安全审查的条件交换。</p><small>第 ${formatRound(currentRound)} 轮</small></div></div>
  </article>`;

  return `<div class="tree-flow">
    <div class="tree-toolbar"><span>第 ${formatRound(currentRound)} 轮 · ${escapeHTML(topic.title)}</span><span>${log.length + 1} 个节点</span></div>
    ${flow}${connector}${current}
  </div>`;
}
