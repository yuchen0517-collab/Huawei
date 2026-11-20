import { topic } from './domain/negotiation.js';
import { NegotiationStore } from './stores/NegotiationStore.js';
import {
  DialogueMessages,
  MetricList,
  ModalController,
  NegotiationApp,
  RelationMatrix,
  ReportContent,

  Speech,
  StrategyCards,
  HandFooterContent,
  StatusStrip,
  ClauseBoard,
  AutoPlayPanel,
  ActionBar,
  DebriefPage,
  ToastController,
  TreeContent,
  TreeDrawerHeader,
  escapeHTML,
  formatRound
} from './components/index.js';
import { EventCardController } from './components/cards/index.js';
import './components/cards/event-card.css';
import { strategyCatalog } from './domain/negotiation.js';
import { CoachPanel } from './components/CoachPanel.js';
import { ErrorBanner } from './components/ErrorBanner.js';
import { submitAction, injectError, adapterId } from './services/adapter.js';
import { actionIdFor, peekActionId, consumeActionId } from './services/idempotency.js';
import { fetchCoach, sanitizeCoach, setCoachMode, getCoachMode, coachRequestCount } from './services/coach.js';
import { ENDGAME_COPY, buildReportSummary } from './domain/endgame.js';
import { buildDebrief } from './domain/debrief.js';

const $ = (selector, root = document) => root.querySelector(selector);
const store = new NegotiationStore();
let replyTimer = null;
let matrixDim = 'affinity';
let treeTrigger = null;
let submitting = false;
let busyLeft = 0;
let busyTimer = null;
let autoPlayTimer = null;
let autoPlayRaf = null;

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
  canEndTurn: store.canEndTurn,
  baseActions: store.baseActions
});

const modal = new ModalController($('#modalOverlay'));
const toast = new ToastController($('#toast'));
const eventCard = new EventCardController();
const appShell = $('.app-shell');
const workspace = $('#workspace');
const fabPositionKey = 'diplomat-fab-pos';
renderAutoPlay();

function setPanelA11y(side, expanded) {
  const panel = side === 'strategy' ? $('#strategyPanel') : $('#situationPanel');
  const collapse = panel?.querySelector('.collapse-button');
  if (collapse) collapse.setAttribute('aria-expanded', String(expanded));
  const rail = side === 'strategy' ? $('.reopen-left') : $('.reopen-right');
  if (rail) rail.setAttribute('aria-expanded', String(expanded));
}

function closePanelFocus(restore = true) {
  if (!appShell?.classList.contains('focus-strategy') && !appShell?.classList.contains('focus-situation')) return;
  appShell.classList.remove('focus-strategy', 'focus-situation');
  document.querySelectorAll('.side-panel').forEach(panel => panel.classList.remove('is-panel-focused'));
  if (restore) $('.main-stage')?.focus({ preventScroll: true });
}

function focusPanel(side) {
  const panel = side === 'strategy' ? $('#strategyPanel') : $('#situationPanel');
  if (!panel) return;
  closePanelFocus(false);
  appShell.classList.add(`focus-${side}`);

  document.querySelectorAll('.side-panel').forEach(item => item.classList.toggle('is-panel-focused', item === panel));
  panel.focus({ preventScroll: true });
}

function collapsePanel(side) {
  closePanelFocus(false);
  workspace?.classList.add(`${side}-collapsed`);
  setPanelA11y(side, false);
  const rail = side === 'strategy' ? $('.reopen-left') : $('.reopen-right');
  rail?.focus({ preventScroll: true });
}

function reopenPanel(side) {
  workspace?.classList.remove(`${side}-collapsed`);
  setPanelA11y(side, true);
  requestAnimationFrame(() => focusPanel(side));
}

function initPanelMode() {
  const mobile = window.matchMedia('(max-width: 900px)');
  const sync = () => {
    if (!mobile.matches) return;
    workspace?.classList.remove('strategy-collapsed', 'situation-collapsed');
    setPanelA11y('strategy', true);
    setPanelA11y('situation', true);
    closePanelFocus(false);
  };
  if (typeof mobile.addEventListener === 'function') mobile.addEventListener('change', sync);
  else if (typeof mobile.addListener === 'function') mobile.addListener(sync);
  sync();
}

