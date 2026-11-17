export const CLAUSE_STATUS = {
  open: '未决',
  pending: '待确认',
  decided: '已决',
  rejected: '已拒绝'
};

/**
 * 条款的单一事实源。id 一旦定下不再修改，后续策略卡、教练、规则审计都按 id 引用。
 * theirValue 的字段形状沿用战报现有的 kind/num/unit/label 结构。
 */
export function createInitialClauses() {
  return [
    {
      id: 'compute-quota',
      name: '公共算力配额',
      ourStance: '维持现立场',
      theirStance: '年度复核',
      theirValue: { kind: 'months', num: 12, unit: '个月', label: '复核周期 12 个月' },
      confidence: 78,
      status: 'decided',
      changedRound: 1,
      changedVersion: 1
    },
    {
      id: 'security-review',
      name: '安全审查范围',
      ourStance: '维持现立场',
      theirStance: '限定于高风险模型',
      theirValue: { kind: 'count', num: 3, unit: '类', label: '覆盖 3 类高风险模型' },
      confidence: 76,
      status: 'decided',
      changedRound: 1,
      changedVersion: 1
    },
    {
      id: 'license-exemption',
      name: '逐案许可豁免',
      ourStance: '维持现立场',
      theirStance: '保留核心清单',
      theirValue: { kind: 'count', num: 27, unit: '项', label: '核心清单保留 27 项' },
      confidence: 72,
      status: 'pending',
      changedRound: 1,
      changedVersion: 1
    },
    {
      id: 'third-party-observer',
      name: '第三方观察员',
      ourStance: '维持现立场',
      theirStance: '接受观察但不介入',
      theirValue: { kind: 'percent', num: 34, label: '介入意愿 34%' },
      confidence: 65,
      status: 'open',
      changedRound: 1,
      changedVersion: 1
    },
    {
      id: 'dispute-resolution',
      name: '争端解决机制',
      ourStance: '维持现立场',
      theirStance: '未表态',
      theirValue: { kind: 'none', label: '暂无数据' },
      confidence: 60,
      status: 'pending',
      changedRound: 1,
      changedVersion: 1
    }
  ];
}

export function clausesSummary(clauses) {
  const summary = { decided: 0, pending: 0, open: 0, rejected: 0, total: 0 };
  (clauses || []).forEach(clause => {
    if (Object.prototype.hasOwnProperty.call(summary, clause.status)) summary[clause.status] += 1;
    summary.total += 1;
  });
  return summary;
}
function sameValue(a, b) {
  if (a === b) return true;
  if (!a || !b) return false;
  return a.kind === b.kind && a.num === b.num && a.unit === b.unit && a.label === b.label;
}

/** 只比较本轮前后两份 clauses，不累计。 */
export function diffClauses(prevClauses, nextClauses) {
  const previous = new Map((prevClauses || []).map(clause => [clause.id, clause]));
  const diff = { accepted: [], modified: [], rejected: [], unchanged: [] };
  (nextClauses || []).forEach(next => {
    const before = previous.get(next.id);
    if (!before) {
      diff.modified.push(next.name);
      return;
    }
    if (before.status !== 'decided' && next.status === 'decided') {
      diff.accepted.push(next.name);
      return;
    }
    if (next.status === 'rejected' && before.status !== 'rejected') {
      diff.rejected.push(next.name);
      return;
    }
    const changed = before.theirStance !== next.theirStance
      || before.ourStance !== next.ourStance
      || !sameValue(before.theirValue, next.theirValue);
    if (changed) diff.modified.push(next.name);
    else diff.unchanged.push(next.name);
  });
  return diff;
}

/** 无任何变化时返回空串，避免为「全是未变」渲染摘要行。 */
export function formatDiff(diff) {
  if (!diff) return '';
  const accepted = (diff.accepted || []).length;
  const modified = (diff.modified || []).length;
  const rejected = (diff.rejected || []).length;
  const unchanged = (diff.unchanged || []).length;
  if (accepted + modified + rejected === 0) return '';
  const parts = [];
  if (accepted) parts.push(`接受 ${accepted}`);
  if (modified) parts.push(`修改 ${modified}`);
  if (rejected) parts.push(`拒绝 ${rejected}`);
  if (unchanged) parts.push(`未变 ${unchanged}`);
  return parts.join(' · ');
}