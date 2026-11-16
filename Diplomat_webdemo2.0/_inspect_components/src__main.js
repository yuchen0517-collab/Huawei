import { initialSpeeches, topic } from './domain/negotiation.js';
import { NegotiationStore } from './stores/NegotiationStore.js';
import {
  ChannelContent,
  DialogueMessages,
  EventContent,
  MetricList,
  ModalController,
  NegotiationApp,
  OpponentIntelContent,
  ReportContent,
  Speech,
  StrategyCards,
  HandFooterContent,
  ToastController,
  TreeContent,
  escapeHTML,
  formatRound
} from './components/index.js';
import { strategyCatalog } from './domain/negotiation.js';

const $ = (selector, root = document) => root.querySelector(selector);
const store = new NegotiationStore();
let replyTimer = null;

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  $('meta[name="theme-color"]').content = theme === 'light' ? '#f7efdf' : '#080604';
  try { localStorage.setItem('diplomat-theme', theme); } catch (_) {}
}

try {
  const savedTheme = localStorage.getItem('diplomat-theme');
  if (savedTheme === 'light' || savedTheme === 'dark') setTheme(savedTheme);
} catch (_) {}

$('#app').innerHTML = NegotiationApp({
  state: store.state,
  usedActionPoints: store.usedActionPoints,
  canEndTurn: store.canEndTurn
});

const modal = new ModalController($('#modalOverlay'));
const toast = new ToastController($('#toast'));

function renderStrategy() {
  $('#strategyCards').innerHTML = StrategyCards({
    strategies: strategyCatalog,
    selectedIds: store.state.selectedIds
  });
  $('#handFooter').innerHTML = HandFooterContent({
    used: store.usedActionPoints,
    total: store.state.actionPoints,
    canEndTurn: store.canEndTurn
  });
}

function renderRound() {
  $('#roundNumber').textContent = formatRound(Math.min(store.state.round, store.state.maxRounds));
}

function renderMetrics() {
  $('#metricList').innerHTML = MetricList({ metrics: store.state.metrics });
}

function appendSpeech(speech) {
  const dialogue = $('#dialogueScroll');
  dialogue.insertAdjacentHTML('beforeend', Speech(speech));
  dialogue.scrollTo({ top: dialogue.scrollHeight, behavior: 'smooth' });
}

function openReport() {
  modal.open({
    title: '谈判战报',
    kicker: 'NEGOTIATION INTELLIGENCE',
    content: ReportContent({ topic, state: store.state })
  });
}

function resetNegotiation() {
  clearTimeout(replyTimer);
  store.reset();
  renderRound();
  renderStrategy();
  renderMetrics();
  $('#dialogueScroll').innerHTML = DialogueMessages({ speeches: initialSpeeches });
  $('#eventCount').textContent = '1';
  modal.close();
  toast.show('已重置为第 1 轮，策略与态势均已恢复。');
}

function endNegotiation() {
  store.end();
  clearTimeout(replyTimer);
  renderStrategy();
  const { round, maxRounds, metrics } = store.state;
  modal.open({
    title: '谈判已结束',
    kicker: 'SESSION CLOSED',
    content: `<p>本场谈判在第 <strong>${Math.min(round, maxRounds)} 轮</strong>结束。最终主体利益为 <strong>${metrics.interest}</strong>，国际形象为 <strong>${metrics.image}</strong>，盟友信任为 <strong>${metrics.trust}</strong>。</p><p>你可以查看本次战报，或重新开启一场谈判。</p>${ReportContent({ topic, state: store.state })}`,
    primary: '重新谈判',
    secondary: '查看战报',
    onPrimary: resetNegotiation,
    onSecondary: openReport
  });
}

function toggleStrategy(button) {
  const result = store.toggleStrategy(button.dataset.strategyId);
  if (!result.ok) {
    const messages = {
      ended: '本场谈判已结束，请重新谈判后再出牌。',
      points: '行动点不足，请取消一张卡牌或选择低消耗策略。',
      unknown: '未找到该策略，请刷新页面后重试。'
    };
    toast.show(messages[result.reason]);
    return;
  }
  renderStrategy();
}