function initReportFab() {
  const fab = $('.report-fab');
  if (!fab) return;

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  const burstParticles = () => {
    if (reduceMotion.matches) return;
    const count = 10 + Math.floor(Math.random() * 5);
    for (let index = 0; index < count; index += 1) {
      const angle = Math.random() * Math.PI * 2;
      const radius = 26 + Math.random() * 22;
      const particle = document.createElement('span');
      particle.className = 'fab-particle';
      particle.style.setProperty('--tx', `${Math.cos(angle) * radius}px`);
      particle.style.setProperty('--ty', `${Math.sin(angle) * radius}px`);
      particle.style.setProperty('--d', `${320 + Math.random() * 200}ms`);
      particle.addEventListener('animationend', () => particle.remove(), { once: true });
      setTimeout(() => particle.remove(), 900);
      fab.append(particle);
    }
  };

  const pressBall = () => {
    if (reduceMotion.matches) return;
    fab.classList.add('pressed');
    setTimeout(() => fab.classList.remove('pressed'), 110);
  };

  const clamp = () => {
    if (fab.style.left === '' && fab.style.top === '') return;
    const rect = fab.getBoundingClientRect();
    const maxX = Math.max(0, window.innerWidth - rect.width);
    const maxY = Math.max(0, window.innerHeight - rect.height);
    const x = Math.min(Math.max(0, Number.parseFloat(fab.style.left) || rect.left), maxX);
    const y = Math.min(Math.max(0, Number.parseFloat(fab.style.top) || rect.top), maxY);
    fab.style.left = `${x}px`;
    fab.style.top = `${y}px`;
    fab.style.right = 'auto';
    fab.style.bottom = 'auto';
  };

  let customPosition = false;
  try {
    const saved = JSON.parse(localStorage.getItem(fabPositionKey) || 'null');
    if (saved && Number.isFinite(saved.x) && Number.isFinite(saved.y)) {
      customPosition = true;
      fab.style.left = `${saved.x}px`;
      fab.style.top = `${saved.y}px`;
      fab.style.right = 'auto';
      fab.style.bottom = 'auto';
    }
  } catch (_) {}

  const place = () => {
    if (customPosition) {
      clamp();
      return;
    }
    if (window.matchMedia('(max-width: 900px)').matches) {
      fab.style.left = '';
      fab.style.top = '';
      fab.style.right = '';
      fab.style.bottom = '';
      return;
    }
    const stage = $('.main-stage');
    if (!stage) return;
    const stageRect = stage.getBoundingClientRect();
    const fabRect = fab.getBoundingClientRect();
    const x = Math.min(Math.max(0, stageRect.right - fabRect.width - 24), Math.max(0, window.innerWidth - fabRect.width));
    const y = Math.min(Math.max(0, stageRect.bottom - fabRect.height - 24), Math.max(0, window.innerHeight - fabRect.height));
    fab.style.left = `${x}px`;
    fab.style.top = `${y}px`;
    fab.style.right = 'auto';
    fab.style.bottom = 'auto';
  };
  place();

  let pointerId = null;
  let startX = 0;
  let startY = 0;
  let originX = 0;
  let originY = 0;
  let moved = false;
  let suppressClick = false;

  fab.addEventListener('pointerdown', event => {
    if (event.pointerType === 'mouse' && event.button !== 0) return;
    event.preventDefault();
    fab.classList.add('dragging');

    const rect = fab.getBoundingClientRect();
    originX = rect.left;
    originY = rect.top;
    startX = event.clientX;
    startY = event.clientY;
    moved = false;
    pointerId = event.pointerId;
    fab.style.left = `${rect.left}px`;
    fab.style.top = `${rect.top}px`;
    fab.style.right = 'auto';
    fab.style.bottom = 'auto';

    try { fab.setPointerCapture(pointerId); } catch (_) {}
  });

  fab.addEventListener('pointermove', event => {
    if (event.pointerId !== pointerId) return;
    const dx = event.clientX - startX;
    const dy = event.clientY - startY;
    if (!moved && Math.hypot(dx, dy) >= 5) {
      moved = true;
      customPosition = true;
    }
    if (!moved) return;
    const rect = fab.getBoundingClientRect();
    const maxX = Math.max(0, window.innerWidth - rect.width);
    const maxY = Math.max(0, window.innerHeight - rect.height);
    fab.style.left = `${Math.min(Math.max(0, originX + dx), maxX)}px`;
    fab.style.top = `${Math.min(Math.max(0, originY + dy), maxY)}px`;
  });

  const finish = event => {
    if (event.pointerId !== pointerId) return;
    try { fab.releasePointerCapture(pointerId); } catch (_) {}
    pointerId = null;
    fab.classList.remove('dragging');
    if (moved) {
      suppressClick = true;
      clamp();
      try {
        const rect = fab.getBoundingClientRect();
        localStorage.setItem(fabPositionKey, JSON.stringify({ x: Math.round(rect.left), y: Math.round(rect.top) }));
      } catch (_) {}
      setTimeout(() => { suppressClick = false; }, 350);
    } else {
      suppressClick = true;
      setTimeout(() => { suppressClick = false; }, 350);
      pressBall();
      burstParticles();
      openReport();
    }
  };

  fab.addEventListener('pointerup', finish);
  fab.addEventListener('pointercancel', event => {
    if (event.pointerId !== pointerId) return;
    pointerId = null;
    fab.classList.remove('dragging');
    suppressClick = false;
  });
  fab.addEventListener('click', event => {
    if (!suppressClick) return;
    event.preventDefault();
    event.stopPropagation();
    suppressClick = false;
  }, true);

  window.addEventListener('resize', place);
  window.addEventListener('orientationchange', place);
}

