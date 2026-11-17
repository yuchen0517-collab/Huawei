export const END_REASONS = {
  full_agreement: 'full_agreement',
  partial: 'partial',
  withdraw: 'withdraw',
  stalemate: 'stalemate',
  rounds_exhausted: 'rounds_exhausted'
};

export const ENDGAME_COPY = {
  full_agreement: {
    title: '协议达成',
    kicker: 'AGREEMENT',
    tone: 'tone-gold',
    summary: '全部条款已决，我方已接受当前条件。'
  },
  partial: {
    title: '部分协议',
    kicker: 'PARTIAL DEAL',
    tone: 'tone-amber',
    summary: '部分条款已经解决，仍有未决或被拒条款，未形成完整协议。'
  },
  withdraw: {
    title: '我方主动退出',
    kicker: 'WITHDRAWN',
    tone: 'tone-neutral',
    summary: '我方主动退出。过程与已达成条款保留在战报中，不判胜负。'
  },
  stalemate: {
    title: '谈判陷入僵局',
    kicker: 'STALEMATE',
    tone: 'tone-danger',
    summary: '连续 3 轮未产生新条款，谈判进入僵局。'
  },
  rounds_exhausted: {
    title: '轮次用尽',
    kicker: 'ROUNDS EXHAUSTED',
    tone: 'tone-danger',
    summary: '轮次已用尽，未形成可签署的完整协议。'
  }
};

function clauseStats(state) {
  const clauses = state.clauses || [];
  return {
    decided: clauses.filter(clause => clause.status === 'decided').length,
    rejected: clauses.filter(clause => clause.status === 'rejected').length,
    total: clauses.length
  };
}

function acceptedByUs(state) {
  return Object.keys(state.actions || {}).some(key => {
    const action = state.actions[key];
    return Boolean(action && action.baseAction && action.baseAction.kind === 'accept');
  });
}

function metricsHint(state, stats) {
  const interest = state.metrics && Number.isFinite(state.metrics.interest) ? ` · 主体利益 ${state.metrics.interest}` : '';
  const rejected = stats.rejected > 0 ? ` · 被拒 ${stats.rejected}` : '';
  return `已决 ${stats.decided}/${stats.total}${rejected}${interest}`;
}

function result(reason, state, stats) {
  const copy = ENDGAME_COPY[reason];
  return {
    reason,
    title: copy.title,
    summary: copy.summary,
    metricsHint: reason === 'stalemate' ? `连续 3 轮无新条款 · ${metricsHint(state, stats)}` : metricsHint(state, stats)
  };
}

/** 终局判定的唯一入口；判不出来返回 null。 */
export function judgeEnd(state) {
  if (!state) return null;
  const stats = clauseStats(state);
  const allResolved = stats.total > 0 && stats.decided + stats.rejected === stats.total;

  if (state.endReason === 'withdraw') return result('withdraw', state, stats);

  if (allResolved) {
    if (stats.decided === stats.total && acceptedByUs(state)) return result('full_agreement', state, stats);
    return result('partial', state, stats);
  }

  if ((state.stagnantRounds || 0) >= 3) return result('stalemate', state, stats);

  if (state.round > state.maxRounds) {
    if (stats.decided > 0) return result('partial', state, stats);
    return result('rounds_exhausted', state, stats);
  }

  return null;
}

/** 战报三段的数据先由领域层推算，组件只负责渲染；无值用 null，展示为「—」。 */
export function buildReportSummary(state) {
  const clauses = state.clauses || [];
  const decided = clauses.filter(clause => clause.status === 'decided').length;
  const rejected = clauses.filter(clause => clause.status === 'rejected').length;
  const total = clauses.length;
  const actions = Object.keys(state.actions || {}).map(key => state.actions[key]);
  const usedPoints = actions.reduce((sum, action) => sum + (Number(action.used) || 0), 0);
  const rejectCount = actions.filter(action => action.baseAction && action.baseAction.kind === 'reject').length;
  const metrics = state.metrics || {};

  return {
    outcome: [
      { label: '主体利益', value: Number.isFinite(metrics.interest) ? metrics.interest : null },
      { label: '国际形象', value: Number.isFinite(metrics.image) ? metrics.image : null }
    ],
    quality: [
      { label: '已决条款', value: total ? `${decided}/${total}` : null },
      { label: '被拒条款', value: total ? `${rejected}/${total}` : null }
    ],
    learning: [
      { label: '已用行动点', value: actions.length ? `${usedPoints} 点` : null },
      { label: '我方拒绝次数', value: actions.length ? rejectCount : null }
    ]
  };
}