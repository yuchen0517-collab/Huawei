import { createInitialNegotiation, strategyCatalog, BASE_ACTION_LABELS } from '../domain/negotiation.js';
import { clausesSummary as summarizeClauses, diffClauses } from '../domain/clauses.js';
import { judgeEnd } from '../domain/endgame.js';

// 对方让步脚本：按提交轮次确定性覆盖条款，最多 5 轮；第 3 轮留空用于「无变化不显示」验收。
const OPPONENT_PATCHES = [
  [
    { id: 'license-exemption', theirStance: '接受豁免清单（保留 21 项）', theirValue: { kind: 'count', num: 21, unit: '项', label: '核心清单保留 21 项' } },
    { id: 'third-party-observer', theirValue: { kind: 'percent', num: 41, label: '介入意愿 41%' } },
    { id: 'dispute-resolution', theirStance: '愿讨论常设仲裁' }
  ],
  [
    { id: 'license-exemption', status: 'decided' },
    { id: 'compute-quota', theirValue: { kind: 'months', num: 10, unit: '个月', label: '复核周期 10 个月' } }
  ],
  [],
  [
    { id: 'third-party-observer', status: 'rejected' },
    { id: 'security-review', theirStance: '限定于高风险且可复核', theirValue: { kind: 'count', num: 4, unit: '类', label: '覆盖 4 类高风险模型' } }
  ],
  [
    { id: 'dispute-resolution', status: 'decided' }
  ]
];

const pad = round => String(round).padStart(2, '0');

const COACH_KEYS = ['coach', 'coachStatus', 'coachCollapsed'];

/** UI-independent negotiation state and rules. All methods are synchronous. */
export class NegotiationStore {
  constructor() {
    this.state = createInitialNegotiation();
  }

  /** 只读派生：条款状态计数，不写回 state。 */
  get clausesSummary() {
    return summarizeClauses(this.state.clauses);
  }

  /** 终局判定唯一入口（纯函数），main 只消费结果。 */
  get judge() {
    return judgeEnd(this.state);
  }

  get strategyMap() {
    return new Map(strategyCatalog.map(strategy => [strategy.id, strategy]));
  }

  get selectedStrategies() {
    return this.state.selectedIds.map(id => this.strategyMap.get(id)).filter(Boolean);
  }

  get usedActionPoints() {
    return this.selectedStrategies.reduce((total, strategy) => total + strategy.cost, 0);
  }

  get canEndTurn() {
    return (this.state.selectedIds.length > 0 || this.state.baseAction.kind !== 'none' || Object.keys(this.state.stanceDrafts || {}).length > 0)
      && !this.state.ended
      && !this.state.roundLocked
      && this.state.phase !== 'loading'
      && this.state.round <= this.state.maxRounds;
  }

  /** 接受：存在待确认/已决条款，且对方在最新一轮里更新过条款。 */
  get canAccept() {
    const state = this.state;
    if (state.ended || state.roundLocked || state.phase === 'loading') return false;
    if (!(state.version > 1)) return false;
    return (state.clauses || []).some(clause =>
      clause.changedVersion === state.version && (clause.status === 'pending' || clause.status === 'decided'));
  }

  /** 只读派生：基础行动条的可用性、原因与选中态。组件不做业务判断。 */
  get baseActions() {
    const state = this.state;
    const lockedReason = state.ended
      ? '本场谈判已结束'
      : state.roundLocked
        ? '本轮已锁定'
        : state.phase === 'loading'
          ? '本轮提交中'
          : '';
    const locked = Boolean(lockedReason);
    const selected = state.baseAction.kind;
    const accept = this.canAccept;
    const awaiting = state.responseWindow.open;
    return [
      { id: 'accept', label: '接受', hint: '接受对方最新条款', disabled: locked || !accept, reason: '当前没有可接受的条款', used: selected === 'accept', primary: awaiting },
      { id: 'reject', label: '拒绝', hint: '拒绝对方最新提案，继续谈判', disabled: locked, reason: lockedReason, used: selected === 'reject', primary: awaiting },
      { id: 'hold', label: '维持现立场', hint: '不调整条款，保持当前立场', disabled: locked, reason: lockedReason, used: selected === 'hold' },
      { id: 'final', label: '最后报价', hint: '每场限用一次，占一轮但不消耗行动点', disabled: locked || state.finalOfferUsed, reason: state.finalOfferUsed ? '本场已使用最后报价' : lockedReason, used: selected === 'final' || state.finalOfferUsed },
      { id: 'exit', label: '宣布退出', hint: '主动退出本场谈判', disabled: locked, reason: lockedReason, used: selected === 'exit' }
    ];
  }