function renderAutoPlay() {
  const host = $('#autoPlaySlot');
  if (!host) return;
  const logWasOpen = Boolean(host.querySelector('.autoplay-log')?.open);
  host.innerHTML = AutoPlayPanel({
    autoPlay: store.state.autoPlay,
    round: store.state.round,
    ended: store.state.ended,
    phase: store.state.phase
  });
  if (logWasOpen) {
    const log = host.querySelector('.autoplay-log');
    if (log) log.open = true;
  }
}

function clearAutoPlayTimers() {
  if (autoPlayTimer) { clearTimeout(autoPlayTimer); autoPlayTimer = null; }
  if (autoPlayRaf) { cancelAnimationFrame(autoPlayRaf); autoPlayRaf = null; }
}

function stopAutoPlayFor(reason) {
  clearAutoPlayTimers();
  if (!store.state.autoPlay.active) return;
  store.stopAutoPlay(reason);
  renderAutoPlay();
  renderStrategy();
}

function pauseAutoPlayForHuman() {
  if (!store.state.autoPlay.active) return;
  clearAutoPlayTimers();
  store.pauseAutoPlay('paused');
  toast.show('自动推演已暂停，人工接管');
  renderAutoPlay();
  renderStrategy();
}

function startAutoPlayRun(mode) {
  if (store.state.ended) return;
  if (replyTimer) { toast.show('等待对方回应后再继续'); return; }
  clearAutoPlayTimers();
  store.startAutoPlay(mode);
  renderAutoPlay();
  renderStrategy();
  autoPlayNext();
}

function pauseAutoPlayByUser() {
  if (!store.state.autoPlay.active) return;
  clearAutoPlayTimers();
  store.pauseAutoPlay('paused');
  renderAutoPlay();
  renderStrategy();
}

function stopAutoPlayByUser() {
  clearAutoPlayTimers();
  store.stopAutoPlay('user');
  renderAutoPlay();
  renderStrategy();
}

function autoPlayNext() {
  const auto = store.state.autoPlay;
  if (!auto.active || store.state.ended || submitting || replyTimer) return;
  if (store.state.roundLocked) { stopAutoPlayFor('round_locked'); return; }
  if (store.state.error) { stopAutoPlayFor('error'); return; }
  const judged = store.judge;
  if (judged) { stopAutoPlayFor(judged.reason); renderEndgame(judged.reason); return; }
  const hasIntent = store.state.selectedIds.length > 0
    || store.state.baseAction.kind !== 'none'
    || Object.keys(store.state.stanceDrafts || {}).length > 0;
  if (!hasIntent) {
    const result = store.chooseBaseAction('hold');
    if (!result.ok) { stopAutoPlayFor(result.reason || 'no_intent'); return; }
  }
  submitTurn({ fromAutoPlay: true });
}

function scheduleAutoPlayNext() {
  clearAutoPlayTimers();
  const auto = store.state.autoPlay;
  if (!auto.active) return;
  if (auto.mode === 'step') {
    store.pauseAutoPlay('step');
    renderAutoPlay();
    renderStrategy();
    return;
  }
  const delay = 400 / (auto.speed || 1);
  autoPlayRaf = requestAnimationFrame(() => {
    autoPlayTimer = setTimeout(() => autoPlayNext(), delay);
  });
}

function checkAutoPlayVersionConsistency() {
  const state = store.state;
  const windowState = state.responseWindow;
  if (windowState.open && Number(windowState.version) !== Number(state.version)) {
    return { ok: false, reason: 'window_version' };
  }
  const nodes = document.querySelectorAll('[data-version], .version-chip, #bdVer, #drVer');
  if (nodes.length > 0) {
    const mismatched = Array.from(nodes).some(node => {
      const text = (node.textContent || '').trim();
      return text !== '' && !text.includes(`v${state.version}`);
    });
    if (mismatched) return { ok: false, reason: 'display_version' };
  }
  return { ok: true };
}

