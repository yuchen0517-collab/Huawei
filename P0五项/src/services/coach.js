// 教练 Agent 前端逻辑（对接第 6 天成果）：
// 只做展示与有效性校验，不生成建议、不改写谈判事实状态。
import { strategyCatalog } from '../domain/negotiation.js';



// 与第 6 天同一份禁用词表：命中即整条不渲染
export const LEAK_WORDS = ['对方红线', '对方真实', '对方batna', '真实底线', '私有', 'net_gain', '隐藏底牌'];

export function hasLeak(text) {
  const normalized = String(text == null ? '' : text).toLowerCase().replace(/\s+/g, '');
  return LEAK_WORDS.some(word => normalized.includes(word));
}

// 断言 1：证据可溯源。任一 evidence 解析失败，整条 item 作废。
function evidenceOk(evidence, state) {
  if (!evidence || typeof evidence !== 'object') return false;
  const round = Number(evidence.round);
  if (!(round >= 1 && round <= state.round)) return false;
  if (evidence.kind === 'action') {
    if (!evidence.action_id) return false;
    return Boolean(state.actions && state.actions[evidence.action_id]);
  }
  if (evidence.kind === 'offer') {
    return !evidence.clause || (state.clauses || []).some(clause => clause.name === evidence.clause);
  }
  if (evidence.kind === 'strategy') {
    return strategyCatalog.some(item => item.name === evidence.clause);
  }
  return false;
}

// 双重断言：证据可溯源 + 禁用词，过滤静默进行，只在控制台留痕。
export function sanitizeCoach(coach, state) {
  if (!coach || !Array.isArray(coach.items)) return coach;
  const kept = coach.items.filter(item => {
    const evidence = Array.isArray(item.evidence) ? item.evidence : [];
    if (evidence.some(single => !evidenceOk(single, state))) {
      console.warn('[coach] filtered item:', item.id, 'evidence');
      return false;
    }
    if (hasLeak(item.title) || hasLeak(item.text)) {
      console.warn('[coach] filtered item:', item.id, 'leak');
      return false;
    }
    return true;
  });
  return Object.assign({}, coach, { items: kept });
}

let coachMode = 'ready';
// 验收用：记录教练请求次数，证明「提交失败不触发」「同一轮只触发一次」
let requestCount = 0;

export function coachRequestCount() {
  return requestCount;
}

export function setCoachMode(mode) {
  coachMode = mode || 'ready';
}

export function getCoachMode() {
  return coachMode;
}

function latestAction(state) {
  const list = Object.keys(state.actions || {}).map(key => state.actions[key]);
  return list.length ? list[list.length - 1] : null;
}

function readyCoach(state) {
  const action = latestAction(state);
  const round = action ? action.round : Math.max(1, state.round - 1);
  const items = [
    {
      id: `adv-r${round}-01`,
      kind: 'stage',
      title: '先固定已达成的程序共识',
      text: `第 ${round} 轮以「${action ? action.label : '程序性保障'}」推进后，公开会场的分歧已收窄到审查范围与许可豁免两项；建议下一轮先请对方确认审查期限，再谈配额折算。`,
      evidence: action
        ? [{ kind: 'action', round, action_id: action.action_id, clause: null, label: action.label }]
        : [],
      ap_cost: null,
      apply_hint: null
    },
    {
      id: `adv-r${round}-02`,
      kind: 'alternative',
      title: '用观察员换豁免口径',
      text: '若对方坚持核心清单保留，可提出以第三方观察员常驻折算豁免项，预计用 2 点行动力换取「逐案许可豁免」的口径松动。',
      evidence: [{ kind: 'offer', round, action_id: null, clause: '逐案许可豁免', label: '豁免条款仍未决' }],
      ap_cost: 2,
      apply_hint: '在战报里把「逐案许可豁免」改为「议题捆绑」，并在发言中说明观察员常驻期限'
    }
  ];

  const coach = {
    status: 'ready',
    basis_round: round,
    basis_version: state.version,
    generated_at: new Date().toISOString(),
    items,
    fail_reason: null
  };

  if (coachMode === 'stale') coach.basis_version = Math.max(1, state.version - 2);
  if (coachMode === 'badEvidence') coach.items[0].evidence[0].action_id = 'a999999';
  if (coachMode === 'leak') coach.items[0].text = '对方真实 BATNA 低于其公开立场，建议直接压价。';
  return coach;
}

// 异步生成：三态 mock，返回结构与第 6 天契约一致（snake_case）
export function fetchCoach(state) {
  requestCount += 1;
  return new Promise(resolve => {
    setTimeout(() => {
      if (coachMode === 'pending') {
        resolve({ ok: true, coach: { status: 'pending', basis_round: state.round, basis_version: state.version, items: [], fail_reason: null } });
        return;
      }
      if (coachMode === 'failed') {
        resolve({ ok: true, coach: { status: 'failed', items: [], fail_reason: '模型暂不可用，请稍后重试' } });
        return;
      }
      resolve({ ok: true, coach: readyCoach(state) });
    }, 700);
  });
}
