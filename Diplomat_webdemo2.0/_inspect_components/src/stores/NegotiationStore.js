import { createInitialNegotiation, strategyCatalog } from '../domain/negotiation.js';

/** UI-independent negotiation state and rules. All methods are synchronous. */
export class NegotiationStore {
  constructor() {
    this.state = createInitialNegotiation();
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
    return this.selectedStrategies.length > 0 && !this.state.ended && this.state.round <= this.state.maxRounds;
  }

  toggleStrategy(id) {
    if (this.state.ended) return { ok: false, reason: 'ended' };
    const strategy = this.strategyMap.get(id);
    if (!strategy) return { ok: false, reason: 'unknown' };
    if (this.state.selectedIds.includes(id)) {
      this.state.selectedIds = this.state.selectedIds.filter(selectedId => selectedId !== id);
      return { ok: true, selected: false };
    }
    if (this.usedActionPoints + strategy.cost > this.state.actionPoints) return { ok: false, reason: 'points' };
    this.state.selectedIds = [...this.state.selectedIds, id];
    return { ok: true, selected: true };
  }

  endTurn() {
    if (!this.canEndTurn) return null;
    const round = this.state.round;
    const selected = this.selectedStrategies;
    const names = selected.map(strategy => strategy.name);
    const used = this.usedActionPoints;
    const selectedIds = new Set(this.state.selectedIds);

    if (selectedIds.has('bundle') || selectedIds.has('package')) this.state.metrics.interest = Math.min(100, this.state.metrics.interest + 3);
    if (selectedIds.has('initiative')) this.state.metrics.image = Math.min(100, this.state.metrics.image + 2);
    if (selectedIds.has('concession') || selectedIds.has('clarify')) this.state.metrics.trust = Math.min(100, this.state.metrics.trust + 1);

    this.state.log.push({ round, text: `我方使用${names.join('、')}，消耗 ${used} 点行动点。` });
    this.state.selectedIds = [];
    this.state.round += 1;

    return {
      round,
      names,
      used,
      text: `我方本轮采取「${names.join('」「')}」策略。所有安排均以对等、透明和可核查为前提，期待贵方给出相应承诺。`
    };
  }

  recordOpponentReply(round) {
    this.state.log.push({ round, text: '美方接受继续讨论程序性保障，要求同步处理配额与审查文本。' });
  }

  recordPrivateIntent() {
    this.state.log.push({ round: Math.min(this.state.round, this.state.maxRounds), text: '通过非正式渠道确认：对方愿意讨论审查期限与年度复核。' });
  }

  markEventRead() {
    this.state.eventRead = true;
  }

  end() {
    this.state.ended = true;
  }

  reset() {
    this.state = createInitialNegotiation();
  }
}