function onRoundSettled(round, payload) {
  const auto = store.state.autoPlay;
  if (!auto.active) return;
  if (store.state.round <= round) return;
  if (store.state.ended) { stopAutoPlayFor('ended'); return; }
  if (store.state.roundLocked) { stopAutoPlayFor('round_locked'); return; }
  if (store.state.error) { stopAutoPlayFor('error'); return; }
  const judged = store.judge;
  if (judged) { stopAutoPlayFor(judged.reason); renderEndgame(judged.reason); return; }
  const versionCheck = checkAutoPlayVersionConsistency();
  if (!versionCheck.ok) { stopAutoPlayFor('version_conflict'); return; }
  store.markAutoPlayPending(null);
  store.recordAutoPlayStep({
    round,
    label: payload && payload.label ? payload.label : '自动推进',
    version: store.state.version,
    clausesVersion: store.state.clausesVersion,
    at: Date.now(),
    status: 'ok'
  });
  renderAutoPlay();
  scheduleAutoPlayNext();
}

function renderStatusStrip() {
  const host = $('#statusStrip');
  if (!host) return;
  const windowState = store.state.responseWindow;
  host.innerHTML = StatusStrip({
    open: windowState.open,
    version: windowState.version,
    remaining: Math.max(0, windowState.deadlineRound - store.state.round),
    transitionUsed: windowState.transitionUsed
  });
}

/** 只重画底部手牌行：高度恒定，选卡不会把行动点顶上去。 */
function updateHandFooter(anim = null) {
  const host = $('#handFooter');
  if (!host) return;
  const state = store.state;
  host.innerHTML = HandFooterContent({
    used: store.usedActionPoints,
    total: state.actionPoints,
    canEndTurn: store.canEndTurn,
    anim,
    phase: state.phase,
    draftCount: state.selectedIds.length
  });
}

/** 报价板弹窗开着且停在签署板上时，把条款表重画一遍（状态/计数随时同步）。 */
function refreshReportBoard() {
  const host = $('#modalContent')?.querySelector('#reportBoard');
  if (!host) return;
  const hadFocus = host.contains(document.activeElement);
  const summary = store.clausesSummary;
  host.innerHTML = ClauseBoard({
    clauses: store.state.clauses,
    drafts: store.state.stanceDrafts,
    draftCount: Object.keys(store.state.stanceDrafts || {}).length,
    pendingCount: summary.pending + summary.open,
    submitting: store.state.phase === 'loading'
  });
  // 重画会把焦点丢到 body：交回弹窗自己的关闭按钮，Esc/Tab 仍可用
  if (hadFocus) $('#modalOverlay [data-action="close-modal"]')?.focus({ preventScroll: true });
}

/** 签署选择器改了就只更新计数与提交按钮，不重画表格，焦点留在原地。 */
function updateDraftFoot() {
  const stat = $('#modalContent .cb-foot-stat');
  if (!stat) return;
  const summary = store.clausesSummary;
  stat.textContent = `已修订 ${Object.keys(store.state.stanceDrafts || {}).length} 条 · 未决 ${summary.pending + summary.open} 条`;
}

function renderActionBar() {
  const host = $('#actionBar');
  if (!host) return;
  host.innerHTML = ActionBar({ actions: store.baseActions });
}

function renderStrategy(anim = null) {
  const state = store.state;
  renderStatusStrip();
  renderAutoPlay();
  renderActionBar();
  if ($('#strategyCards')) $('#strategyCards').classList.toggle('is-readonly', state.ended);
  if ($('#coachSlot')) $('#coachSlot').classList.toggle('is-readonly', state.ended);
  $('#strategyCards').innerHTML = StrategyCards({
    strategies: strategyCatalog,
    selectedIds: state.selectedIds
  });
  updateHandFooter(anim);
  refreshReportBoard();
}

function renderError() {
  const slot = $('#errorSlot');
  if (!slot) return;
  slot.innerHTML = ErrorBanner({
    error: store.state.error,
    actionId: peekActionId(),
    draftCount: store.state.selectedIds.length,
    busyLabel: busyLeft > 0 ? `立即重试（${busyLeft}）` : ''
  });
}

function renderCoach() {
  const slot = $('#coachSlot');
  if (!slot) return;
  slot.innerHTML = CoachPanel({
    coach: store.state.coach,
    status: store.state.coachStatus,
    collapsed: store.state.coachCollapsed,
    version: store.state.version
  });
}

function withTimeout(promise, ms) {
  return Promise.race([
    promise,
    new Promise((_, reject) => setTimeout(() => reject(new Error('coach-timeout')), ms))
  ]);
}

// 教练：fire-and-forget，绝不进入提交链路的 await；不阻塞、不改事实状态
let coachSeq = 0;
async function requestCoach() {
  const seq = ++coachSeq;
  store.patchCoach({ coachStatus: 'pending' });
  renderCoach();

  let attempts = 0;
  const run = async () => {
    attempts += 1;
    let res = { ok: false };
    try {
      res = await withTimeout(fetchCoach(store.state), 8000);
    } catch (_) {
      res = { ok: false };
    }
    if (seq !== coachSeq) return; // 已有更新的一轮请求，丢弃旧结果
    if (!res.ok) {
      if (attempts < 2) {
        setTimeout(run, 1500);
        return;
      }
      store.patchCoach({
        coach: { status: 'failed', items: [], fail_reason: '模型暂不可用，请稍后重试' },
        coachStatus: 'failed'
      });
      renderCoach();
      return;
    }
    const safe = sanitizeCoach(res.coach, store.state);
    store.patchCoach({ coach: safe, coachStatus: (safe && safe.status) || 'ready' });
    renderCoach();
  };
  run();
}

