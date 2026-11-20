import { escapeHTML, icon } from './ui.js';

const KIND_LABEL = { stage: '阶段建议', alternative: '替代行动' };

function evidenceList(items) {
  if (!items || !items.length) return '';
  return `<div class="coach-evidence">${items.map(item =>
    `<span class="coach-ev">R${escapeHTML(item.round)} · ${escapeHTML(item.label)}</span>`
  ).join('')}</div>`;
}

function itemMarkup(item) {
  const kind = item.kind === 'alternative' ? 'alternative' : 'stage';
  return `<article class="coach-item">
    <div class="coach-item-head"><em class="coach-kind ${kind}">${KIND_LABEL[kind]}</em><strong>${escapeHTML(item.title)}</strong></div>
    <p>${escapeHTML(item.text)}</p>
    ${evidenceList(item.evidence)}
    ${item.ap_cost == null ? '' : `<span class="coach-cost">预计消耗 ${escapeHTML(String(item.ap_cost))} 行动点</span>`}
    ${item.apply_hint ? `<span class="coach-hint">${escapeHTML(item.apply_hint)}</span>` : ''}
  </article>`;
}

/**
 * 教练面板：默认折叠、三态渲染、不阻塞。
 * 只读渲染，没有任何「一键应用」入口——手册要求教练不代替用户做决定。
 */
export function CoachPanel({ coach, status = 'idle', collapsed = true, version = 1 }) {
  const items = coach && Array.isArray(coach.items) ? coach.items : [];
  const basisVersion = coach && coach.basis_version;
  const stale = status === 'ready' && typeof basisVersion === 'number' && basisVersion < version;

  const title = status === 'pending' ? '教练建议生成中'
    : status === 'ready' ? `教练建议 · ${items.length} 条`
      : status === 'failed' ? '教练建议暂不可用'
        : '教练建议';

  const meta = status === 'pending' ? '<i class="coach-breath" aria-hidden="true"></i>异步生成'
    : status === 'ready' ? (stale ? '建议已过期' : '不阻塞下一轮')
      : status === 'failed' ? escapeHTML((coach && coach.fail_reason) || '生成失败')
        : '提交本轮后生成';

  let body = '';
  if (!collapsed) {
    if (status === 'ready') {
      body = items.length
        ? items.map(itemMarkup).join('')
        : '<p class="coach-empty">本轮暂无建议<span>模型返回空数组，不编造建议</span></p>';
    } else if (status === 'pending') {
      body = `<p class="coach-empty">正在分析本轮策略选择<span>不影响你继续选卡或提交下一轮</span></p>`;
    } else if (status === 'failed') {
      body = `<p class="coach-empty">${escapeHTML((coach && coach.fail_reason) || '生成失败')}</p>
        <button class="coach-retry" data-action="retry-coach">重试一次</button>`;
    } else {
      body = '<p class="coach-empty">本轮提交成功后异步生成<span>不占用行动点、不改变报价</span></p>';
    }
  }

  return `<section class="coach-panel" id="coachPanel" aria-label="教练建议">
    <button class="coach-head" data-action="toggle-coach" aria-expanded="${!collapsed}">
      <span class="coach-title">${escapeHTML(title)}</span>
      <span class="coach-meta${stale ? ' stale' : ''}">${meta}</span>
      ${icon('chevron', 'coach-chevron')}
    </button>
    ${collapsed ? '' : `<div class="coach-body">${body}</div>`}
  </section>`;
}
