import { escapeHTML } from './ui.js';

const TITLES = {
  INVALID_ACTION: '行动不合法，未提交',
  SESSION_BUSY: '上一轮仍在处理',
  MODEL_UNAVAILABLE: '模型服务暂不可用',
  ROUND_LOCKED: '本轮已锁定',
  VERSION_CONFLICT: '选择已过期，未提交',
  TIMEOUT: '请求超时'
};

function primaryButton(error, busyLabel) {
  switch (error.error) {
    case 'INVALID_ACTION':
      return '<button class="eb-btn primary" data-action="locate-selection">定位到策略卡</button>';
    case 'MODEL_UNAVAILABLE':
      return `<button class="eb-btn primary" data-action="retry-turn">重试</button>
        <button class="eb-btn" data-action="fallback-turn">使用规则引擎基础行动</button>`;
    case 'ROUND_LOCKED':
      return '<button class="eb-btn primary" data-action="show-tree">查看谈判记录</button>';
    case 'VERSION_CONFLICT':
      return '<button class="eb-btn primary" data-action="rebase-version">重新提交当前选择</button>';
    case 'SESSION_BUSY':
      return `<button class="eb-btn primary" data-action="retry-turn" id="busyRetry">${escapeHTML(busyLabel || '立即重试')}</button>
        <button class="eb-btn" data-action="dismiss-error">取消等待</button>`;
    default:
      return `<button class="eb-btn primary" data-action="retry-turn">重试（沿用同一 action_id）</button>
        <button class="eb-btn" data-action="dismiss-error">取消本次请求</button>`;
  }
}

/**
 * 错误横幅：统一错误格式 { error, detail } 的展示层。
 * 失败不清空用户已选卡牌（草稿保留），并始终暴露 action_id 供联调核对幂等。
 */
export function ErrorBanner({ error, actionId, draftCount = 0, busyLabel = '' }) {
  if (!error) return '';
  const tone = error.error === 'SESSION_BUSY' || error.error === 'TIMEOUT' ? 'warn' : 'error';
  const title = TITLES[error.error] || '提交失败';
  const draft = draftCount > 0 ? `已选 ${draftCount} 张卡已保留，无需重选` : '无待提交选择';

  return `<div class="error-banner ${tone}" role="alert" aria-live="assertive">
    <span class="eb-mark" aria-hidden="true">${tone === 'warn' ? '!' : '×'}</span>
    <div class="eb-body">
      <strong>${escapeHTML(title)}</strong>
      <p>${escapeHTML(error.detail || '')}</p>
      <small>错误码 ${escapeHTML(error.error)} ｜ action_id ${escapeHTML(actionId || '未生成')} ｜ ${escapeHTML(draft)}</small>
      <div class="eb-actions">${primaryButton(error, busyLabel)}</div>
    </div>
  </div>`;
}