/** 协议版本号三处同源，全部读 store.state.version（#mVer 顶栏 / #bdVer 报价板 / #drVer 抽屉）。 */
function renderVersion() {
  const text = `v${store.state.version}`;
  ['#mVer', '#bdVer', '#drVer'].forEach(id => {
    const node = $(id);
    if (node) node.textContent = text;
  });
}

function renderRound() {
  $('#roundNumber').textContent = formatRound(Math.min(store.state.round, store.state.maxRounds));
  renderVersion();
}

/** 录制前探针：报价板打开、抽屉存在时三处徽标应同源。 */
function versionBadges() {
  const nodes = ['#mVer', '#bdVer', '#drVer'].map(id => $(id)).filter(Boolean);
  const texts = nodes.map(node => (node.textContent || '').trim());
  const expected = `v${store.state.version}`;
  return {
    count: nodes.length,
    texts,
    expected,
    ok: nodes.length === 3 && texts.every(text => text === expected)
  };
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
  closePanelFocus(false);
  const summary = store.clausesSummary;
  modal.open({
    title: '本轮报价板',
    content: ReportContent({
      topic,
      clauses: store.state.clauses,
      drafts: store.state.stanceDrafts,
      draftCount: Object.keys(store.state.stanceDrafts || {}).length,
      pendingCount: summary.pending + summary.open,
      submitting: store.state.phase === 'loading',
      summary: buildReportSummary(store.state),
      version: store.state.version
    }),
    primary: '提交本轮修订',
    secondary: '达成协议',
    onPrimary: async () => {
      await submitTurn({ fromRevision: true });
      refreshReportBoard();
    },
    onSecondary: () => { modal.close(); toast.show('演示版：协议已达成'); }
  });
}

function renderDebrief() {
  return DebriefPage({
    debrief: buildDebrief(store.state),
    coach: store.state.coach
  });
}

function openDebrief() {
  closePanelFocus(false);
  modal.open({
    title: '终局复盘',
    kicker: 'DEBRIEF',
    content: renderDebrief(),
    primary: '查看报价板',
    secondary: '关闭',
    onPrimary: openReport
  });
}

function openTree() {
  closePanelFocus(false);
  const drawer = $('#treeDrawer');
  const backdrop = $('#drawerBackdrop');
  const treeBody = $('#treeDrawerBody');
  if (!drawer || !backdrop || !treeBody) return;
  treeTrigger = document.activeElement && document.activeElement.closest
    ? document.activeElement.closest('[data-action="show-tree"]')
    : null;
  if (!treeTrigger) treeTrigger = $('[data-action="show-tree"]');
  const header = drawer.querySelector('.drawer-header');
  if (header) header.outerHTML = TreeDrawerHeader({
    topic,
    round: Math.min(store.state.round, store.state.maxRounds),
    nodeCount: (store.state.log || []).length + 1,
    version: store.state.version
  });
  treeBody.innerHTML = TreeContent({ state: store.state, topic });
  appShell.classList.add('tree-open');
  drawer.classList.add('open');
  drawer.setAttribute('aria-hidden', 'false');
  backdrop.classList.add('open');
  drawer.querySelector('[data-action="close-tree"]')?.focus({ preventScroll: true });
}

function closeTree() {
  const drawer = $('#treeDrawer');
  const backdrop = $('#drawerBackdrop');
  if (!drawer || !drawer.classList.contains('open')) return;
  drawer.classList.remove('open');
  drawer.setAttribute('aria-hidden', 'true');
  backdrop?.classList.remove('open');
  appShell.classList.remove('tree-open');
  if (treeTrigger) treeTrigger.focus({ preventScroll: true });
  treeTrigger = null;
}

function jumpToRound(round) {
  if (!Number.isFinite(round) || round < 1) {
    toast.show('无法回到该轮次。');
    return;
  }
  clearTimeout(replyTimer);
  if (!store.rewindTo(round)) {
    toast.show('本场谈判已结束，无法回退。');
    return;
  }
  renderRound();
  renderStrategy();
  renderMetrics();
  renderError();
  renderCoach();
  const dialogue = $('#dialogueScroll');
  dialogue.innerHTML = DialogueMessages({ speeches: store.state.speeches });
  dialogue.scrollTop = dialogue.scrollHeight;
  closeTree();
  toast.show(`已回到第 ${formatRound(store.state.round)} 轮，会场对话与策略已同步。`);
}

