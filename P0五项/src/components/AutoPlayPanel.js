import { escapeHTML } from './ui.js';

const STATUS_LABEL = { ok: '完成', paused: '暂停', stopped: '停止' };
const REASON_LABEL = {
  user: '用户停止',
  paused: '人工接管',
  step: '单步完成',
  round_locked: '轮次锁定',
  error: '请求错误',
  ended: '终局',
  no_intent: '无可用行动',
  version_conflict: '版本不一致'
};

function statusText(autoPlay, round, ended) {
  if (ended) return '终局已停止';
  if (autoPlay.lastError === 'paused') return '已暂停（人工接管）';
  if (autoPlay.lastError === 'step') return '单步完成，等待下一单步';
  if (autoPlay.lastError && !autoPlay.active) return `已停止：${REASON_LABEL[autoPlay.lastError] || autoPlay.lastError}`;
  if (autoPlay.active && autoPlay.pendingRound != null) {
    return `自动推演 R${autoPlay.pendingRound} → R${autoPlay.pendingRound + 1} · 等待对方回应`;
  }
  if (autoPlay.active) return autoPlay.mode === 'step' ? '单步模式 · 等待下一轮' : `自动推演中 · R${round}`;
  return '未开始';
}

function timeText(at) {
  if (!at) return '—';
  const date = new Date(at);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleTimeString('zh-CN', { hour12: false });
}

export function AutoPlayPanel({ autoPlay = {}, round = 1, ended = false, phase = 'ready' }) {
  const active = Boolean(autoPlay.active);
  const speed = autoPlay.speed || 1;
  const steps = autoPlay.steps || [];
  const loading = phase === 'loading';
  const logRows = steps.map(step => {
    const cv = step.clausesVersion == null ? '—' : String(step.clausesVersion);
    return `<li>R${escapeHTML(String(step.round))} · ${escapeHTML(String(step.label || '推进'))} · v${escapeHTML(String(step.version))} / cv${escapeHTML(cv)} · ${escapeHTML(timeText(step.at))} · <em class="ap-st-${escapeHTML(step.status)}">${STATUS_LABEL[step.status] || escapeHTML(step.status)}</em>${step.reason ? ` · ${escapeHTML(REASON_LABEL[step.reason] || step.reason)}` : ''}</li>`;
  }).join('');

  return `<div class="autoplay-panel" id="autoPlayPanel">
    <div class="status-strip autoplay-bar" role="status">
      <span class="ss-dot" aria-hidden="true"></span><strong>自动推演</strong>
      <span class="ap-status">${escapeHTML(statusText(autoPlay, round, ended))}</span>
      <button type="button" class="action-bar-btn" data-action="autoplay-start"${active || ended ? ' disabled' : ''}>开始</button>
      <button type="button" class="action-bar-btn" data-action="autoplay-pause"${active ? '' : ' disabled'}>暂停</button>
      <button type="button" class="action-bar-btn" data-action="autoplay-step"${ended || loading ? ' disabled' : ''}>单步</button>
      <button type="button" class="action-bar-btn" data-action="autoplay-stop"${active ? '' : ' disabled'}>停止</button>
      ${[1, 1.5, 2].map(value => `<button type="button" class="action-bar-btn ap-speed" data-action="autoplay-speed" data-speed="${value}" aria-pressed="${speed === value}">${value}x</button>`).join('')}
    </div>
    <details class="autoplay-log">
      <summary data-action="toggle-autoplay-log">推演日志（${steps.length} 步）</summary>
      ${steps.length ? `<ol>${logRows}</ol>` : '<p class="ap-empty">暂无步骤</p>'}
    </details>
  </div>`;
}