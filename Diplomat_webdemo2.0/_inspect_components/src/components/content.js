import { escapeHTML, formatRound } from './ui.js';

export function ReportContent({ topic, state }) {
  const logs = state.log.map(item => `<li><time>ROUND ${formatRound(item.round)}</time><span>${escapeHTML(item.text)}</span></li>`).join('');
  return `<div class="report-hero"><img src="/report-logo.png" alt="战报图标"><div><span>AFTER ACTION REPORT</span><h3>${escapeHTML(topic.title)}</h3><p>${escapeHTML(topic.mode)} · 本地演示记录 · 共 ${topic.maxRounds} 轮</p></div></div><div class="report-stats"><div><strong>${formatRound(Math.min(state.round, topic.maxRounds))}</strong><span>当前轮次</span></div><div><strong>${state.metrics.interest}</strong><span>主体利益</span></div><div><strong>${state.metrics.image}</strong><span>国际形象</span></div></div><ul class="report-log">${logs}</ul>`;
}

export function EventContent({ topic }) {
  return `<div class="event-card"><span>${escapeHTML(topic.eyebrow)}</span><h3>产业联盟发布联合声明</h3><p>多家科技企业呼吁建立“可互认”的安全审查机制，并反对将公共算力配额设为强制义务。会场对审查条款的关注显著上升。</p><div class="event-effects"><span>审查议题热度 +1</span><span>公开倡议收益增强</span><span>持续 2 轮</span></div></div>`;
}

export function TreeContent({ log }) {
  return `<ul class="tree-list">${log.map(item => `<li><strong>第 ${item.round} 轮</strong><p>${escapeHTML(item.text)}</p></li>`).join('')}<li><strong>当前决策点</strong><p>选择策略组合，推进公共算力配额与安全审查的条件交换。</p></li></ul>`;
}

export function OpponentIntelContent() {
  return '<div class="intel-list"><div class="intel-row"><strong>合作窗口 · 有限开放</strong><p>依据：对方主动将“逐案许可”与公共算力配额并置讨论。可信度：中。</p></div><div class="intel-row"><strong>核心红线 · 安全审查</strong><p>依据：开场陈述明确拒绝无条件开放。审查范围与期限仍可能协商。</p></div><div class="intel-row"><strong>建议策略 · 明确对价</strong><p>优先使用议题捆绑或一揽子方案，避免无回报的单边让步。</p></div></div>';
}

export function ChannelContent() {
  return '<div class="channel-room"><h3>美国代表团 · 会下接触</h3><p>“我们可以接受把审查期限写入文本，但公共算力配额需要保留年度复核安排。此表态仅作为意向，仍须公开确认。”</p><p><strong>渠道规则：</strong>当前仅可交换意向，不形成秘密约束；任何承诺均须进入正式提案后生效。</p></div>';
}