function resetNegotiation() {
  clearTimeout(replyTimer);
  stopBusyCountdown();
  store.reset();
  renderRound();
  renderStrategy();
  renderMetrics();
  renderError();
  renderCoach();
  $('#dialogueScroll').innerHTML = DialogueMessages({ speeches: store.state.speeches });
  $('#eventCount').textContent = '1';
  modal.close();
  toast.show('已重置为第 1 轮，策略与态势均已恢复。');
}

function endNegotiation(reason = 'withdraw') {
  clearTimeout(replyTimer);
  renderEndgame(reason);
}

/** 五种终局共用同一个 ModalController；判定与文案来自 domain/endgame.js。 */
function renderEndgame(reason) {
  const copy = ENDGAME_COPY[reason];
  if (!copy) return;
  store.end(reason);
  renderStrategy();
  const state = store.state;
  const judgement = store.judge || { reason, title: copy.title, summary: copy.summary, metricsHint: '' };
  modal.open({
    title: copy.title,
    kicker: copy.kicker,
    content: `<div class="endgame-tone ${copy.tone}"></div><p>${escapeHTML(judgement.summary || '')}</p><p class="endgame-hint">${escapeHTML(judgement.metricsHint || '')}</p>`,
    primary: '查看复盘',
    secondary: '重新谈判',
    onPrimary: openDebrief,
    onSecondary: resetNegotiation
  });
}

function useResponseTransition() {
  const result = store.useTransition();
  if (!result.ok) return;
  renderStatusStrip();
  toast.show('已使用过渡，表态窗口延长 1 轮。');
}

function pickBaseAction(kind) {
  pauseAutoPlayForHuman();
  if (kind === 'exit') { requestExit(); return; }
  const result = store.chooseBaseAction(kind);
  if (!result.ok) {
    const messages = {
      ended: '本场谈判已结束。',
      locked: '本轮已锁定，无法再选择基础行动。',
      loading: '本轮提交中，请稍候。',
      used: '本场已使用最后报价。',
      accept: '当前没有可接受的条款。',
      unknown: '未知的基础行动。'
    };
    toast.show(messages[result.reason] || '当前无法使用该基础行动。');
    return;
  }
  if (result.clearedCards) toast.show('已切换为基础行动，卡牌选择已清空');
  renderStrategy();
}

function requestExit() {
  modal.open({
    title: '确认退出谈判？',
    kicker: 'WITHDRAW',
    content: '<p>退出会记为「主动退出」，不是谈判失败。本场将结束并生成战报，当前会场不再接受新的出牌。</p>',
    primary: '确认退出',
    secondary: '继续谈判',
    primaryAction: 'confirm-exit'
  });
}

function confirmExit() {
  const result = store.chooseBaseAction('exit');
  if (!result.ok) {
    toast.show(result.reason === 'loading' ? '本轮提交中，请稍候。' : '当前无法退出谈判。');
    return;
  }
  renderStrategy();
  submitTurn();
}

function toggleStrategy(button) {
  pauseAutoPlayForHuman();
  const before = store.state.actionPoints - store.usedActionPoints;
  const result = store.toggleStrategy(button.dataset.strategyId);
  if (!result.ok) {
    const messages = {
      ended: '本场谈判已结束，请重新谈判后再出牌。',
      points: '行动点不足，请取消一张卡牌或选择低消耗策略。',
      unknown: '未找到该策略，请刷新页面后重试。'
    };
    toast.show(messages[result.reason]);
    if (result.reason === 'points') {
      const points = $('#handFooter .action-points');
      if (points) {
        points.classList.remove('shake');
        void points.offsetWidth;
        points.classList.add('shake');
        points.addEventListener('animationend', () => points.classList.remove('shake'), { once: true });
      }
    }
    return;
  }
  const after = store.state.actionPoints - store.usedActionPoints;
  const anim = after === before ? null : { kind: after < before ? 'spend' : 'restore', from: before, to: after };
  renderStrategy(anim);
  if (result.clearedBaseAction) toast.show('已切换为策略卡，基础行动已清除');
}

// 提交意图的指纹：选卡一变，action_id 就作废重生成（幂等规则）
function selectionSignature() {
  const drafts = Object.keys(store.state.stanceDrafts || {}).sort()
    .map(id => `${id}:${store.state.stanceDrafts[id]}`)
    .join(',');
  return [store.state.selectedIds.slice().sort().join('|'), store.state.baseAction.kind, drafts].join('#');
}

function stopBusyCountdown() {
  clearInterval(busyTimer);
  busyTimer = null;
  busyLeft = 0;
}