  toggleStrategy(id) {
    if (this.state.ended || this.state.roundLocked) return { ok: false, reason: 'ended' };
    if (this.state.phase === 'loading') return { ok: false, reason: 'loading' };
    const strategy = this.strategyMap.get(id);
    if (!strategy) return { ok: false, reason: 'unknown' };
    if (this.state.selectedIds.includes(id)) {
      this.state.selectedIds = this.state.selectedIds.filter(selectedId => selectedId !== id);
      return { ok: true, selected: false, clearedBaseAction: false };
    }
    if (this.usedActionPoints + strategy.cost > this.state.actionPoints) return { ok: false, reason: 'points' };
    const clearedBaseAction = this.state.baseAction.kind !== 'none';
    if (clearedBaseAction) this.state.baseAction = { kind: 'none', atRound: 0, atVersion: 0 };
    this.state.selectedIds = [...this.state.selectedIds, id];
    return { ok: true, selected: true, clearedBaseAction };
  }

  /** 基础行动与选卡互斥：成功选中基础行动时清空卡牌草稿。 */
  chooseBaseAction(kind) {
    const state = this.state;
    if (state.ended) return { ok: false, reason: 'ended' };
    if (state.roundLocked) return { ok: false, reason: 'locked' };
    if (state.phase === 'loading') return { ok: false, reason: 'loading' };
    if (!BASE_ACTION_LABELS[kind]) return { ok: false, reason: 'unknown' };
    if (kind === 'final' && state.finalOfferUsed) return { ok: false, reason: 'used' };
    if (kind === 'accept' && !this.canAccept) return { ok: false, reason: 'accept' };
    const clearedCards = state.selectedIds.length > 0;
    state.selectedIds = [];
    state.baseAction = { kind, atRound: state.round, atVersion: state.version };
    return { ok: true, clearedCards };
  }

  clearBaseAction() {
    this.state.baseAction = { kind: 'none', atRound: 0, atVersion: 0 };
  }

  /** 签署板草稿：只记录 clauseId → stance，提交失败时原样保留。 */
  setStanceDraft(clauseId, stance) {
    if (!clauseId) return;
    this.state.stanceDrafts = { ...this.state.stanceDrafts, [clauseId]: stance };
  }

  clearStanceDrafts() {
    this.state.stanceDrafts = {};
  }

  /** 第一段：只算「要提交什么」，不改任何状态。提交失败时草稿（已选卡牌）自然保留。 */
  prepareTurn() {
    if (!this.canEndTurn) return null;
    const round = this.state.round;
    const selected = this.selectedStrategies;
    const hasStrategies = selected.length > 0;
    const baseLabel = BASE_ACTION_LABELS[this.state.baseAction.kind] || '基础行动';
    const revisions = Object.keys(this.state.stanceDrafts || {}).map(clauseId => ({
      clauseId,
      stance: this.state.stanceDrafts[clauseId]
    }));
    return {
      round,
      version: this.state.version,
      strategyIds: [...this.state.selectedIds],
      baseAction: { ...this.state.baseAction },
      revisions,
      names: selected.map(strategy => strategy.name),
      label: hasStrategies ? selected.map(strategy => strategy.name).join('、') : revisions.length > 0 ? `协议修订 ${revisions.length} 条` : baseLabel,
      used: this.usedActionPoints,
      text: hasStrategies
        ? `我方本轮采取「${selected.map(strategy => strategy.name).join('」「')}」策略。所有安排均以对等、透明和可核查为前提，期待贵方给出相应承诺。`
        : revisions.length > 0
          ? `我方对 ${revisions.length} 条条款提交立场修订，请对方确认。`
          : `我方本轮不调整策略卡，直接采取基础行动「${baseLabel}」，请贵方记录我方立场。`
    };
  }

