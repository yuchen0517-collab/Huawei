import { buildReportSummary, judgeEnd, ENDGAME_COPY } from './endgame.js';

const DATA_SOURCE = '本页数字来自本局结构化状态；模型解说仅供参考，不构成事实。';

function actionEntries(state) {
  return Object.keys(state.actions || {})
    .map(key => state.actions[key])
    .filter(action => action && Number.isFinite(Number(action.round)));
}

function buildTurningPoints(state) {
  return actionEntries(state)
    .sort((a, b) => (Number(a.round) - Number(b.round)) || (Number(a.version || 0) - Number(b.version || 0)))
    .slice(-4)
    .map(action => ({
      round: Number(action.round),
      label: action.label || '行动',
      version: action.version == null ? null : action.version,
      kind: action.baseAction && action.baseAction.kind !== 'none'
        ? 'base'
        : (Array.isArray(action.strategyIds) && action.strategyIds.length ? 'strategy' : 'revision')
    }));
}

/** 教练契约 §1.3 断言 1：任一条件不成立，整条证据丢弃。 */
function collectEvidence(state) {
  const actions = state.actions || {};
  const clauseNames = new Set((state.clauses || []).map(clause => clause.name));
  const items = state.coach && Array.isArray(state.coach.items) ? state.coach.items : [];
  const evidence = [];

  items.forEach(item => {
    (item.evidence || []).forEach(entry => {
      if (!entry || typeof entry !== 'object') return;
      const round = Number(entry.round);
      if (!(round >= 1 && round <= state.maxRounds)) return;
      if (entry.kind === 'action') {
        if (!entry.action_id || !actions[entry.action_id]) return;
      } else if (entry.clause && !clauseNames.has(entry.clause)) {
        return;
      }
      evidence.push({
        action_id: entry.action_id || null,
        round,
        kind: entry.kind || 'event',
        clause: entry.clause || null,
        label: entry.label || '证据'
      });
    });
  });

  return evidence;
}

export function buildDebrief(state) {
  const summary = buildReportSummary(state);
  const verdict = judgeEnd(state);
  const unresolved = (state.clauses || [])
    .filter(clause => ['pending', 'open', 'rejected'].includes(clause.status))
    .map(clause => ({
      id: clause.id,
      name: clause.name,
      status: clause.status,
      changedVersion: clause.changedVersion
    }));
  const speakerScorePresent = Object.prototype.hasOwnProperty.call(state, 'speakerScore')
    || Object.prototype.hasOwnProperty.call(state, 'speaker_score');
  const speakerScore = state.speakerScore || state.speaker_score || null;

  return {
    outcome: summary.outcome,
    quality: summary.quality,
    learning: summary.learning,
    verdict: verdict
      ? {
          reason: verdict.reason,
          title: verdict.title,
          summary: verdict.summary,
          metricsHint: verdict.metricsHint,
          kicker: ENDGAME_COPY[verdict.reason].kicker,
          tone: ENDGAME_COPY[verdict.reason].tone
        }
      : null,
    turningPoints: buildTurningPoints(state),
    unresolved,
    evidence: collectEvidence(state),
    dataSource: DATA_SOURCE,
    speakerScore,
    speakerScorePresent
  };
}