function startBusyCountdown(seconds) {
  stopBusyCountdown();
  busyLeft = Math.max(1, Number(seconds) || 3);
  busyTimer = setInterval(() => {
    busyLeft -= 1;
    if (busyLeft <= 0) {
      stopBusyCountdown();
      submitTurn();
      return;
    }
    renderError();
  }, 1000);
}

async function submitTurn(options = {}) {
  if (submitting) return;

  // 规则引擎降级：模型不可用时由程序给一个合法的基础行动，不伪造模型输出
  if (options.fallback) {
    store.clearError();
    const base = strategyCatalog.find(item => item.recommended) || strategyCatalog[0];
    store.state.selectedIds = [base.id];
    renderStrategy();
    toast.show(`已改用规则引擎基础行动：${base.name}`);
  }

  const payload = store.prepareTurn();
  if (!payload) {
    if (options.fromAutoPlay) { stopAutoPlayFor('no_intent'); return; }
    if (options.fromRevision) {
      toast.show('请先修改至少一条条款立场。');
      return;
    }
    toast.show(store.state.baseAction.kind !== 'none'
      ? '本轮提交条件尚未满足，请稍候。'
      : '请先选择策略卡或基础行动，或等待本轮提交完成。');
    return;
  }

  stopBusyCountdown();
  submitting = true;
  store.clearError();
  if (options.fromAutoPlay) {
    store.markAutoPlayPending(payload.round);
    renderAutoPlay();
  }
  store.setPhase('loading');
  renderStrategy();
  renderError();

  const actionId = actionIdFor(selectionSignature());
  const response = await submitAction({
    actionId,
    round: payload.round,
    version: payload.version,
    strategyIds: payload.strategyIds,
    baseAction: payload.baseAction,
    revisions: payload.revisions,
    names: payload.names,
    label: payload.label,
    used: payload.used,
    text: payload.text
  });

  submitting = false;
  store.setPhase('ready');

  if (!response.ok) {
    store.failSubmit(response.error);
    renderStrategy();
    renderError();
    if (response.error.error === 'ROUND_LOCKED') {
      store.lockRound();
      renderStrategy();
    }
    if (response.error.error === 'SESSION_BUSY') startBusyCountdown(response.error.retryAfter);
    if (options.fromAutoPlay) stopAutoPlayFor(response.error.error);
    return;
  }

  // 成功：先落地事实状态，再触发教练（教练不进 await）
  const turn = store.applyTurn(payload, { actionId, version: response.patch.version });
  const windowTimedOut = store.checkWindowTimeout();
  consumeActionId();
  stopBusyCountdown();

  appendSpeech({
    party: 'cn',
    text: turn.text,
    label: `ROUND ${formatRound(turn.round)} · ${payload.strategyIds.length ? '策略出牌' : '基础行动'}`
  });
  renderStrategy();
  renderRound();
  renderMetrics();
  renderError();

  if (windowTimedOut) {
    store.state.metrics.trust = Math.max(0, store.state.metrics.trust - 3);
    store.closeResponseWindow();
    appendSpeech({
      system: true,
      label: '窗口超时',
      text: `我方未在窗口内表态，对方视为沉默处理。`
    });
    renderMetrics();
    renderStrategy();
    toast.show('待表态窗口已超时，信任 -3。');
  }

  const judged = store.judge;
  if (judged) {
    if (store.state.autoPlay.active) stopAutoPlayFor(judged.reason);
    if (judged.reason === 'withdraw') toast.show('已按主动退出处理，本场谈判结束。');
    renderEndgame(judged.reason);
    return;
  }

  if (!options.fromAutoPlay) {
    toast.show(payload.revisions && payload.revisions.length > 0
      ? '本轮修订已提交'
      : `第 ${turn.round} 轮策略已提交`);
  }

  clearTimeout(replyTimer);
  replyTimer = setTimeout(() => {
    replyTimer = null;
    if (store.state.ended) return;
    const reply = store.recordOpponentReply(turn.round);
    appendSpeech(reply);
    renderStrategy();
    renderRound();
    renderMetrics();
    onRoundSettled(turn.round, payload);
  }, 650);

  requestCoach();
}