  /** 第二段：服务端接受后才落地。版本、轮次、行动账本在这里一次写清。 */
  applyTurn(payload, { actionId, version }) {
    const state = this.state;
    const clausesVersionBefore = state.clausesVersion;
    const selectedIds = new Set(payload.strategyIds);

    if (selectedIds.has('bundle') || selectedIds.has('package')) state.metrics.interest = Math.min(100, state.metrics.interest + 3);
    if (selectedIds.has('initiative')) state.metrics.image = Math.min(100, state.metrics.image + 2);
    if (selectedIds.has('concession') || selectedIds.has('clarify')) state.metrics.trust = Math.min(100, state.metrics.trust + 1);

    const hasStrategies = payload.strategyIds.length > 0;
    state.log.push({
      round: payload.round,
      text: hasStrategies
        ? `我方使用${payload.label}，消耗 ${payload.used} 点行动点。`
        : `我方采取基础行动「${payload.label}」，不消耗行动点。`
    });
    state.speeches.push({
      round: payload.round,
      party: 'cn',
      label: `ROUND ${pad(payload.round)} · ${hasStrategies ? '策略出牌' : '基础行动'}`,
      text: payload.text,
      actionId
    });

    state.actions[actionId] = {
      action_id: actionId,
      round: payload.round,
      label: payload.label,
      strategyIds: payload.strategyIds,
      baseAction: payload.baseAction || { kind: 'none', atRound: 0, atVersion: 0 },
      used: payload.used,
      version
    };

    const revisions = payload.revisions || [];
    if (revisions.length > 0) {
      revisions.forEach(({ clauseId, stance }) => {
        const clause = state.clauses.find(item => item.id === clauseId);
        if (!clause) return;
        if (stance === 'accept') {
          clause.ourStance = clause.theirStance;
          clause.status = 'decided';
        } else if (stance === 'modify') {
          clause.ourStance = `提出修改：${clause.ourStance}`;
          clause.status = 'pending';
        } else if (stance === 'reject') {
          clause.status = 'rejected';
        }
        clause.changedRound = payload.round;
        clause.changedVersion = version;
      });
      state.clausesVersion += 1;
      state.stanceDrafts = {};
    }

    const baseKind = payload.baseAction ? payload.baseAction.kind : 'none';
    if (baseKind === 'final') state.finalOfferUsed = true;
    if (baseKind === 'exit') {
      state.ended = true;
      state.endReason = 'withdraw';
    }
    // 任一基础行动都视为完成一次表态并关窗；纯选卡提交不代我方表态，窗口保留。
    if (baseKind !== 'none') this.closeResponseWindow();
    state.baseAction = { kind: 'none', atRound: 0, atVersion: 0 };
    state.selectedIds = [];
    state.round += 1;
    state.version = version;
    state.stagnantRounds = state.clausesVersion > clausesVersionBefore ? 0 : state.stagnantRounds + 1;
    state.phase = 'ready';
    state.error = null;
    return payload;
  }

  failSubmit(error) {
    // 只记录错误，不动 selectedIds / round / version —— 草稿必须保留
    this.state.phase = 'ready';
    this.state.error = error;
  }

  clearError() {
    this.state.error = null;
  }

  rebaseVersion(serverVersion) {
    if (typeof serverVersion === 'number' && serverVersion > this.state.version) {
      this.state.version = serverVersion;
    }
    this.state.error = null;
  }

  lockRound() {
    this.state.roundLocked = true;
    this.state.phase = 'ready';
  }

  setPhase(phase) {
    this.state.phase = phase;
  }

  /** 教练状态独立槽位：严禁触碰 round / version / actionPoints / metrics / actions。 */
  patchCoach(partial) {
    COACH_KEYS.forEach(key => {
      if (partial && Object.prototype.hasOwnProperty.call(partial, key)) this.state[key] = partial[key];
    });
  }

  toggleCoach() {
    this.state.coachCollapsed = !this.state.coachCollapsed;
  }

  /** 待表态窗口：开窗、过渡、关闭、超时判定。窗口不写教练槽位，也不阻塞出牌。 */
  openResponseWindow(version, round) {
    this.state.responseWindow = {
      open: true,
      version,
      openedRound: round,
      deadlineRound: round + 2,
      transitionUsed: false
    };
  }

  useTransition() {
    const windowState = this.state.responseWindow;
    if (!windowState.open || windowState.transitionUsed) return { ok: false };
    windowState.transitionUsed = true;
    windowState.deadlineRound += 1;
    return { ok: true };
  }

  closeResponseWindow() {
    this.state.responseWindow.open = false;
  }

  checkWindowTimeout() {
    const windowState = this.state.responseWindow;
    return Boolean(windowState.open) && this.state.round > windowState.deadlineRound;
  }