function endTurn() {
  const turn = store.endTurn();
  if (!turn) return;
  appendSpeech({
    party: 'cn',
    text: turn.text,
    label: `ROUND ${formatRound(turn.round)} · 策略出牌`
  });
  renderStrategy();
  renderRound();
  renderMetrics();
  toast.show(`第 ${turn.round} 轮策略已提交，等待对方回应。`);
  clearTimeout(replyTimer);
  replyTimer = setTimeout(() => {
    if (store.state.ended) return;
    appendSpeech({
      party: 'us',
      text: '我们注意到贵方方案中的交换条件。程序性保障可以作为下一步磋商基础，但公共算力配额与安全审查仍需同步形成文本。',
      label: `ROUND ${formatRound(turn.round)} · 对方回应`
    });
    store.recordOpponentReply(turn.round);
  }, 650);
}

const actions = {
  'toggle-strategy': toggleStrategy,
  'end-turn': endTurn,
  'show-report': openReport,
  'toggle-theme': () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'),
  restart: () => modal.open({
    title: '重新开启谈判？',
    kicker: 'CONFIRM RESTART',
    content: '<p>当前轮次、已选策略和战报记录将被重置，此操作无法撤销。</p>',
    primary: '确认重新谈判',
    secondary: '保留当前进度',
    onPrimary: resetNegotiation
  }),
  'end-negotiation': () => modal.open({
    title: '结束本场谈判？',
    kicker: 'CONFIRM CLOSE',
    content: '<p>结束后将生成本场战报，当前会场不再接受新的策略出牌。</p>',
    primary: '确认结束',
    secondary: '继续谈判',
    onPrimary: endNegotiation
  }),
  back: () => modal.open({
    title: '返回谈判大厅？',
    kicker: 'LEAVE SESSION',
    content: '<p>这是单页界面演示，没有独立的大厅页面。你可以留在当前会场，或重置本场谈判。</p>',
    primary: '留在会场',
    secondary: '重置谈判',
    onSecondary: resetNegotiation
  }),
  'show-event': () => {
    store.markEventRead();
    $('#eventCount').textContent = '0';
    modal.open({
      title: '科技巨头联合游说',
      kicker: `FLASH EVENT · ROUND ${formatRound(Math.min(store.state.round, store.state.maxRounds))}`,
      content: EventContent({ topic }),
      primary: '记录事件并返回'
    });
  },
  'show-tree': () => modal.open({
    title: '谈判树',
    kicker: 'NEGOTIATION PATH',
    content: TreeContent({ log: store.state.log })
  }),
  'show-opponent': () => modal.open({
    title: '对方态势研判',
    kicker: 'INTELLIGENCE ESTIMATE',
    content: OpponentIntelContent()
  }),
  'show-channel': () => modal.open({
    title: '非正式沟通',
    kicker: 'INFORMAL CONSULTATION',
    content: ChannelContent(),
    primary: '记录意向',
    secondary: '返回公开会场',
    onPrimary: () => {
      store.recordPrivateIntent();
      modal.close();
      toast.show('非正式意向已记入战报。');
    }
  }),
  'collapse-strategy': () => $('#workspace').classList.add('strategy-collapsed'),
  'reopen-strategy': () => $('#workspace').classList.remove('strategy-collapsed'),
  'collapse-situation': () => $('#workspace').classList.add('situation-collapsed'),
  'reopen-situation': () => $('#workspace').classList.remove('situation-collapsed'),
  'close-modal': () => modal.close()
};

document.addEventListener('click', event => {
  const button = event.target.closest('[data-action]');
  if (!button) return;
  const handler = actions[button.dataset.action];
  if (handler) handler(button, event);
});

$('#modalOverlay').addEventListener('click', event => {
  if (event.target === modal.root) modal.close();
});

document.addEventListener('keydown', event => modal.handleKeyboard(event));