const actions = {
  'toggle-strategy': toggleStrategy,
  'open-debrief': openDebrief,
  'debrief-jump': button => {
    const round = Number(button.dataset.round);
    modal.close();
    jumpToRound(round);
  },
  'toggle-debrief-section': (button, event) => {
    event.preventDefault();
    const details = button.closest('details');
    if (details) details.open = !details.open;
  },
  'base-action': button => pickBaseAction(button.dataset.kind),
  'confirm-exit': () => confirmExit(),
  'use-transition': () => useResponseTransition(),
  'stance-change': () => {},
  'end-turn': () => { pauseAutoPlayForHuman(); submitTurn(); },
  'autoplay-start': () => startAutoPlayRun('continuous'),
  'autoplay-pause': () => pauseAutoPlayByUser(),
  'autoplay-step': () => startAutoPlayRun('step'),
  'autoplay-stop': () => stopAutoPlayByUser(),
  'autoplay-speed': button => { store.setAutoPlaySpeed(Number(button.dataset.speed)); renderAutoPlay(); },
  'toggle-autoplay-log': (button, event) => {
    event.preventDefault();
    const details = button.closest('details');
    if (details) details.open = !details.open;
  },
  'toggle-coach': () => { store.toggleCoach(); renderCoach(); },
  'retry-coach': () => requestCoach(),
  'retry-turn': () => submitTurn(),
  'dismiss-error': () => {
    stopBusyCountdown();
    store.clearError();
    renderError();
    renderStrategy();
  },
  'rebase-version': () => {
    const serverVersion = store.state.error && store.state.error.serverVersion;
    store.rebaseVersion(serverVersion);
    renderError();
    toast.show(`已重新提交，选卡保留`);
    submitTurn();
  },
  'fallback-turn': () => submitTurn({ fallback: true }),
  'locate-selection': () => {
    const cards = $('#strategyCards');
    if (!cards) return;
    cards.scrollIntoView({ block: 'center', behavior: 'smooth' });
    cards.classList.remove('flash');
    void cards.offsetWidth;
    cards.classList.add('flash');
    cards.addEventListener('animationend', () => cards.classList.remove('flash'), { once: true });
  },
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
    eventCard.show({
      id: 'G01', kind: 'diplomacy', round: Math.min(store.state.round, store.state.maxRounds),
      title: '科技巨头联合游说',
      text: '多家科技企业呼吁建立"可互认"的安全审查机制，并反对将公共算力配额设为强制义务。会场对审查条款的关注显著上升。',
      impacts: [{ keys: ['cn', 'us'], label: '中美双方', role: '当事方', count: 2, deltas: { image: 1, trust: 1 } }]
    });
  },
  'show-tree': () => openTree(),
  'close-tree': () => closeTree(),
  'jump-round': button => jumpToRound(Number.parseInt(button.dataset.round, 10)),
  'matrix-dim': button => {
    matrixDim = button.dataset.dim || 'affinity';
    const target = $('#relationMatrix');
    if (target) target.innerHTML = RelationMatrix({ dim: matrixDim });
  },
  'collapse-strategy': () => collapsePanel('strategy'),
  'reopen-strategy': () => reopenPanel('strategy'),
  'collapse-situation': () => collapsePanel('situation'),
  'reopen-situation': () => reopenPanel('situation'),

  'close-modal': () => modal.close()
};

document.addEventListener('click', event => {
  const button = event.target.closest('[data-action]');
  if (!button) return;
  const handler = actions[button.dataset.action];
  if (handler) handler(button, event);
});

document.addEventListener('change', event => {
  const stance = event.target.closest('.cb-select');
  if (stance) pauseAutoPlayForHuman();
  if (stance) {
    store.setStanceDraft(stance.dataset.clauseId, stance.value);
    stance.classList.toggle('changed', stance.value !== 'hold');
    if (stance.value === 'accept') {
      const summary = store.clausesSummary;
      const unresolved = summary.pending + summary.open;
      if (unresolved > 0) toast.show(`仍有 ${unresolved} 条未决，接受将形成部分协议`);
    }
    updateHandFooter();
    updateDraftFoot();
    return;
  }
  const select = event.target.closest('.quote-select');
  if (!select) return;
  select.classList.toggle('changed', select.value !== select.dataset.default);
});

$('#modalOverlay').addEventListener('click', event => {
  if (event.target === modal.root) modal.close();
});

document.addEventListener('keydown', event => {
  if ($('#modalOverlay').classList.contains('open')) { modal.handleKeyboard(event); return; }
  const drawer = $('#treeDrawer');
  if (drawer && drawer.classList.contains('open')) {
    if (event.key === 'Escape') { event.preventDefault(); closeTree(); }
    return;
  }
  if (event.key === 'Escape' && (appShell.classList.contains('focus-strategy') || appShell.classList.contains('focus-situation'))) closePanelFocus();
});

initReportFab();
initPanelMode();

// 联调探针：验收/自动化测试用，不影响界面逻辑。
window.__diplomat = {
  store,
  submitTurn,
  injectError,
  setCoachMode,
  getCoachMode,
  adapterId: () => adapterId(),
  peekActionId: () => peekActionId(),
  stopBusyCountdown,
  coachRequests: () => coachRequestCount(),
  renderError,
  renderEndgame,
  judge: () => store.judge,
  versionBadges,
  openDebrief,
  renderDebrief
};