  recordOpponentReply(round) {
    const previous = this.state.clauses.map(clause => ({ ...clause, theirValue: { ...clause.theirValue } }));
    const patches = OPPONENT_PATCHES[round - 1] || [];
    patches.forEach(patch => {
      const clause = this.state.clauses.find(item => item.id === patch.id);
      if (!clause) return;
      Object.assign(clause, patch);
      clause.changedRound = round;
      clause.changedVersion = this.state.version;
    });
if (patches.length > 0) {
      this.state.clausesVersion += 1;
      this.state.stagnantRounds = 0;
      this.openResponseWindow(this.state.version, this.state.round);
    }
    const clauseDiff = diffClauses(previous, this.state.clauses);

    this.state.log.push({ round, text: '美方接受继续讨论程序性保障，要求同步处理配额与审查文本。' });
    const speech = {
      round,
      party: 'us',
      label: `ROUND ${pad(round)} · 对方回应`,
      text: '我们注意到贵方方案中的交换条件。程序性保障可以作为下一步磋商基础，但公共算力配额与安全审查仍需同步形成文本。',
      clauseDiff
    };
    this.state.speeches.push(speech);
    return speech;
  }

  recordPrivateIntent() {
    this.state.log.push({ round: Math.min(this.state.round, this.state.maxRounds), text: '通过非正式渠道确认：对方愿意讨论审查期限与年度复核。' });
  }

  /**
   * 回到指定轮次。指标（metrics）与事件已读状态有意不回滚：
   * 逐轮回滚它们需要保存每轮快照，超出本 demo 的范围；回退只保证
   * 轮次、策略选择、战报记录与会场发言回到目标轮。
   */
  rewindTo(round) {
    if (this.state.ended) return false;
    const target = Math.max(1, Math.min(round, this.state.maxRounds));
    this.state.round = target;
    this.state.selectedIds = [];
    this.state.error = null;
    this.state.log = this.state.log.filter(item => item.round <= target);
    this.state.speeches = this.state.speeches.filter(item => (item.round || 1) <= target);
    return true;
  }

  markEventRead() {
    this.state.eventRead = true;
  }

  end(reason = null) {
    this.state.ended = true;
    if (reason) this.state.endReason = reason;
  }

  /** 自动推演：只记录控制状态与日志，不绕过 lockRound / ROUND_LOCKED / 幂等。 */
  startAutoPlay(mode = 'continuous') {
    const auto = this.state.autoPlay;
    auto.active = true;
    auto.mode = mode === 'step' ? 'step' : 'continuous';
    auto.pendingRound = null;
    auto.startedAtRound = this.state.round;
    auto.lastError = null;
    if (auto.mode === 'continuous') auto.steps = [];
  }

  pauseAutoPlay(reason = 'paused') {
    if (!this.state.autoPlay.active) return;
    this.state.autoPlay.active = false;
    this.state.autoPlay.pendingRound = null;
    this.state.autoPlay.lastError = reason;
    this.recordAutoPlayStep({
      round: this.state.round,
      label: '暂停',
      version: this.state.version,
      clausesVersion: this.state.clausesVersion,
      at: Date.now(),
      status: 'paused',
      reason
    });
  }

  stopAutoPlay(reason = 'user') {
    if (!this.state.autoPlay.active) return;
    this.state.autoPlay.active = false;
    this.state.autoPlay.pendingRound = null;
    this.state.autoPlay.lastError = reason;
    this.recordAutoPlayStep({
      round: this.state.round,
      label: '停止',
      version: this.state.version,
      clausesVersion: this.state.clausesVersion,
      at: Date.now(),
      status: 'stopped',
      reason
    });
  }

  setAutoPlaySpeed(speed) {
    const value = Number(speed);
    if ([1, 1.5, 2].includes(value)) this.state.autoPlay.speed = value;
  }

  recordAutoPlayStep(step) {
    this.state.autoPlay.steps.push({
      round: step.round,
      label: step.label,
      version: step.version,
      clausesVersion: step.clausesVersion,
      at: step.at,
      status: step.status || 'ok',
      reason: step.reason || null
    });
    if (this.state.autoPlay.steps.length > 80) this.state.autoPlay.steps.shift();
  }

  clearAutoPlaySteps() {
    this.state.autoPlay.steps = [];
  }

  markAutoPlayPending(round) {
    this.state.autoPlay.pendingRound = round == null ? null : round;
  }

  reset() {
    this.state = createInitialNegotiation();
  }
}
