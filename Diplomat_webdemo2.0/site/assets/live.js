(function () {
  'use strict';
  if (!window.__DIPLOMAT_LIVE__) return;

  var FIXED_MODE = window.__DIPLOMAT_MODE__ || 'bilateral';
  var API = '/api/v2';
  var CONFIRM_CARDS = ['bundle', 'public_bundle', 'package', 'phased'];
  var UI_TO_MODE = { bilateral: 'bilateral', multilateral: 'multi', observe: 'observe' };
  var MODE_TO_UI = { bilateral: 'bilateral', multi: 'multilateral', observe: 'observe' };
  var MODE_LABEL = { bilateral: '双边谈判', multi: '多边磋商', observe: '九方观战' };
  var DOM_SCREEN = { bilateral: 'bilateral', multi: 'multilateral', observe: 'observe' };
  var STANCE = { support: '支持', swing: '摇摆', oppose: '反对' };
  var PERSONA = ['neutral', 'partisan', 'snark'];
  var PERSONA_LABEL = { neutral: '中立分析师', partisan: '偏袒一方', snark: '毒舌评论员' };
  var S = {
    mode: FIXED_MODE, view: 'strategy', state: null, selected: [],
    busy: false, auto: true, timer: null, perspective: 'omniscient', follow: 'id',
    matrix: 'affinity', relation: null, tab: 'intel', persona: 0, lastEvent: null,
    target: null
  };

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }
  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function hl(value) {
    var s = esc(value || '');
    var CN = '[一二三四五六七八九十百千两]+';
    var UNITS = '(?:海里|公里|年|条|轮|届|亿|万个?|万|方|国|月|天|倍|%|％)';
    var NUM = '\\d+(?:\\.\\d+)?\\s*' + UNITS;
    var KW = '(支持|反对|接受|拒绝|要求|承诺|底线|条件|对价|配额|通行|主权|核查|过渡期|技术援助|表决|协议|草案|让步|威胁|制裁)';
    /* 先标「引号条件」，再标数字，最后标关键词，避免嵌套 */
    s = s.replace(/「([^」]{2,16})」/g, '\u0001$1\u0002');
    s = s.replace(new RegExp(NUM, 'g'), '<mark class="hl-num">$&</mark>');
    s = s.replace(new RegExp(CN + UNITS, 'g'), '<mark class="hl-num">$&</mark>');
    s = s.replace(new RegExp(KW, 'g'), '<b class="hl-kw">$1</b>');
    s = s.replace(/\u0001([^\u0002]*)\u0002/g, '「<mark class="hl">$1</mark>」');
    return s;
  }

  function rich(value) {
    return esc(value).replace(/「([^」]{1,24})」/g, '「<strong>$1</strong>」');
  }
  function pct(value) { return Math.max(0, Math.min(100, Number(value) || 0)); }
  function signed(value) {
    var n = Number(value) || 0;
    return (n > 0 ? '+' : '') + n;
  }
  function screen() { return $('.mode-screen[data-screen="' + DOM_SCREEN[S.mode] + '"]'); }
  function inScreen(sel) { return $$(sel, screen() || document); }
  function one(sel) { return $(sel, screen() || document); }
  function toast(message) {
    var el = $('#toast');
    if (!el) return;
    var span = $('span', el);
    if (span) span.textContent = message;
    el.classList.add('show');
    clearTimeout(toast.timer);
    var duration = /失败|降级|错误|不可用/.test(String(message)) ? 6500 : 2800;
    toast.timer = setTimeout(function () { el.classList.remove('show'); }, duration);
  }

  function flagArt(key) {
    var art = {
      cn: '<rect width="60" height="60" fill="#de2910"/><g fill="#ffde00"><path d="M0-6l1.8 4.1H6L2.7 1 3.8 5 0 2.5-3.8 5-2.7 1-6-1.9h4.2z" transform="translate(15 17) scale(1.35)"/><path d="M0-6l1.8 4.1H6L2.7 1 3.8 5 0 2.5-3.8 5-2.7 1-6-1.9h4.2z" transform="translate(29 8) rotate(22) scale(.43)"/><path d="M0-6l1.8 4.1H6L2.7 1 3.8 5 0 2.5-3.8 5-2.7 1-6-1.9h4.2z" transform="translate(34 17) rotate(42) scale(.43)"/><path d="M0-6l1.8 4.1H6L2.7 1 3.8 5 0 2.5-3.8 5-2.7 1-6-1.9h4.2z" transform="translate(33 27) rotate(58) scale(.43)"/><path d="M0-6l1.8 4.1H6L2.7 1 3.8 5 0 2.5-3.8 5-2.7 1-6-1.9h4.2z" transform="translate(27 35) rotate(28) scale(.43)"/></g>',
      us: '<rect width="60" height="60" fill="#fff"/><path d="M0 0h60v7H0zm0 14h60v7H0zm0 14h60v7H0zm0 14h60v7H0zm0 14h60v4H0z" fill="#b22234"/><rect width="29" height="32" fill="#3c3b6e"/><g fill="#fff"><circle cx="6" cy="7" r="1.3"/><circle cx="14" cy="7" r="1.3"/><circle cx="22" cy="7" r="1.3"/><circle cx="10" cy="14" r="1.3"/><circle cx="18" cy="14" r="1.3"/><circle cx="6" cy="21" r="1.3"/><circle cx="14" cy="21" r="1.3"/><circle cx="22" cy="21" r="1.3"/><circle cx="10" cy="28" r="1.3"/><circle cx="18" cy="28" r="1.3"/></g>',
      su: '<rect width="60" height="60" fill="#cc0000"/><g transform="translate(-26.5 -2) scale(.23)" fill="#ffd700"><path d="m 200.0005,37.5 -8.41933,25.911886 H 164.336 L 186.37777,79.426122 177.95844,105.338 200.0005,89.323465 222.04257,105.338 213.62324,79.426122 235.665,63.411886 h -27.24516 z m 0,13.499987 5.38828,16.583473 h 17.43718 l -14.107,10.249496 5.38827,16.583472 L 200.0005,84.167224 185.89378,94.416428 191.28205,77.832956 177.17504,67.58346 h 17.43718 z"/><g transform="matrix(0.98931879,0,0,0.98673811,3.8297658,3.7659398)"><path d="m 137.43744,171.69421 18.86296,18.9937 17.78834,-17.66589 c 27.05847,29.021 55.43807,56.99501 82.28704,86.12782 4.03444,4.06233 10.59815,4.085 14.66056,0.0506 4.06232,-4.03445 4.08499,-10.59815 0.0506,-14.66056 -28.81871,-27.1901 -57.72545,-54.60143 -86.55328,-81.89095 l 23.96499,-23.80003 -33.34026,-4.61605 z"/><path d="m 198.2887,110.1955 c 15.51743,8.7394 27.29872,21.28122 34.2484,34.3924 7.04394,13.28902 10.13959,27.16218 10.20325,38.25433 0.13054,22.74374 -18.43771,41.18184 -41.18183,41.18184 -12.13597,0 -23.04607,-5.24868 -30.58302,-13.60085 l -4.16863,3.51033 c -0.70999,-0.27231 -1.46387,-0.41221 -2.22429,-0.41276 -1.82948,1.9e-4 -3.56621,0.80531 -4.74859,2.20136 -2.97368,0.38896 -5.46251,2.44529 -6.40534,5.29224 -3.13486,6.28843 -8.63524,11.21997 -15.29104,13.4776 -0.0637,0.0216 -0.11992,0.05 -0.1758,0.0783 -3.07749,1.12758 -6.16259,3.1643 -8.78919,5.80245 -5.19155,5.23656 -7.72858,11.93658 -6.30024,16.63822 -0.14098,0.40857 -0.21361,0.83759 -0.21498,1.26979 1.5e-4,2.17082 1.75991,3.93058 3.93073,3.93073 0.54341,-0.002 1.08053,-0.11639 1.57745,-0.33632 4.69369,1.05881 11.06885,-1.54582 16.05444,-6.55917 2.82624,-2.85072 4.94356,-6.22349 5.98303,-9.53062 2.31696,-6.62278 7.29699,-12.01856 13.62281,-15.05312 0.15105,-0.0725 0.27303,-0.14714 0.38218,-0.22358 2.12082,-1.01408 3.67251,-2.92895 4.225,-5.2139 9.70222,11.44481 24.25255,18.75299 40.51876,19.13577 29.83352,0.70205 52.13299,-21.25802 53.16414,-52.83642 0.51894,-15.89259 -5.62993,-36.3847 -19.6412,-53.19089 -10.70835,-12.84441 -26.40987,-23.50795 -44.18699,-28.20777 z"/></g></g>',
      br: '<rect width="60" height="60" fill="#009c3b"/><path d="M30 8L54 30 30 52 6 30z" fill="#ffdf00"/><circle cx="30" cy="30" r="12" fill="#002776"/><path d="M19 27c8-3 16-2 23 3" fill="none" stroke="#fff" stroke-width="2"/>',
      id: '<rect width="60" height="60" fill="#fff"/><rect width="60" height="30" fill="#e70011"/>',
      jp: '<rect width="60" height="60" fill="#fff"/><circle cx="30" cy="30" r="15" fill="#bc002d"/>',
      'in': '<rect width="60" height="20" fill="#ff9933"/><rect y="20" width="60" height="20" fill="#fff"/><rect y="40" width="60" height="20" fill="#138808"/><circle cx="30" cy="30" r="6" fill="none" stroke="#000080" stroke-width="1.5"/><path d="M30 24v12M24 30h12M25.8 25.8l8.4 8.4m0-8.4l-8.4 8.4" stroke="#000080" stroke-width=".8"/>',
      eg: '<rect width="60" height="20" fill="#ce1126"/><rect y="20" width="60" height="20" fill="#fff"/><rect y="40" width="60" height="20" fill="#000"/><path d="M30 23l5 5-2 8h-6l-2-8z" fill="#c9a227"/>',
      sg: '<rect width="60" height="60" fill="#fff"/><rect width="60" height="30" fill="#ef2536"/><circle cx="18" cy="15" r="8" fill="#fff"/><circle cx="21" cy="13" r="7" fill="#ef2536"/><g fill="#fff"><circle cx="28" cy="8" r="1.3"/><circle cx="34" cy="13" r="1.3"/><circle cx="31" cy="21" r="1.3"/><circle cx="23" cy="23" r="1.3"/><circle cx="23" cy="13" r="1.3"/></g>',
      uk: '<rect width="60" height="60" fill="#012169"/><path d="M0 0l60 60M60 0L0 60" stroke="#fff" stroke-width="12"/><path d="M0 0l60 60M60 0L0 60" stroke="#c8102e" stroke-width="5"/><path d="M30 0v60M0 30h60" stroke="#fff" stroke-width="18"/><path d="M30 0v60M0 30h60" stroke="#c8102e" stroke-width="10"/>',
      tr: '<rect width="60" height="60" fill="#e30a17"/><circle cx="24" cy="30" r="12" fill="#fff"/><circle cx="28" cy="30" r="9.6" fill="#e30a17"/><path d="M40 30l-6.5-2.2 4 5.4v-6.4l-4 5.4z" fill="#fff"/>',      eu: '<rect width="60" height="60" fill="#344f91"/><g fill="#f1cf5c"><circle cx="30" cy="10" r="2"/><circle cx="40" cy="13" r="2"/><circle cx="47" cy="22" r="2"/><circle cx="47" cy="34" r="2"/><circle cx="40" cy="44" r="2"/><circle cx="30" cy="48" r="2"/><circle cx="20" cy="44" r="2"/><circle cx="13" cy="34" r="2"/><circle cx="13" cy="22" r="2"/><circle cx="20" cy="13" r="2"/></g>'
    };
    return '<svg viewBox="0 0 60 60" aria-hidden="true">' +
      (art[key] || '<rect width="60" height="60" fill="#8b7149"/>') + '</svg>';
  }
  function hydrateFlags(root) {
    $$('[data-flag]', root || document).forEach(function (el) {
      var key = el.getAttribute('data-flag');
      if (el.getAttribute('data-flag-done') === key) return;
      el.innerHTML = flagArt(key);
      el.setAttribute('data-flag-done', key);
    });
  }

  async function api(path, body) {
    var response = await fetch(API + path, {
      method: body ? 'POST' : 'GET',
      headers: { 'Content-Type': 'application/json', 'X-Client': clientId() },
      body: body ? JSON.stringify(body) : undefined,
      cache: 'no-store'
    });
    var data = {};
    try { data = await response.json(); } catch (e) { data = {}; }
    if (!response.ok || data.error) {
      throw new Error(data.error || ('HTTP ' + response.status));
    }
    return data;
  }

  function setBusy(on, label) {
    S.busy = !!on;
    var app = $('#app');
    if (app) app.classList.toggle('live-busy', !!on);
    var box = $('#liveLoading');
    if (!box) {
      box = document.createElement('div');
      box.id = 'liveLoading';
      box.className = 'live-loading';
      document.body.appendChild(box);
    }
    box.textContent = label || '';
    box.classList.toggle('show', !!on && !!label);
    var end = $('#liveEndTurn') || (screen() && $('.end-turn', screen()));
    if (end) end.disabled = !!on;
    var next = $('#nextSpeech');
    if (next) next.disabled = !!on;
  }

  // ---------------------------------------------------------------- 会话

  function resetTable() {
    /* 每次进对局都从干净状态开始：清掉 HTML 里的样张内容 */
    ['#signalList', '#multiSignalList', '#eventHistoryBody', '.mini-timeline'].forEach(function (sel) {
      var el = $(sel);
      if (el) el.innerHTML = '<div class="fold-placeholder">正在准备会场…</div>';
    });
    $$('.speech-body p, .council-speech-body p').forEach(function (el) {
      el.textContent = '正在准备会场…';
    });
    $$('.delegation em').forEach(function (el) { el.textContent = ''; });
    var badge = document.querySelector('#eventDemo span');
    if (badge) { badge.textContent = '0'; badge.style.display = 'none'; }
  }

  var CLIENT_ID = null;
  function clientId() {
    if (CLIENT_ID) return CLIENT_ID;
    try {
      CLIENT_ID = sessionStorage.getItem('v2-client');
      if (!CLIENT_ID) {
        CLIENT_ID = Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
        sessionStorage.setItem('v2-client', CLIENT_ID);
      }
    } catch (e) { CLIENT_ID = 'tab'; }
    return CLIENT_ID;
  }

  function scenarioFor(mode) {
    var tid = '';
    try { tid = (new URLSearchParams(location.search)).get('topic') || ''; } catch (e) { tid = ''; }
    var TOPICS = {
      'compute-chip': { rounds: 12, parties: ['cn','us','eu','in','br','jp'] },
      'unclos': { rounds: 12, parties: ['cn','us','su','br','id','jp','in','eg','sg'] },
      'dst': { rounds: 12, parties: ['cn','us','eu','in','uk','tr'] }
    };
    if (mode === 'observe') {
      var ob = TOPICS[tid] || TOPICS['unclos'];
      return { topic_id: TOPICS[tid] ? tid : 'unclos', rounds: 18, max_turns: 18, parties: ob.parties };
    }
    var sc = TOPICS[tid] || TOPICS['compute-chip'];
    if (mode === 'multi') {
      return { topic_id: TOPICS[tid] ? tid : 'compute-chip', rounds: 25, max_turns: 25, parties: sc.parties };
    }
    return { topic_id: TOPICS[tid] ? tid : 'compute-chip', rounds: 15, parties: sc.parties };
  }

  function mySeat() {
    var raw = '';
    try { raw = (new URLSearchParams(location.search)).get('player') || ''; } catch (e) { raw = ''; }
    return (raw || S.seat || 'cn').toLowerCase();
  }

  async function startSession() {
    var mode = FIXED_MODE;
    resetTable();
    /* 观战是独立场景：清掉上一局（比如双边）留下的场景信息 */
    if (mode === 'observe') {
      try {
        localStorage.removeItem('neg-pick');
        localStorage.setItem('neg-scene', JSON.stringify({
          version: 'observe', topic: '联合国海洋法公约 · 第三次海洋法会议',
          topicId: 'unclos', you: null, rivals: [], size: 9
        }));
      } catch (e) {}
    }
    S.mode = mode;
    S.selected = [];
    S.target = null;
    S.state = null;
    S.lastEvent = null;
    S.persona = 0;
    S.perspective = 'omniscient';
    var cfg = scenarioFor(mode);
    var wanted = mySeat();
    var _rq = '';
    try { _rq = (new URLSearchParams(location.search)).get('rivals') || ''; } catch (e) { _rq = ''; }
    var pickedRivals = _rq.split(',').map(function (x) { return x.trim(); }).filter(Boolean);
    if (wanted && cfg.parties.indexOf(wanted) < 0) cfg.parties.unshift(wanted);
    if (wanted && cfg.parties.indexOf(wanted) < 0) wanted = 'cn';
    S.seat = mode === 'observe' ? null : wanted;
    S.follow = mode === 'observe' ? 'id' : wanted;
    S.auto = true;
    stopAuto();
    setModeUI();
    setBusy(true, '正在准备会场…');
    var rivals = mode === 'observe'
      ? cfg.parties.slice()
      : cfg.parties.filter(function (key) { return key !== wanted; });
    if (mode !== 'observe' && pickedRivals.length) {
      var _valid = pickedRivals.filter(function (k) { return k !== wanted; });
      if (_valid.length) rivals = _valid;
    }
    if (mode === 'bilateral') rivals = rivals.slice(0, 1);
    try {
      var body = {
        mode: mode, topic_id: cfg.topic_id, rounds: cfg.rounds,
      max_turns: cfg.max_turns || cfg.rounds,
        player: mode === 'observe' ? null : wanted,
        rival: rivals[0],
        rivals: rivals, seed: 7,
        perspective: S.perspective, follow: S.follow
      };
      var res = await api('/session', body);
      setBusy(false);
      applyView(res.view);
    if (mode === 'multi' && res.view && !res.view.finished) {
      /* 多边：先由一位 NPC 开场（带重试，避免被 busy 吞掉） */
      var kickRound = Number(res.view.round || 0);
      var kick = function (tries) {
        if (S.mode !== 'multi') return;
        if (S.busy || !S.state || Number(S.state.round || 0) !== kickRound) {
          if (tries > 0) setTimeout(function () { kick(tries - 1); }, 700);
          return;
        }
        if ((S.state.messages || []).some(function (m) { return m.role !== 'player'; })) return;
        nextSpeech();
      };
      setTimeout(function () { kick(6); }, 600);
    }
      var keep = mode === 'observe' ? '' : ('?player=' + wanted);
      history.replaceState(null, '', location.pathname + keep);
      toast('已进入' + MODE_LABEL[mode] + ' · ' + (res.offline ? '离线演示' : '真实模型'));
      if (mode === 'observe') startAuto();
    } catch (e) {
      setBusy(false);
      if (location.protocol === 'file:') {
        var sample = window.DIPLOMAT_SAMPLES && window.DIPLOMAT_SAMPLES[FIXED_MODE];
        if (sample) {
          try { applyView(sample); } catch (err) { /* 快照坏了也不影响提示 */ }
        }
        showFileTip();
        return;
      }
      toast(e.message || '无法连接本地引擎');
    }
  }

  function showFileTip() {
    var old = $('#fileTip');
    if (old) return;
    var tip = document.createElement('div');
    tip.id = 'fileTip';
    tip.className = 'live-file-tip';
    tip.innerHTML = '<div><strong>静态预览 · 非实时</strong>' +
      '<span>实时对局请双击 <code>启动新界面.bat</code>，再访问 ' +
      '<code>http://127.0.0.1:8002/diplomat/multi.html</code></span></div>' +
      '<button type="button" id="fileTipClose">知道了</button>';
    document.body.appendChild(tip);
    var close = $('#fileTipClose');
    if (close) close.addEventListener('click', function () { tip.remove(); });
  }

  function restartSession() {
    if (!confirm('重新开始本局谈判？当前进度会清空。')) return;
    stopAuto();
    S.busy = false;
    /* 清掉「已读」记录，保证新一局的提示重新计数 */
    document.querySelectorAll('#signalSummary, #multiSignalSummary').forEach(function (el) {
      delete el.dataset.seen;
      el.classList.remove('has-new');
    });
    document.querySelectorAll('#signalCount, #multiSignalCount').forEach(function (el) {
      el.textContent = '';
      el.style.display = 'none';
    });
    try { localStorage.removeItem('neg-report'); } catch (e) {}
    S.lastEvent = null;
    S.persona = 0;
    startSession();
  }

  function setModeUI() {
    var app = $('#app');
    var collapsed = [];
    if (app && app.classList.contains('left-collapsed')) collapsed.push('left-collapsed');
    if (app && app.classList.contains('right-collapsed')) collapsed.push('right-collapsed');
    if (app) {
      app.className = 'mode-' + S.mode + ' view-' + S.view +
        (collapsed.length ? ' ' + collapsed.join(' ') : '');
    }
    $$('.mode-screen').forEach(function (section) {
      section.classList.toggle('active',
        section.getAttribute('data-screen') === DOM_SCREEN[S.mode]);
    });
    $$('.mode-switch [data-mode]').forEach(function (link) {
      link.classList.toggle('active', link.getAttribute('data-mode') === MODE_TO_UI[S.mode]);
    });
    var campTab = $('#drawerTabs [data-tab="camp"]');
    if (campTab) campTab.style.display = S.mode === 'bilateral' ? 'none' : '';
    if (app) app.classList.toggle('is-following', S.mode === 'observe' && S.perspective === 'party');
  }

  function applyView(view, event) {
    if (!view) return;
    S.state = view;
    setModeUI();
    renderTop(view);
    var _list = view.deals || (view.deal ? [view.deal] : []);
    var _deal = _list.filter(function (d) { return d.initiator === 'npc' && d.status === 'draft'; }).pop() || null;
    if (_deal && S._seenInvite !== _deal.id) {
      S._seenInvite = _deal.id;
      setTimeout(function () { showSecretCard(_deal); }, 700);
    } else {
      /* 暗线节点：谈判树里已经有「某人 → 我」的接触，也弹卡提醒 */
      var meKey = ((view.player || {}).key) || '';
      var dark = ((view.tree || {}).nodes || []).filter(function (n) {
        return n.kind === 'nonpublic' && (n.visibility || []).indexOf(meKey) >= 0;
      }).pop();
      if (dark && meKey && S._seenDark !== dark.id) {
        S._seenDark = dark.id;
        var other = (dark.visibility || []).filter(function (k) { return k !== meKey; })[0] || '';
        setTimeout(function () {
          showSecretCard({ party_label: _labelOf(other), their_term: dark.claim || '' });
        }, 900);
      }
    }
    if (S.mode === 'bilateral') renderBilateral(view);
    else if (S.mode === 'multi') {
      renderMulti(view);
      /* 只要还有 NPC 待回应，就由渲染驱动继续推进（不依赖调用点） */
      if (!view.finished && Number(view.auto_left || 0) > 0) scheduleMultiAuto();
      /* NPC 依次说完后交回玩家：等 8 秒再提示，先让最后一句显示完整 */
      clearTimeout(S._turnPromptTimer);
      if (!view.finished && Number(view.auto_left || 0) === 0 && !S._ownPreview) {
        S._turnPromptTimer = setTimeout(function () {
          if (S.mode !== 'multi' || !S.state) return;
          if (Number(S.state.auto_left || 0) !== 0) return;
          if (S._ownPreview) return;
          showPlayerTurn(S.state);
        }, 8000);
      }
    }
    else {
      renderObserve(view);
      /* 观战走的是独立渲染流程，旁白/信号/纪要需要单独刷新 */
      renderNarrator(view);
      renderSignals(view);
      renderTimeline(view);
    }
    hydrateFlags(document);
    if ($('#analysisDrawer').classList.contains('open')) renderDrawer();
    if (event) showEvent(event);
    if (view.finished) {
      var status = $('#playStatus');
      if (status) status.textContent = '谈判已结束';
    }
  }

  function renderTop(view) {
    var roundEl = $('#roundNumber');
    var shown = Math.max(1, Number(view.round) || 0);
    if (roundEl) roundEl.textContent = String(shown).padStart(2, '0');
    var totalEl = $('#roundTotal');
    if (totalEl) totalEl.textContent = '/ ' + (view.round_total || view.max_rounds || 12);
    var eyebrow = $('#topicEyebrow');
    if (eyebrow) eyebrow.textContent = view.topic_id === 'unclos'
      ? 'THIRD UN CONFERENCE · 1973—1982' : 'GLOBAL AI GOVERNANCE';
    var title = $('#topicTitle');
    if (title) title.textContent = view.topic || '';
  }

  // ---------------------------------------------------------------- 双边

  var ACTION_CN = {
    offer: '出价', concede: '让步', demand: '索价', threat: '威胁',
    disclose: '揭露', probe: '试探', procedure: '程序', batna: '底线'
  };

  function claimLabel(message) {
    var info = message.bluff;
    if (!info) return '';
    var action = ACTION_CN[info.claimed_action] || info.claimed_action || '';
    var pct = Math.round(Number(info.credibility || 0) * 100);
    var tail = info.player_noticed ? ' · 你已识破' : '';
    return '宣称：' + action + ' · 可信度 ' + pct + '%' + tail;
  }

  function playedLabel(message) {
    var cards = message.cards || [];
    if (!cards.length) return '';
    return cards.map(function (c) { return (c.kind || '') + '·' + (c.name || ''); }).join(' + ');
  }

  function addrChip(message) {
    var targets = (message && message.addressed_to) || [];
    if (!targets.length) return '';
    var names = targets.map(function (k) { return _labelOf(k); }).join('、');
    return '<span class="addr-chip">→ ' + esc(names) + '</span>';
  }

  function speechHTML(message, view, isLast) {
    var self = message.role === 'player';
    var cards = (message.cards || []).map(function (c) { return c.name || c; });
    var played = playedLabel(message);
    var metaRight = self
      ? ((cards.length ? '策略卡：' + cards.join(' · ') : '我方发言') +
         (claimLabel(message) ? ' · ' + claimLabel(message) : ''))
      : (claimLabel(message) || played || (message.stance && STANCE[message.stance]) || '回应');
    var advisor = '';
    if (!self && isLast) {
      var note = (view.last && view.last.settle_notes && view.last.settle_notes[0]) ||
        (view.risk && view.risk.message) || '';
      if (note) advisor = '<div class="advisor-reading"><span>顾问解读</span>' + esc(note) + '</div>';
      var fc = view.last && view.last.fact_check;
      if (fc && fc.flagged && fc.flagged.length) {
        advisor += '<div class="advisor-reading live-factcheck"><span>事实核查</span>' +
          esc(fc.flagged.slice(0, 2).map(function (item) {
            return (item.token || item.text || item.value || '') + '：' +
              (item.reason || '与知识库不一致');
          }).join('；')) + '</div>';
      }
    }
    return '<article class="speech ' + (self ? 'self-speech' : 'opponent-speech') +
      (isLast ? ' current-speech' : '') + '">' +
      '<div class="speech-avatar" data-flag="' + esc(message.speaker) + '"></div>' +
      '<div class="speech-body"><div class="speech-meta"><strong>' +
      esc(message.label) + (self ? ' · 我方' : '') + '</strong>' +
      '<span>第 ' + esc(message.round) + ' 轮</span>' + addrChip(message) + '<em>' + esc(metaRight) + '</em></div>' +
      '<p>' + hl(message.text) + '</p>' + advisor + '</div></article>';
  }

  function renderBilateral(view) {
    var box = one('.dialogue-scroll');
    if (box) {
      var messages = (view.messages || []).slice(-6);
      box.classList.toggle('is-opening', messages.length === 0);
      box.innerHTML = messages.length ? messages.map(function (m, i) {
        return speechHTML(m, view, i === messages.length - 1);
      }).join('') :
        '<div class="opening-notice" role="status"><svg viewBox="0 0 24 24" aria-hidden="true">' +
        '<path d="M13 2 4 14h7l-1 8 10-13h-7z"/></svg><span>谈判开始 · 请陈述我方立场' +
        '（第 1 轮 / 共 ' + esc(view.round_total || view.max_rounds || 15) + ' 轮）</span></div>';
    }

    var banner = one('.risk-banner');
    if (banner) {
      var risk = view.risk || {};
      if (risk.level && risk.level !== 'low') {
        banner.hidden = false;
        banner.style.display = '';
        var strong = $('strong', banner);
        var small = $('small', banner);
        var em = $('em', banner);
        if (strong) strong.textContent = '方案研判 · ' + (risk.label || '');
        if (small) small.textContent = risk.message || '';
        if (em) em.textContent = (risk.basis || 0) + ' 条情报依据';
      } else {
        banner.hidden = true;
        banner.style.display = 'none';
      }
    }

    renderStrategy(view);
    renderMetrics(view);
    renderOpponent(view);
    renderChannel(view);
    renderTasks(view);
    renderNarrator(view);
    renderSignals(view);
    renderTimeline(view);
    renderTargetChip();
  }

  var CARD_ICONS = {
    book: 'i-intel', scale: 'i-matrix', shield: 'i-shield', eye: 'i-eye',
    compass: 'i-intel', gavel: 'i-tree', lens: 'i-eye', swap: 'i-nodes',
    seal: 'i-check', link: 'i-nodes', key: 'i-lock', gift: 'i-plus',
    handshake: 'i-nodes', steps: 'i-tree', megaphone: 'i-send',
    bolt: 'i-intel', package: 'i-tree', flag: 'i-shield', door: 'i-close'
  };
  var RARITY_LABEL = { common: '普通', uncommon: '罕见', rare: '稀有' };

  var CARD_ART = {
    offer: 'coop', concede: 'coop', demand: 'pressure', threat: 'pressure',
    batna: 'endgame', disclose: 'evidence', probe: 'probe', procedure: 'procedure'
  };
  var CARD_ART_KIND = {
    '出价': 'coop', '让步': 'coop', '索价': 'pressure', '威胁': 'pressure',
    '底线': 'endgame', '揭露': 'evidence', '试探': 'probe', '程序': 'procedure',
    '造势': 'mobilize', '终局': 'endgame', '修饰': 'mobilize'
  };

  function cardHTML(card) {
    var selected = S.selected.indexOf(card.id) >= 0;
    var effects = (card.effects || []).map(function (line) { return '<li>' + esc(line) + '</li>'; }).join('');
    var icon = CARD_ICONS[card.icon] || 'i-intel';
    var color = card.color || '#c9a061';
    var artKey = CARD_ART[card.action] || CARD_ART_KIND[card.kind] || 'coop';
    return '<button class="strategy-card game-card' + (selected ? ' selected' : '') +
      (card.recommended ? ' recommended' : '') + '" data-card-id="' + esc(card.id) + '" ' +
      'data-cost="' + esc(card.cost) + '" style="--c:' + esc(color) + '" data-model="' + esc(card.model_label) + '" ' +
      'data-model-desc="' + esc(card.model_desc || '') + '" title="' + esc(card.detail || card.desc || '') + '">' +
      '<span class="gc-cost">' + esc(card.cost) + '</span>' +
      '<div class="gc-frame">' +
      '<div class="gc-name">' + esc(card.name) + '</div>' +
      '<div class="gc-art" data-art="' + artKey + '" style="--c:' + esc(color) + '">' +
      '<div class="gc-art-art"></div><svg class="gc-art-icon"><use href="#' + icon + '"/></svg></div>' +
      '<div class="gc-type">' + esc(card.kind || '') + ' · ' + esc(RARITY_LABEL[card.rarity] || '普通') + '</div>' +
      '<div class="gc-desc">' + esc(card.desc || '') + '</div>' +
      '<ul class="gc-effects">' + effects + '</ul>' +
      '</div>' +
      (card.recommended ? '<em class="gc-em">顾问建议</em>' : '') +
      '</button>';
  }

  function renderStrategy(view) {
    var sc = screen();
    if (!sc) return;
    var area = $('.strategy-area', sc);
    if (!area) return;
    var hand = view.hand || [];
    var cardsBox = $('.strategy-cards', area);
    if (cardsBox) cardsBox.innerHTML = hand.map(cardHTML).join('');

    updateSelectionUI();
  }

  function updateSelectionUI() {
    var view = S.state;
    if (!view) return;
    var sc = screen();
    if (!sc) return;
    var hand = view.hand || [];
    var selectedCards = hand.filter(function (c) { return S.selected.indexOf(c.id) >= 0; });
    var used = selectedCards.reduce(function (sum, c) { return sum + Number(c.cost || 0); }, 0);
    var maxAp = Number((view.action_points || {}).max) || 3;
    var remaining = Math.max(0, maxAp - used);

    $$('.strategy-card', sc).forEach(function (el) {
      el.classList.toggle('selected', S.selected.indexOf(el.getAttribute('data-card-id')) >= 0);
      if (el.hasAttribute('data-cost')) {
        el.disabled = Number(el.getAttribute('data-cost')) > remaining &&
          S.selected.indexOf(el.getAttribute('data-card-id')) < 0;
      }
    });

    $$('.action-points', sc).forEach(function (box) {
      var strong = $('strong', box);
      var dots = $$('i', box);
      if (dots.length !== maxAp) {
        var html = '';
        for (var i = 0; i < maxAp; i++) html += '<i></i>';
        box.innerHTML = html + '<strong></strong>';
        strong = $('strong', box);
        dots = $$('i', box);
      }
      if (strong) strong.textContent = remaining + ' / ' + maxAp;
      dots.forEach(function (dot, index) {
        dot.classList.toggle('filled', index < remaining);
      });
    });

    var modelEl = one('[data-game-model]');
    var descEl = one('[data-game-model-desc]');
    if (modelEl) {
      modelEl.textContent = selectedCards.length
        ? selectedCards.map(function (c) { return c.model_label; }).join(' + ')
        : '尚未出牌';
    }
    if (descEl) {
      descEl.textContent = selectedCards.length === 1
        ? (selectedCards[0].model_desc || '')
        : selectedCards.length > 1
          ? '组合战术：' + selectedCards.map(function (c) { return c.name; }).join(' + ')
          : '选择卡牌后显示策略逻辑';
    }

    var end = $('#liveEndTurn') || $('.end-turn', sc);
    if (end) {
      end.disabled = S.busy || !!(view && view.finished);
      end.textContent = view && view.finished ? '谈判已结束' : '结束本轮';
    }
  }

  // ---------------------------------------------------------------- 定向发言

  function targetLabel(key) {
    if (!key) return '全体';
    var parties = (S.state && S.state.parties) || [];
    var hit = parties.filter(function (p) { return p.key === key; })[0];
    return hit ? hit.label : key;
  }

  function applyTarget(key) {
    if (!S.state) return;
    var player = S.state.player ? S.state.player.key : null;
    if (key === player) key = null;
    S.target = (S.target === key) ? null : key;
    renderTargetChip();
    syncSeatSelection();
  }

  // 只切类名，不重建 DOM —— 重建会让国旗（SVG）丢水合，也会卡
  function syncSeatSelection() {
    var sc = screen();
    if (!sc) return;
    $$('[data-target-key]', sc).forEach(function (el) {
      var hit = !!S.target && el.getAttribute('data-target-key') === S.target;
      el.classList.toggle('selected', hit);
    });
  }

  function renderTargetChip() {
    var sc = screen();
    if (!sc || !S.state || S.mode !== 'multi') return;
    var heading = $('.strategy-heading', sc);
    if (!heading) return;
    var chip = $('#liveTargetChip', heading);
    if (!chip) {
      chip = document.createElement('button');
      chip.id = 'liveTargetChip';
      chip.type = 'button';
      chip.className = 'target-chip';
      var anchor = $('.channel-inline', heading);
      if (anchor && anchor.parentNode === heading) heading.insertBefore(chip, anchor);
      else heading.appendChild(chip);
      chip.addEventListener('click', function (event) {
        event.stopPropagation();
        if (S.mode === 'bilateral') {
          var opponent = (S.state.opponent || {}).key || null;
          S.target = S.target ? null : opponent;
        } else {
          S.target = null;
          syncSeatSelection();
        }
        renderTargetChip();
      });
    }
    var key = S.target;
    chip.classList.toggle('active', !!key);
    chip.innerHTML = '<svg><use href="#i-intel"/></svg>发言对象：' + esc(targetLabel(key)) +
      (key ? ' <i>✕</i>' : ' <small>点席位定向</small>');
  }

  function toggleCard(cardId) {
    var card = (S.state && S.state.hand || []).filter(function (c) { return c.id === cardId; })[0];
    if (!card || S.busy) return;
    var index = S.selected.indexOf(cardId);
    if (index >= 0) {
      S.selected.splice(index, 1);
    } else {
      var maxAp = Number((S.state.action_points || {}).max) || 3;
      var used = S.selected.reduce(function (sum, id) {
        var c = (S.state.hand || []).filter(function (x) { return x.id === id; })[0];
        return sum + (c ? Number(c.cost) : 0);
      }, 0);
      if (used + Number(card.cost) > maxAp) {
        toast('行动点不足：本轮最多消耗 ' + maxAp + ' 点');
        return;
      }
      S.selected.push(cardId);
    }
    updateSelectionUI();
  }

  function renderMetrics(view) {
    var box = one('.metric-list');
    if (!box || !view.player) return;
    var deltas = (view.last && view.last.deltas && view.last.deltas.player) || {};
    var rows = [
      { key: 'interest', label: '主体利益', cls: '', dk: 'interest_delta' },
      { key: 'image', label: '国际形象', cls: 'blue', dk: 'image_delta' },
      { key: 'trust', label: '盟友信任', cls: 'purple', dk: 'trust_delta' }
    ];
    box.innerHTML = rows.map(function (row) {
      var value = Number((view.player.indexes || {})[row.key] || 0);
      var delta = Number(deltas[row.dk] || 0);
      var before = Math.max(0, Math.min(100, value - delta));
      return '<div class="metric ' + row.cls + '"><div><span>' + row.label + '</span><strong>' +
        Math.round(value) + '<small class="' + (delta < 0 ? 'negative' : '') + '">' +
        (delta ? signed(delta) : '') + '</small></strong></div>' +
        '<div class="metric-track"><i style="width:' + pct(value) + '%"></i>' +
        '<b style="left:' + pct(before) + '%"></b></div></div>';
    }).join('');
  }

  function renderOpponent(view) {
    var box = one('.opponent-situation');
    if (!box) return;
    var op = view.opponent || {};
    var intel = op.intel || view.intel || {};
    var trust = op.trust_toward_player || {};
    var win = op.window || {};
    var image = '-';
    if (op.indexes) image = Math.round(Number(op.indexes.image || 0));
    else if (op.public_image != null) image = Math.round(Number(op.public_image));
    else if (op.indexes_range && op.indexes_range.image) {
      image = op.indexes_range.image[0] + '–' + op.indexes_range.image[1];
    }
    var range = intel.interest_range || ['?', '?'];
    var cells = [
      '<div><span>公开形象</span><strong>' + image + '</strong><small>公开评价</small></div>',
      '<div><span>核心利益</span><strong>' + esc(range[0]) + '～' + esc(range[1]) +
      '</strong><small>情报区间 · 非真值</small></div>'
    ];
    if (view.mode !== 'observe') {
      cells.splice(1, 0, '<div><span>对我信任</span><strong>' +
        esc(trust.label || '未知') + ' → ' + esc(trust.trend_label || '持平') +
        '</strong><small>估计 · 可信度' + esc(trust.confidence_label || '低') + '</small></div>');
      cells.push('<div><span>合作窗口</span><strong>' + esc(win.label || '未知') +
        '</strong><small>' + esc(win.basis || 0) + ' 条公开依据</small></div>');
    }
    box.innerHTML =
      '<div class="situation-head"><span data-flag="' + esc(op.key) + '"></span><strong>' +
      esc(op.label || '') + '</strong><em>' + esc((op.stance || {}).position_label || '') +
      '</em></div><div class="situation-grid">' + cells.join('') + '</div>' +
      '<small class="evidence-link">查看趋势、区间与证据 →</small>';
  }

  function currentDeal(view) {
    if (!view) return null;
    var deals = (view.deals || []).filter(function (d) {
      return ['draft', 'intent', 'confirmed'].indexOf(d.status) >= 0;
    });
    if (deals.length) return deals[deals.length - 1];
    return view.pending_invite || null;
  }

  function renderChannel(view) {
    var sc = screen();
    if (!sc) return;
    var deal = currentDeal(view);
    var op = view.opponent || {};
    var policy = (view.channel_policies || []).filter(function (p) { return p.key === op.key; })[0] || {};
    var preview = $('.secret-preview', sc);
    if (preview) {
      var title = deal
        ? (deal.status === 'confirmed' ? '非正式沟通 · 已公开确认'
          : deal.status === 'intent' ? '非正式沟通 · 待公开确认'
            : deal.initiator === 'npc' ? '对方请求非正式沟通'
              : '已发起沟通 · 待交换意向')
        : ('非正式沟通 · ' + (policy.policy_label || '受限'));
      var note = deal ? ('『' + (deal.their_term || '') + '』⇄『' + (deal.our_term || '') + '』')
        : (policy.disclosure || '可私下探底 · 秘密附件暂不开放');
      preview.innerHTML = '<svg><use href="#i-lock"/></svg><div><strong>' + esc(title) +
        '</strong><small>' + esc(note) + '</small></div><svg><use href="#i-chevron"/></svg>';
    }
    var dealCard = $('.deal-card', sc);
    if (dealCard) {
      if (deal) {
        dealCard.innerHTML = '<div><span data-flag="' + esc(view.player.key) +
          '"></span><i>⇄</i><span data-flag="' + esc(deal.party) + '"></span><em>' +
          esc(deal.status_label || '') + '</em></div><strong>' +
          esc(deal.our_term || '') + ' ⇄ ' + esc(deal.their_term || '') +
          '</strong><small>' + esc(deal.status === 'intent' ? '须用正式卡牌公开确认' : '不产生秘密约束') +
          '</small>';
      } else {
        dealCard.innerHTML = '<div><span data-flag="' + esc(view.player.key) +
          '"></span><i>⇄</i><span data-flag="' + esc(op.key) + '"></span><em>暂无</em></div>' +
          '<strong>尚未交换非正式意向</strong><small>可从外交渠道发起沟通</small>';
      }
    }
  }

  function renderTasks(view) {
    if (!view.player) return;
    var details = inScreen('details').filter(function (d) {
      return /隐藏任务/.test((d.querySelector('summary') || {}).textContent || '');
    })[0];
    if (!details && S.mode === 'multi') {
      var panel = one('.right-panel');
      var entry = panel ? $('.analysis-entry', panel) : null;
      if (panel && entry) {
        var wrapper = document.createElement('div');
        wrapper.innerHTML = '<details class="fold-section"><summary>隐藏任务<span>0 / 3</span></summary>' +
          '<div class="fold-placeholder"></div></details>';
        details = wrapper.firstChild;
        panel.insertBefore(details, entry);
      }
    }
    if (!details) return;
    var tasks = view.player.hidden_tasks || [];
    var done = tasks.filter(function (t) { return t.done; }).length;
    var span = details.querySelector('summary span');
    if (span) span.textContent = done + ' / ' + tasks.length;
    var box = details.querySelector('.fold-placeholder');
    if (box) {
      box.innerHTML = (tasks.length ? tasks.map(function (task) {
        return '<div class="live-task' + (task.done ? ' done' : '') + '">' +
          (task.done ? '✓' : '○') + ' ' + esc(task.text) +
          '<small>' + esc(task.done ? ('第 ' + (task.done_round || '?') + ' 轮完成') : (task.priority || '')) +
          '</small></div>';
      }).join('') : '本局没有配置隐藏任务。') +
        '<button type="button" class="live-refresh-tasks" id="liveRefreshTasks">刷新任务进度</button>';
    }
  }

  function renderNarrator(view) {
    /* 只更新当前模式下可见的那张旁白卡 */
    var card = document.querySelector('.mode-screen.active .narrator-card') || one('.narrator-card');
    if (!card) return;
    var narration = view.narrator || {};
    var key = PERSONA[S.persona % PERSONA.length];
    var text = narration[key] || narration.neutral ||
      '本轮尚未开始。选择策略卡并提交，系统会按卡牌生成我方发言；对手的回应、三指数结算与情报信号会显示在这里。';
    var label = (narration.persona_labels && narration.persona_labels[key]) || PERSONA_LABEL[key];
    var labelEl = $('.persona-label', card);
    var p = $('p', card);
    if (labelEl) labelEl.textContent = label;
    if (p) {
      var changed = p.textContent !== text;
      p.innerHTML = esc(text);
      if (changed) {
        p.classList.remove('narrator-flash');
        void p.offsetWidth;
        p.classList.add('narrator-flash');
      }
    }
  }

  function renderSignals(view) {
    var list = $('#signalList');
    if (list) {
      var items = [];
      if (view.risk && view.risk.level && view.risk.level !== 'low') {
        items.push({
          icon: 'intel', tone: 'red', title: '方案研判 · ' + (view.risk.label || ''),
          small: view.risk.message || '', tab: 'intel'
        });
      }
      (view.evidence || []).slice(-2).forEach(function (ev) {
        items.push({
          icon: 'intel', tone: 'amber', title: ev.text,
          small: '情报依据 · ' + (ev.confidence === 'high' ? '高' : ev.confidence === 'mid' ? '中' : '低'),
          tab: 'intel'
        });
      });
      var deal = currentDeal(view);
      if (deal && deal.status !== 'confirmed') {
        items.push({
          icon: 'lock', tone: 'purple',
          title: (deal.initiator === 'npc' ? '对方请求非正式沟通 · ' : '非正式沟通 · ') +
            (deal.status_label || ''),
          small: deal.their_term || '', tab: 'private'
        });
      }
      var _seenForNew = Number((($('#signalSummary') || {}).dataset || {}).seen || 0);
      list.innerHTML = items.slice(0, 3).map(function (item, idx) {
        var isNew = idx >= _seenForNew;
        return '<button class="signal-item" data-open="' + esc(item.tab) + '">' +
          '<i class="signal-icon ' + esc(item.tone) + '"><svg><use href="#i-' + esc(item.icon) +
          '"/></svg></i><span><strong>' + esc(item.title) + '</strong><small>' +
          esc(item.small) + '</small></span>' + (isNew ? '<time>NEW</time>' : '') + '</button>';
      }).join('') || '<div class="fold-placeholder">暂无新信号。</div>';
      var count = $('#signalCount');
      var summary0 = $('#signalSummary');
        var _seenNow = Number((summary0 && summary0.dataset.seen) || 0);
      if (count) {
        var _unread = Math.max(0, Math.min(items.length, 3) - _seenNow);
        count.textContent = _unread ? (_unread + ' 条新信号') : '';
        count.style.display = _unread ? '' : 'none';
      }
    var summary = $('#signalSummary');
      if (summary) {
        var seen = Number(summary.dataset.seen || 0);
        summary.classList.toggle('has-new', items.length > seen);
        if (!summary.dataset.boundSeen) {
          summary.dataset.boundSeen = '1';
          summary.addEventListener('click', function () {
            summary.dataset.seen = String(items.length);
            summary.classList.remove('has-new');
            var c = $('#signalCount');
            if (c) { c.textContent = ''; c.style.display = 'none'; }
          });
          var listEl = $('#signalList');
          if (listEl && !listEl.dataset.boundSeen) {
            listEl.dataset.boundSeen = '1';
            listEl.addEventListener('click', function () {
              summary.dataset.seen = String(items.length);
              summary.classList.remove('has-new');
              var c = $('#signalCount');
              if (c) { c.textContent = ''; c.style.display = 'none'; }
            });
          }
        }
      }
    }

    var mlist = $('#multiSignalList');
    if (mlist) {
      var notices = [];
      var deal2 = currentDeal(view);
      if (deal2 && deal2.status === 'draft') {
        notices.push({ dot: 'purple-dot', title: '非正式沟通邀请待回复', small: deal2.their_term || '', tab: 'private' });
      }
      if (view.risk && view.risk.level && view.risk.level !== 'low') {
        notices.push({ dot: 'amber-dot', title: '方案研判 · ' + (view.risk.label || ''), small: view.risk.message || '', tab: 'intel' });
      }
      if ((view.events || []).length) {
        var ev = view.events[view.events.length - 1];
        notices.push({ dot: 'green-dot', title: ev.title || '会场事件', small: '第 ' + ev.round + ' 轮', tab: 'intel' });
      }
      mlist.innerHTML = notices.map(function (item) {
        return '<button data-open="' + esc(item.tab) + '"><i class="' + esc(item.dot) +
          '"></i><span><strong>' + esc(item.title) + '</strong><small>' +
          esc(item.small) + '</small></span></button>';
      }).join('') || '<button><i class="green-dot"></i><span><strong>暂无新信号</strong><small>继续谈判以获取情报</small></span></button>';
      var msummary = $('#multiSignalSummary');
      var mseen = Number((msummary && msummary.dataset.seen) || 0);
      var mc = $('#multiSignalCount');
      if (mc) {
        var munread = Math.max(0, notices.length - mseen);
        mc.textContent = munread ? (munread + ' 条新信号') : '';
        mc.style.display = munread ? '' : 'none';
      }
      if (msummary) {
        msummary.classList.toggle('has-new', notices.length > mseen);
        if (!msummary.dataset.boundSeen) {
          msummary.dataset.boundSeen = '1';
          msummary.addEventListener('click', function () {
            msummary.dataset.seen = String(notices.length);
            msummary.classList.remove('has-new');
            var c = $('#multiSignalCount');
            if (c) { c.textContent = ''; c.style.display = 'none'; }
          });
        }
      }
    }

    /* 突发事件徽标：只统计本轮真实发生的事件 */
    var evBadge = document.querySelector('#eventDemo span');
    if (evBadge) {
      var evn = (view.events || []).filter(function (e) {
        return Number(view.round) > 0 && Number(e.round) === Number(view.round);
      }).length;
      evBadge.textContent = evn;
      evBadge.style.display = evn ? '' : 'none';
    }
  }

  function renderTimeline(view) {
    var box = one('.mini-timeline');
    if (!box) return;
    var rows = (view.recent_rounds || []).slice(-3).reverse().map(function (r) {
      return '<div><i></i><span><strong>第 ' + esc(r.round) + ' 轮 · ' +
        esc(r.speaker || '') + '</strong><small>' + esc(r.summary || '') + '</small></span></div>';
    });
    if ((view.events || []).length) {
      var ev = view.events[view.events.length - 1];
      rows.push('<div class="muted"><i></i><span><strong>' + esc(ev.title || '突发事件') +
        '</strong><small>第 ' + esc(ev.round) + ' 轮 · 事件卡</small></span></div>');
    }
    box.innerHTML = rows.join('') || '<div class="muted"><i></i><span><strong>尚未开始</strong><small>提交本轮后生成纪要</small></span></div>';
    var details = box.closest ? box.closest('details') : null;
    var count = details ? details.querySelector('summary span') : null;
    if (count) count.textContent = String((view.recent_rounds || []).length + (view.events || []).length);
  }

  // ---------------------------------------------------------------- 多边

  function renderMulti(view) {
    var sc = screen();
    if (!sc) return;
    var list = $('.delegation-list', sc);
    if (list) {
      list.innerHTML = (view.parties || []).map(function (party) {
        var active = party.key === view.speaker;
        return '<button class="delegation ' + (active ? 'active' : '') +
          '" data-open="intel" data-key="' + esc(party.key) + '"><span data-flag="' +
          esc(party.key) + '"></span><div><strong>' + esc(party.label) +
          (party.is_player ? ' · 我方' : '') + '</strong>' +
          (active ? '<small>正在发言</small>' : '') +
          '</div><em class="stance ' + esc((party.stance || {}).position || 'swing') +
          '">' + esc((party.stance || {}).position_label || '') + '</em></button>';
      }).join('');
      var head = document.querySelector('.delegation-head-count') ||
        (sc.querySelector('.panel-heading span'));
      if (head) head.textContent = 'DELEGATIONS · ' + (view.parties || []).length;
    }

    var campSummary = $('.camp-summary', sc);
    var counts = (view.camp || {}).counts || {};
    if (campSummary) {
      campSummary.innerHTML = '<span><i class="support-bg"></i>支持 ' + (counts.support || 0) +
        '</span><span><i class="swing-bg"></i>摇摆 ' + (counts.swing || 0) +
        '</span><span><i class="oppose-bg"></i>反对 ' + (counts.oppose || 0) +
        '</span><svg><use href="#i-chevron"/></svg>';
    }

    renderSeats(sc, view, 'multi-table');
    renderCouncilSpeech(sc, view);

    var camp = $('.camp-preview', sc);
    if (camp) {
      camp.innerHTML = renderCampBody(view);
    }
    renderOpponent(view);
    renderChannel(view);

    var metrics = $('.compact-metrics', sc);
    if (metrics && view.player) {
      var d = (view.last && view.last.deltas && view.last.deltas.player) || {};
      metrics.innerHTML = ['interest', 'image', 'trust'].map(function (key, index) {
        var label = ['主体利益', '国际形象', '盟友信任'][index];
        var delta = d[key + '_delta'] || 0;
        return '<span>' + label + '<strong>' + Math.round(view.player.indexes[key] || 0) +
          ' <small class="' + (delta < 0 ? 'negative' : '') + '">' +
          (delta ? signed(delta) : '') + '</small></strong></span>';
      }).join('');
    }

    renderStrategy(view);
    renderTasks(view);
    renderSignals(view);
    renderTargetChip();
  }

  function partyLine(view, key) {
    var list = (view.messages || []);
    for (var i = list.length - 1; i >= 0; i--) {
      var m = list[i];
      if (m.key !== key) continue;
      var t = String(m.text || '').replace(/\s+/g, '');
      var cut = t.split(/[。；;！!？?]/)[0] || t;
      return cut.slice(0, 14) + (cut.length > 14 ? '…' : '');
    }
    return '';
  }

  var STANCE_CN = { support: '支持', swing: '摇摆', oppose: '反对' };

  function renderSeats(sc, view, tableClass) {
    var table = $('.' + tableClass, sc);
    if (!table) return;
    var surface = $('.table-surface', table);
    var parties = view.parties || [];
    var html = parties.map(function (party, index) {
      var angle = Math.PI + (parties.length === 1 ? Math.PI / 2 : Math.PI * index / (parties.length - 1));
      var x = 50 + 45 * Math.cos(angle);
      var y = 67 + 60 * Math.sin(angle);
      var speaking = party.key === ((S._ownPreview && view.player) ? view.player.key : view.speaker);
      var picked = S.target === party.key && S.mode !== 'observe';
      return '<button class="seat' + (speaking ? ' speaking' : '') + (picked ? ' selected' : '') +
        '" style="--x:' + x.toFixed(2) + '%;--y:' + y.toFixed(2) + '%" data-target-key="' +
        esc(party.key) + '"' + (S.mode === 'observe' ? ' data-open="intel"' : '') + ' data-speech="' +
        esc(party.key) + '"><span data-flag="' + esc(party.key) + '"></span><strong>' +
        esc(party.label) + '</strong><small>' +
      (speaking ? '正在发言' : esc(STANCE_CN[party.stance] || 'STANDBY')) +
      '</small></button>';
    }).join('');
    table.innerHTML = surface ? surface.outerHTML + html : html;
    hydrateFlags(table);
  }

  function renderCouncilSpeech(sc, view, observe) {
    var box = $('.council-speech', sc);
    if (!box) return;
    var all = (view.messages || []);
    var lastAny = all[all.length - 1];
    var ownPreview = (!observe && S._ownPreview && Number(S._ownPreview.round) === Number(view.round))
      ? S._ownPreview : null;
    var isOwn = !!ownPreview || (!observe && lastAny && lastAny.role === 'player');
    /* 我方刚发完言：先把我方那段显示成独立气泡，20 秒后由下一位 NPC 替换 */
    var messages = isOwn ? [ownPreview || lastAny]
      : all.filter(function (m) { return m.role !== 'player'; });
    var message = messages[messages.length - 1];
    box.classList.toggle('is-system', !message);
    box.classList.remove('is-pending');
    if (!message) {
      box.innerHTML = '<div class="broadcast-avatar" aria-hidden="true"><svg viewBox="0 0 24 24">' +
        '<path d="M13 2 4 14h7l-1 8 10-13h-7z"/></svg></div>' +
        '<div class="council-speech-body"><div class="speech-meta"><strong>会议播报 ' +
        '<small class="broadcast-system">SYSTEM</small></strong><span>WAITING</span><em>' +
        (observe ? 'AUTO' : 'LIVE') + '</em></div><p>谈判开始 · 请陈述立场</p></div>';
      return;
    }

    var stance = message.stance ? (STANCE[message.stance] || '') : '';
    var claimText = claimLabel(message);
    var played = claimText || playedLabel(message);
    var truth = (S.state && S.state.full && message.cards && message.cards.length)
      ? '（实际：' + playedLabel(message) + '）' : '';
    var fact = (view.last && view.last.fact_check) || {};
    var factHtml = (fact.flagged && fact.flagged.length)
      ? '<div class="advisor-reading live-factcheck"><span>事实核查</span>' +
        esc(fact.flagged.slice(0, 2).map(function (item) {
          return (item.token || '') + '：' + (item.reason || '与知识库不一致');
        }).join('；')) + '</div>'
      : '';
    var detail = '';
    if (observe) {
      var op = view.opponent || {};
      var canSeeOs = !op.inner_os_limited;
      detail = '<div class="inner-os' + (canSeeOs ? '' : ' limited') + '" id="innerOs"><span>内心 OS</span>' +
        '<p id="observeOs">' + esc(canSeeOs ? (op.inner_os || '（本轮没有可读取的内心 OS）') :
          '无法读取该代表团的未公开动机。切换到全知视角后可查看。') + '</p>' +
        '<button id="expandOs">展开</button></div><div class="fact-source">推演记录 · 第 ' +
        esc(message.round) + ' 轮 · ' + esc(view.last && view.last.summary || '') + '</div>';
    } else {
      var ownMessages = (view.messages || []).filter(function (m) {
        return m.role === 'player' && Number(m.round) === Number(message.round);
      });
      var own = ownMessages[ownMessages.length - 1];
      var ownHtml = own ? '<div class="council-own-speech"><span>我方本轮发言</span><p>' +
        rich(own.text) + '</p></div>' : '';
      detail = '<div class="position-change">真实动机尚需情报确认' +
        '<button data-open="intel">查看情报</button></div>';
    }
    box.innerHTML = '<div class="speech-avatar" data-flag="' + esc(message.speaker) +
      '"></div><div class="council-speech-body"><div class="speech-meta"><strong>' +
      esc(message.label) + (isOwn ? ' · 我方' : '') +
      '</strong><span>第 ' + esc(message.round) + ' 轮 · ' + (isOwn ? '我方发言' : '正在发言') + '</span>' +
      addrChip(message) + '<em>' +
      esc(played || stance || '公开发言') + esc(truth) + '</em></div><p>' + hl(message.text) + '</p>' + factHtml + detail + '</div>';
    box.classList.remove('broadcast-swap');
    void box.offsetWidth;
    box.classList.add('broadcast-swap');
  }

  function renderCampBody(view) {
    var counts = (view.camp || {}).counts || {};
    var total = Math.max(1, (counts.support || 0) + (counts.swing || 0) + (counts.oppose || 0));
    var changed = (view.camp || {}).changed || [];
    var rows = (view.camp || {}).rows || [];
    var html = '<div class="camp-overview"><div class="support"><strong>' + (counts.support || 0) +
      '</strong><span>支持</span></div><div class="swing"><strong>' + (counts.swing || 0) +
      '</strong><span>摇摆</span></div><div class="oppose"><strong>' + (counts.oppose || 0) +
      '</strong><span>反对</span></div></div>' +
      '<div class="camp-bar"><i style="width:' + (counts.support || 0) / total * 100 +
      '%"></i><i style="width:' + (counts.swing || 0) / total * 100 +
      '%"></i><i style="width:' + (counts.oppose || 0) / total * 100 + '%"></i></div>';
    html += '<div class="evidence-list"><div class="content-subtitle">各方公开立场<span>点击席位可查看</span></div>' +
      rows.map(function (row) {
        return '<div class="alignment-row"><span data-flag="' + esc(row.key) +
          '"></span><div><strong>' + esc(row.label) + '</strong><small>' +
          esc(row.reason || '') + '</small></div><em class="stance ' +
          esc(row.position) + '">' + esc(row.position_label) + '</em></div>';
      }).join('') + '</div>';
    html += '<div class="limit-note"><strong>变化提醒：</strong>' +
      (changed.length ? changed.map(function (c) {
        return c.key + ' ' + (STANCE[c.from] || c.from) + ' → ' + (STANCE[c.to] || c.to);
      }).join('；') : '本轮阵营没有发生变化。') + '</div>';
    return html;
  }

  // ---------------------------------------------------------------- 观战

  function renderObserve(view) {
    var sc = screen();
    if (!sc) return;
    renderSeats(sc, view, 'observe-table');
    renderCouncilSpeech(sc, view, true);

    var monitor = $('.party-monitor', sc);
    if (monitor) {
      var rows = ['<div class="party-head"><span>代表团</span><b>利</b><b>形</b><b>信</b></div>'];
      (view.parties || []).forEach(function (party) {
        var idx = party.indexes || {};
        var range = (party.indexes_range || {}).interest;
        var interest = party.exact ? Math.round(idx.interest || 0) : (range ? range[0] + '–' + range[1] : '?');
        var image = party.exact ? Math.round(idx.image || 0) : (party.public_image != null ? Math.round(party.public_image) : '?');
        var trust = party.exact ? Math.round(idx.trust || 0) : '?';
        rows.push('<div class="' + (party.key === view.speaker ? 'speaking-row' : '') +
          '"><span><i data-flag="' + esc(party.key) + '"></i>' + esc(party.label) +
          '</span><b>' + interest + '</b><b>' + image + '</b><b>' + trust + '</b></div>');
      });
      monitor.innerHTML = rows.join('');
    }

    var camp = $('.observe-camp', sc);
    if (camp) camp.innerHTML = renderCampBody(view);

    renderPerspectiveUI(view);
    renderDarkRadar(view);
    renderSignals(view);

    var status = $('#playStatus');
    if (status) {
      status.textContent = view.finished ? '推演已结束'
        : (window.NegotiationEventCard && window.NegotiationEventCard.isOpen())
          ? '事件卡打开 · 推演已暂停'
          : (S.auto ? '自动推演中' : '手动逐条播放');
    }
    var auto = $('#autoButton');
    if (auto) {
      auto.classList.toggle('active', S.auto);
      auto.textContent = S.auto ? 'AUTO' : 'MANUAL';
    }
  }

  function renderPerspectiveUI(view) {
    var full = !!view.full;
    var followed = (view.parties || []).filter(function (p) { return p.key === S.follow; })[0] || {};
    var status = $('#perspectiveStatus');
    if (status) status.textContent = full ? '全知' : ('跟随 · ' + (followed.label || S.follow));
    var picker = $('#partyPicker');
    if (picker) picker.hidden = full;
    var select = $('#partySelect');
    if (select) {
      select.innerHTML = (view.parties || []).map(function (party) {
        return '<option value="' + esc(party.key) + '"' +
          (party.key === S.follow ? ' selected' : '') + '>' + esc(party.label) + '</option>';
      }).join('');
    }
    var explain = $('#perspectiveExplain');
    if (explain) {
      explain.textContent = full
        ? '可查看全部 NPC 动机、内部指数与虚构暗线 · 非史实'
        : '仅显示该方知道的信息 · 其他方为公开信息、估计或未知';
    }
    $$('[data-perspective]').forEach(function (button) {
      button.classList.toggle('active', button.getAttribute('data-perspective') === S.perspective);
    });
    var app = $('#app');
    if (app) app.classList.toggle('is-following', S.mode === 'observe' && !full);
  }

  function renderDarkRadar(view) {
    var box = $('#darkRadar');
    if (!box) return;
    var badge = $('#darkRadarBadge');
    var deals = (view.deals || []).filter(function (d) { return d.fictional; });
    var nodes = [];   /* 暗线雷达只列闭门会谈，非公开意向在谈判树里看 */
    var items = [];
    var seenDeal = {};
    deals.forEach(function (deal) {
      var fp = (deal.participants || [deal.party]).slice().sort().join('>') + '|' + (deal.their_term || '');
      if (seenDeal[fp]) return;
      seenDeal[fp] = 1;
      var pair = (deal.participants && deal.participants.length >= 2)
        ? deal.participants
        : [deal.party, (view.player ? view.player.key : 'cn')];
      items.push('<button class="secret-event" data-open="private"><div><span data-flag="' +
        esc(pair[0]) + '"></span><i>······</i><span data-flag="' +
        esc(pair[1]) + '"></span></div><strong>假想闭门会谈 · 非史实</strong>' +
        '<p>' + esc(deal.our_term || '') + ' ⇄ ' + esc(deal.their_term || '') +
        '</p><small>查看假想暗线与边界 →</small></button>');
    });
    var dealTerms = deals.map(function (d) { return (d.our_term || '') + (d.their_term || ''); }).join(' ');
    var seenNode = {};
    nodes.forEach(function (node) {
      var claim = (node.claim || '').trim();
      if (claim && dealTerms.indexOf(claim) >= 0) return;
      if (seenNode[claim]) return;
      seenNode[claim] = 1;
      items.push('<button class="secret-event secondary" data-open="tree"><div><span data-flag="' +
        esc(node.speaker) + '"></span><i>······</i></div><strong>' +
        esc(node.speaker_label) + ' · 非公开意向</strong><p>' + hl(node.claim) +
        '</p><small>' + esc(node.fictional_label || '虚构 · 非史实') + '</small></button>');
    });
    if (badge) badge.textContent = view.full ? '虚构 · 非史实' : '本方暗线 · 虚构';
    if (!items.length) {
      items.push('<div class="fold-placeholder">当前视角没有可见的虚构暗线。' +
        (view.full ? '' : '切换到全知视角或参与方视角后可查看。') + '</div>');
    }
    box.innerHTML = '<summary>暗线雷达<span class="purple-text" id="darkRadarBadge">' +
      (view.full ? '虚构 · 非史实' : '本方暗线 · 虚构') + '</span></summary>' + items.join('');
  }

  // ---------------------------------------------------------------- 抽屉

  function heading(kicker, title, desc) {
    return '<div class="drawer-section-kicker">' + esc(kicker) + '</div>' +
      '<h3 class="drawer-section-title">' + esc(title) + '</h3>' +
      '<p class="drawer-section-desc">' + esc(desc) + '</p>';
  }

  function intelTemplate(view) {
    if (view.mode === 'observe' && !view.full) {
      return heading('LIMITED PERSPECTIVE', '该视角无法读取完整底线',
        '正在跟随一方：以下是公开表态与情报推断，不显示其他方的真实内部设定。') +
        '<div class="history-boundary"><strong>未知 / NOT VISIBLE</strong><p>' +
        '切换到全知视角后，才可查看完整底线、内心 OS 与虚构暗线。</p></div>';
    }
    var intel = view.intel || {};
    var risk = view.risk || {};
    var html = heading('BOTTOM-LINE INTELLIGENCE', '底线研判',
      view.mode === 'observe'
        ? '全知观战视角中的真实策略区间；公开文本仍按史料生成。'
        : '你看到的是基于公开表态与试探结果形成的情报推断，不是 NPC 的真实配置。');
    if (risk.level && risk.level !== 'low') {
      html += '<div class="intel-warning"><span>!</span><div><strong>' +
        esc(risk.label || '') + '</strong><p>' + esc(risk.message || '') + '</p></div></div>';
    }
    html += '<div class="zone-list">';
    (intel.zones || []).forEach(function (zone) {
      html += '<div class="zone-item ' + esc(zone.kind === 'sensitive' ? 'sensitive' :
        zone.kind === 'redline' ? 'redline' : '') + '"><div class="zone-label"><i></i>' +
        esc(zone.label) + '</div><div><strong>' + esc(zone.item) + '</strong><small>' +
        esc(zone.note || '') + '</small></div><span class="confidence">' +
        esc(zone.confidence_label || '') + '</span></div>';
    });
    html += '</div><div class="evidence-list"><div class="content-subtitle">情报依据<span>' +
      (intel.evidence_count || 0) + ' 条 · 准确度 ' + (intel.accuracy || 0) + '</span></div>';
    var evidence = view.evidence || [];
    if (!evidence.length) {
      html += '<div class="fold-placeholder">还没有拿到可用情报。使用「澄清核查边界」「事实援引」或「私下探底」可以累积证据。</div>';
    } else {
      evidence.slice(-4).reverse().forEach(function (ev) {
        html += '<div class="evidence-row"><span>第 ' + esc(ev.round) + ' 轮</span><div><strong>' +
          esc(ev.text) + '</strong><p>' + esc(ev.source || '发言') + ' · 可信度 ' +
          esc(ev.confidence === 'high' ? '高' : ev.confidence === 'mid' ? '中' : '低') +
          '</p></div></div>';
      });
    }
    html += '</div><div class="limit-note"><strong>限知提示：</strong>推断可能出错。新的发言、试探结果与事件会更新区间和可信度，但不会直接暴露 NPC 的隐藏配置。</div>';
    var ledger = view.intel_ledger || [];
    if (ledger.length) {
      html += '<div class="evidence-list"><div class="content-subtitle">情报账本<span>只有你看得见</span></div>';
      ledger.forEach(function (item) {
        var status = item.status === 'sold' ? '已卖出'
          : item.status === 'hinted' ? '已放风'
            : item.status === 'public' ? '已公开' : '待用';
        var buyer = S.target
          ? ((view.parties || []).filter(function (p) { return p.key === S.target; })[0] || {}).label
          : '对手';
        html += '<div class="intel-entry"><div><strong>' + esc(item.target_label) +
          ' · 第 ' + esc(item.round) + ' 轮</strong><em>' + esc(status) + '</em></div>' +
          '<p>嘴上是「' + esc(item.claim_label) + '」，实际是「' + esc(item.real_label) +
          '」 · 可信度 ' + Math.round(Number(item.credibility || 0) * 100) + '%</p>' +
          '<div class="intel-actions">' +
          '<button data-intel-action="hint" data-intel-id="' + esc(item.id) + '">放风</button>' +
          '<button data-intel-action="sell" data-intel-id="' + esc(item.id) + '">卖给' +
          esc(buyer || '对手') + '</button>' +
          '<button data-intel-action="expose" data-intel-id="' + esc(item.id) + '">当众揭穿</button>' +
          '</div></div>';
      });
      html += '</div>';
    }
    return html;
  }

  function campTemplate(view) {
    return heading('ISSUE-BASED COALITIONS', '议题阵营',
      '阵营只描述各方在当前议题上的公开立场，不等同于固定盟友或双边亲和关系。') +
      renderCampBody(view);
  }

  function relationValue(cell, type) {
    if (!cell || cell.kind === 'diagonal') return { text: '—', cls: 'diagonal', alpha: 0 };
    if (!cell.values) return { text: '?', cls: 'unknown', alpha: 0 };
    var value = cell.values[type];
    if (!value) return { text: '?', cls: 'unknown', alpha: 0 };
    if (value.kind === 'unknown') return { text: '?', cls: 'unknown', alpha: 0 };
    if (value.kind === 'exact') {
      return { text: String(value.value), cls: 'exact',
        alpha: Math.min(0.85, 0.08 + Number(value.value) / 150) };
    }
    var mid = (Number(value.range[0]) + Number(value.range[1])) / 2;
    return { text: value.range[0] + '–' + value.range[1], cls: 'estimate',
      alpha: Math.min(0.7, 0.06 + mid / 170) };
  }

  function matrixTemplate(view) {
    var rel = view.relations || {};
    var parties = rel.parties || [];
    var labels = rel.labels || parties;
    var cells = rel.cells || [];
    var type = S.matrix;
    var selected = S.relation ? S.relation.split(':') : [parties[0], parties[1]];
    var typeName = { affinity: '亲和度', hostility: '敌意度', trust: '信任度' }[type];
    var html = heading('DIRECTED RELATION MATRIX', '有向双边关系矩阵',
      rel.full ? '全知视角显示内部评估真值。行表示观察方，列表示被评估方。'
        : '参与模式只显示情报区间与未知项，不公开其他方内部真值。行表示观察方，列表示被评估方。');
    html += '<div class="matrix-controls">' +
      ['affinity', 'hostility', 'trust'].map(function (key) {
        return '<button data-matrix="' + key + '" class="' + (type === key ? 'active' : '') +
          '">' + (key === 'affinity' ? '亲和' : key === 'hostility' ? '敌意' : '信任') + '</button>';
      }).join('') + '</div>';
    html += '<table class="relation-matrix"><thead><tr><th></th>' +
      labels.map(function (label) { return '<th>' + esc(String(label).slice(0, 2)) + '</th>'; }).join('') +
      '</tr></thead><tbody>';
    parties.forEach(function (src, rowIndex) {
      html += '<tr><th>' + esc(String(labels[rowIndex] || src).slice(0, 2)) + '</th>';
      parties.forEach(function (dst) {
        if (src === dst) { html += '<td class="diagonal">—</td>'; return; }
        var cell = cells.filter(function (c) { return c.src === src && c.dst === dst; })[0];
        var val = relationValue(cell, type);
        html += '<td data-relation="' + esc(src + ':' + dst) + '" class="' + esc(type) + ' ' + val.cls +
          '" style="--alpha:' + (val.alpha || 0).toFixed(2) + '" title="' +
          esc(labels[parties.indexOf(src)] + ' → ' + labels[parties.indexOf(dst)]) +
          '">' + esc(val.text) + '</td>';
      });
      html += '</tr>';
    });
    html += '</tbody></table><div class="matrix-legend"><span>低 0</span><span>' + typeName +
      ' · ' + (rel.full ? '内部真值' : '区间估计') + '</span><span>100 高</span></div>';

    var cell = cells.filter(function (c) {
      return c.src === selected[0] && c.dst === selected[1];
    })[0];
    var val = relationValue(cell, type);
    html += '<div class="relation-detail"><div><span data-flag="' + esc(selected[0]) +
      '"></span><strong>' + esc((labels[parties.indexOf(selected[0])] || selected[0]) + ' → ' +
        (labels[parties.indexOf(selected[1])] || selected[1])) + '</strong><span data-flag="' +
      esc(selected[1]) + '"></span></div><p>当前' + typeName + '为 <b>' + esc(val.text) +
      '</b>。' + (type === 'affinity' ? '共同议题支持与近期合作提高亲和，但不会自动降低敌意。'
        : type === 'hostility' ? '红线冲突与公开施压提高敌意；即使仍有合作，也可能同时保持高亲和。'
          : '该指标主要由承诺、履约与被知悉的违约驱动。') +
      '</p><small>' + (rel.full ? '全知视角 · 内部评估真值' : '情报估计 · 可能随新证据调整') +
      '</small></div>';
    return html;
  }

  function privateTemplate(view) {
    var op = view.opponent || {};
    var policies = view.channel_policies || [];
    var playerKey = view.player ? view.player.key : ((view.parties || [])[0] || {}).key;
    var html = heading('DIPLOMATIC CHANNEL ACCESS', '本场景外交渠道与保密边界',
      '准入由主体、议题、场景授权、双边关系和保密形式共同决定。玩家能发起沟通，不代表 NPC 必须接受。');
    html += '<div class="channel-ladder">';
    (view.channel && view.channel.ladder || []).forEach(function (item) {
      html += '<div class="' + esc(item.state) + '"><span>' + esc(item.no) + '</span><div><strong>' +
        esc(item.name) + '</strong><small>' + esc(item.desc) + '</small></div><em>' +
        esc(item.note) + '</em></div>';
    });
    html += '</div>';
    if (view.mode !== 'bilateral' && policies.length) {
      html += '<div class="party-policies"><div class="content-subtitle">各方接受条件<span>不是国家永久属性</span></div>';
      policies.forEach(function (policy) {
        if (policy.key === playerKey) return;
        var cls = policy.policy === 'open' ? 'channel-ok' : policy.policy === 'restricted' ? 'channel-condition' : 'channel-closed';
        html += '<div><span data-flag="' + esc(policy.key) + '"></span><strong>' +
          esc(policy.label) + '</strong><small>' + esc(policy.reason || policy.disclosure) +
          '</small><em class="' + cls + '">' + esc(policy.policy_label) + '</em></div>';
      });
      html += '</div>';
    }
    if (view.player && policies.length) {
      html += '<div class="live-invite-list"><div class="content-subtitle">主动发起非正式沟通<span>对方可以拒绝</span></div>';
      policies.forEach(function (policy) {
        if (policy.key === playerKey) return;
        html += '<button type="button" data-invite-key="' + esc(policy.key) + '">' +
          esc(policy.label) + ' · ' + esc(policy.policy_label) + '</button>';
      });
      html += '</div>';
    }
    var deal = currentDeal(view);
    if (deal) {
      html += '<div class="drawer-deal informal"><div class="drawer-deal-head"><span data-flag="' +
        esc(playerKey) + '"></span><i>······</i><span data-flag="' + esc(deal.party) +
        '"></span><em>' + esc(deal.status_label) + '</em></div><h3>' +
        esc(deal.our_term) + ' ⇄ ' + esc(deal.their_term) + '</h3><p>' +
        esc(deal.status === 'intent' ? '意向已记录，但尚未产生收益。用正式卡牌公开确认后才结算。'
          : deal.status === 'confirmed' ? '已通过正式卡牌公开确认，收益已结算。'
            : '这是一份非约束性意向草案。接受不产生收益，也不形成秘密约束。') +
        '</p><button id="drawerEnterPrivate">进入非正式沟通 →</button></div>';
    } else {
      html += '<div class="drawer-deal informal"><div class="drawer-deal-head"><span data-flag="' +
        esc(playerKey) + '"></span><i>······</i><span data-flag="' + esc(op.key) +
        '"></span><em>暂无草案</em></div><h3>还没有非正式意向</h3><p>' +
        '可以先发起沟通，交换非约束性意向；任何承诺都须公开确认。</p>' +
        '<button id="drawerEnterPrivate">发起非正式沟通 →</button></div>';
    }
    html += '<div class="deal-flow"><span class="active"><b>1</b>发起沟通</span><i></i>' +
      '<span class="active"><b>2</b>交换意向</span><i></i>' +
      '<span class="' + (deal && deal.status !== 'draft' ? 'active' : '') + '"><b>3</b>接受意向</span><i></i>' +
      '<span class="' + (deal && deal.status === 'confirmed' ? 'active' : '') + '"><b>4</b>公开确认</span><i></i>' +
      '<span><b>5</b>结算</span></div>';
    html += '<div class="limit-note"><strong>公开路线可达成同等结局：</strong>正式议题捆绑、分阶段协议与第三方调解不依赖秘密外交。拒绝密谈不会使玩家失去胜利路径。</div>';
    if (view.mode !== 'observe') {
      html += '<button class="live-secret" id="liveSecret">申请完全秘密附件（将被拒绝）</button>';
    }
    return html;
  }

  /* 观战：谈判树是否显示暗线 */
  function secretTreeOn() {
    try { return localStorage.getItem('neg-tree-secret') === '1'; } catch (e) { return false; }
  }
  function setSecretTree(on) {
    try { localStorage.setItem('neg-tree-secret', on ? '1' : '0'); } catch (e) {}
  }

  function _labelOf(key) {
    var list = (S.state && S.state.parties) || [];
    for (var i = 0; i < list.length; i++) {
      if (list[i].key === key) return list[i].label || key;
    }
    return key;
  }

  function treeTemplate(view) {
    var tree = view.tree || {};
    var nodes = tree.nodes || [];
    var html = heading('ARGUMENT & NONPUBLIC CAUSALITY', '公开论点与非公开因果',
      '实线＝公开回应，虚线＝非公开意向；暗线为虚构演示，公开确认后才生效。');
    var observeMode = view.mode === 'observe';
    var showSecret = !observeMode || secretTreeOn();
    if (observeMode && !showSecret) {
      nodes = nodes.filter(function (n) { return n.kind !== 'nonpublic'; });
    }
    html += '<div class="tree-controls"><span>第 ' + (view.round || 0) + ' 轮 · ' +
      (view.topic_id === 'unclos' ? '群岛与海峡' : '利益交换') +
      '</span><span class="live-tree-count">' + nodes.length + ' 个节点</span></div>' +
      (observeMode
        ? '<div class="tree-secret-row"><span>暗线渠道</span>' +
          '<button type="button" class="secret-toggle' + (showSecret ? ' on' : '') +
          '" id="treeSecretToggle" aria-pressed="' + (showSecret ? 'true' : 'false') + '">' +
          '<i></i><em>' + (showSecret ? '关闭暗线' : '开启暗线') + '</em></button></div>'
        : '');
    html += '<div class="negotiation-tree">';
    if (!nodes.length) {
      html += '<div class="fold-placeholder">还没有谈判树节点。提交一轮发言后会自动生成。</div>';
    } else {
      nodes.slice(-24).forEach(function (node) {
        var secret = node.kind === 'nonpublic';
        var vis = node.visibility || [];
        var flags = secret && vis.length >= 2
          ? '<span data-flag="' + esc(vis[0]) + '"></span><i class="tree-pair">→</i>' +
            '<span data-flag="' + esc(vis[1]) + '"></span>'
          : '<span data-flag="' + esc(node.speaker) + '"></span>';
        var titleTxt = secret && vis.length >= 2
          ? (esc(_labelOf(vis[0])) + ' × ' + esc(_labelOf(vis[1])) + ' · 暗线')
          : (esc(node.speaker_label) + ' · ' + esc(node.kind_label));
        html += '<div class="tree-node' + (secret ? ' secret' : '') +
          (node.responds_to ? '' : ' root') + '" data-tree-round="' + esc(node.round) +
          '" data-tree-speaker="' + esc(node.speaker) + '"><div class="tree-card"><div>' + flags +
          '<strong>' + titleTxt + '</strong><em>' + (secret ? '虚构 · 非史实' : '公开') +
          '</em></div><p>' + hl(node.claim) + '</p><small>第 ' + esc(node.round) +
          ' 轮' + (node.basis && node.basis.length ? ' · ' + esc(node.basis[0]) : '') +
          '</small></div></div>';
      });
    }
    html += '<div class="limit-note">实线＝公开回应，虚线＝非公开意向；观战暗线为虚构演示。</div>';
    return html;
  }

  function openDrawer(tab) {
    if (S.mode === 'bilateral' && tab === 'camp') tab = 'intel';
    S.tab = tab || 'intel';
    $$('#drawerTabs button').forEach(function (button) {
      button.classList.toggle('active', button.getAttribute('data-tab') === S.tab);
    });
    renderDrawer();
    $('#analysisDrawer').classList.add('open');
    $('#analysisDrawer').setAttribute('aria-hidden', 'false');
    $('#drawerBackdrop').classList.add('open');
  }

  function closeDrawer() {
    $('#analysisDrawer').classList.remove('open');
    $('#analysisDrawer').setAttribute('aria-hidden', 'true');
    $('#drawerBackdrop').classList.remove('open');
  }

  function renderDrawer() {
    var view = S.state;
    var box = $('#drawerContent');
    if (!view || !box) return;
    var html = '';
    if (S.tab === 'intel') html = intelTemplate(view);
    else if (S.tab === 'camp') html = campTemplate(view);
    else if (S.tab === 'matrix') html = matrixTemplate(view);
    else if (S.tab === 'private') html = privateTemplate(view);
    else if (S.tab === 'tree') html = treeTemplate(view);
    else html = intelTemplate(view);
    box.innerHTML = html;
    hydrateFlags(box);
  }

  // ---------------------------------------------------------------- 密约

  async function startInvite(key) {
    if (S.busy || !key) return;
    closeDrawer();
    setBusy(true, '正在发起非正式沟通…');
    try {
      var res = await api('/deal', {
        action: 'invite', key: key,
        perspective: S.perspective, follow: S.follow
      });
      S.state = res.view;
      applyView(res.view);
      toast(res.message || '对方已接受沟通请求');
      renderPrivate((res.result && res.result.deal) || currentDeal(S.state));
      var modal = $('#privateModal');
      modal.classList.add('open');
      modal.setAttribute('aria-hidden', 'false');
    } catch (e) {
      toast(e.message || '对方婉拒了非正式沟通');
    } finally {
      setBusy(false);
    }
  }

  async function openPrivate(skipInvite) {
    var view = S.state;
    if (!view) return;
    var deal = currentDeal(view);
    if (!deal && !skipInvite && S.mode !== 'observe') {
      try {
        var res = await api('/deal', {
          action: 'invite', key: (view.opponent && view.opponent.key) || '',
          perspective: S.perspective, follow: S.follow
        });
        S.state = res.view;
        applyView(res.view);
        toast(res.message || '已发起非正式沟通');
        deal = (res.result && res.result.deal) || currentDeal(S.state);
      } catch (e) {
        toast(e.message || '对方暂不接受非正式沟通');
        return;
      }
    }
    renderPrivate(deal);
    var modal = $('#privateModal');
    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
  }

  function closePrivate() {
    var modal = $('#privateModal');
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
  }

  function renderPrivate(deal) {
    var view = S.state;
    if (!view) return;
    var op = view.opponent || {};
    var partyLabel = (deal && (deal.party_label || deal.party)) || op.label || '对方';
    var fictional = S.mode === 'observe';
    var npcInitiated = !!(deal && deal.initiator === 'npc');
    var playerLabel = (view.player && view.player.label) || '我方';
    $('#privateKicker').textContent = fictional
      ? 'HYPOTHETICAL BACKCHANNEL'
      : (npcInitiated ? 'INFORMAL INVITATION' : 'INFORMAL CONSULTATION');
    $('#privateTitle').textContent = fictional
      ? '假想暗线 · ' + playerLabel + ' × ' + partyLabel
      : (npcInitiated
        ? partyLabel + '代表团请求非正式沟通'
        : '非正式沟通 · 与' + partyLabel + '代表团');
    $('#privateSubtitle').textContent = fictional
      ? '非历史事实 · 仅用于展示秘密外交机制与公开因果差异'
      : (npcInitiated
        ? '对方主动提出私下交换意向；接受不产生收益，任何承诺须公开确认'
        : '你发起的沟通已获对方接受；可交换非约束性意向，任何承诺须公开确认');
    $('#privateSpeaker').textContent = partyLabel + '代表团';
    var selfName = (view.player && view.player.label) || '我方';
    var selfEl = document.querySelector('.private-message.self strong');
    if (selfEl) selfEl.textContent = selfName + '代表团 · 我方';
    (function () {
      var _k = (deal && deal.party) || op.key || 'us';
      var _p = (view.player && view.player.key) || 'cn';
      var _o = document.querySelector('.private-message:not(.self) [data-flag]');
      var _m = document.querySelector('.private-message.self [data-flag]');
      if (_o) { _o.setAttribute('data-flag', _k); _o.removeAttribute('data-flag-done'); }
      if (_m) { _m.setAttribute('data-flag', _p); _m.removeAttribute('data-flag-done'); }
      hydrateFlags(document);
    })();
    $('#privateMessage').textContent = fictional
      ? '【假想】这是一条用于演示秘密外交机制的暗线，不是史料记载的密约。'
      : (npcInitiated
        ? '我方希望就当前议题私下交换一些非约束性意向。贵方可以接受、拒绝，或先记录草案；任何承诺仍须在正式会场公开确认。'
        : '我方已接受贵方的非正式沟通请求。可以先把可交换的对价记录成草案，但不会接受绕过正式会场的秘密约束。');
    $('#annexLabel').textContent = fictional ? 'FICTIONAL ANNEX · 01' : 'INFORMAL DRAFT · 01';
    $('#annexTitle').textContent = fictional ? '假想秘密附件' : '非正式意向草案';
    $('#dealStatus').textContent = deal ? deal.status_label : '暂无草案';
    $('#ourTerm').textContent = deal ? deal.our_term : '尚未提出';
    $('#theirTerm').textContent = deal ? deal.their_term : '尚未提出';
    $('#ourTermNote').textContent = fictional ? '假想推演 · 非史实' : '仅记录意向 · 须进入正式提案';
    $('#theirTermNote').textContent = fictional ? '用于演示公开投票履约' : '公开确认与最终投票均须履约';
    $('#privacyText').textContent = fictional
      ? '全知观战 · 虚构内容不进入「册载」与史实依据'
      : '受限保密 · 须向授权团队或调解方备案';
    $('#secrecyLabel').textContent = fictional ? '内容性质' : '披露要求';
    $('#secrecyValue').textContent = fictional ? '虚构推演 · 非史实' : ((deal && deal.disclosure) || '须备案');
    $('#secrecyRisk').textContent = fictional ? '仅机制演示' : '不进入公开直播';
    $('#dealRuleText').textContent = fictional
      ? '本弹层仅演示「接受—履约—结算」的机制，不证明相关国家在真实历史中签署过此类协议。'
      : '接受意向不立即产生收益，也不形成秘密约束。使用正式卡牌确认后，才结算利益与信任。';

    var accept = $('#acceptDeal');
    var modify = $('#modifyDeal');
    if (!deal) {
      accept.disabled = true;
      accept.textContent = '暂无待处理意向';
      accept.dataset.action = '';
    } else if (fictional) {
      accept.disabled = true;
      accept.textContent = '观战模式 · 仅可查看';
      accept.dataset.action = '';
    } else if (deal.status === 'draft') {
      accept.disabled = false;
      accept.textContent = '接受非正式意向';
      accept.dataset.action = 'accept';
    } else if (deal.status === 'intent') {
      accept.disabled = false;
      accept.textContent = '公开确认（需正式卡牌）';
      accept.dataset.action = 'confirm';
    } else if (deal.status === 'confirmed') {
      accept.disabled = true;
      accept.textContent = '已公开确认 · 已结算';
      accept.dataset.action = '';
    } else {
      accept.disabled = true;
      accept.textContent = deal.status_label || '已失效';
      accept.dataset.action = '';
    }
    if (modify) modify.style.display = fictional || !deal ? 'none' : '';
    var returnBtn = $('#returnPublic');
    if (returnBtn) {
      var canDecline = !fictional && npcInitiated && deal && deal.status === 'draft';
      returnBtn.textContent = canDecline ? '暂不回应 · 婉拒' : '返回公开会场';
      returnBtn.dataset.decline = canDecline ? '1' : '';
    }
    hydrateFlags($('#privateModal'));
  }

  async function dealAction(action, extra) {
    var view = S.state;
    if (!view) return;
    var deal = currentDeal(view);
    var key = (view.opponent && view.opponent.key) || '';
    var body = {
      action: action,
      key: key,
      deal_id: deal ? deal.id : null,
      perspective: S.perspective,
      follow: S.follow
    };
    Object.keys(extra || {}).forEach(function (k) { body[k] = extra[k]; });
    try {
      var res = await api('/deal', body);
      S.state = res.view;
      applyView(res.view);
      toast(res.message || '操作完成');
      if (action === 'decline') closePrivate();
      else renderPrivate(currentDeal(S.state));
    } catch (e) {
      toast(e.message || '操作未完成');
    }
  }

  // ---------------------------------------------------------------- 推演

  function animateSelectedCards() {
    var target = one(S.mode === 'bilateral' ? '.dialogue-scroll' : '.council-speech');
    if (!target || !target.getBoundingClientRect) return;
    var targetRect = target.getBoundingClientRect();
    var stage = one('.main-stage');
    if (stage) {
      stage.classList.remove('card-play-receiving');
      void stage.offsetWidth;
      stage.classList.add('card-play-receiving');
      setTimeout(function () { stage.classList.remove('card-play-receiving'); }, 800);
    }
    $$('.strategy-card.selected', screen()).forEach(function (card, index) {
      var rect = card.getBoundingClientRect();
      var clone = card.cloneNode(true);
      clone.className = 'strategy-card strategy-card-flight';
      clone.removeAttribute('disabled');
      clone.style.left = rect.left + 'px';
      clone.style.top = rect.top + 'px';
      clone.style.width = rect.width + 'px';
      clone.style.height = rect.height + 'px';
      clone.style.transitionDelay = (index * 70) + 'ms';
      document.body.appendChild(clone);
      var dx = targetRect.left + targetRect.width / 2 - (rect.left + rect.width / 2);
      var dy = targetRect.top + targetRect.height / 2 - (rect.top + rect.height / 2);
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          clone.style.transform = 'translate(' + dx + 'px,' + dy + 'px) scale(.22) rotate(' +
            (index % 2 ? 5 : -5) + 'deg)';
          clone.style.opacity = '0';
        });
      });
      setTimeout(function () { if (clone.parentNode) clone.parentNode.removeChild(clone); }, 950);
    });
  }

  function responsePendingHTML(label) {
    return '<div class="response-pending" id="liveResponsePending" role="status">' +
      '<span class="response-pending-icon"><i></i><i></i><i></i></span><span>' +
      esc(label) + '</span></div>';
  }

  function showPlayerTurn(view) {
    var box = one('.council-speech');
    if (!box) return;
    var who = ((view.player || {}).label || '我方');
    box.classList.add('is-system');
    box.classList.add('is-pending');
    box.innerHTML = '<div class="broadcast-avatar"><span class="response-pending-icon">' +
      '<i></i><i></i><i></i></span></div><div class="council-speech-body"><div class="speech-meta">' +
      '<strong>轮到 ' + esc(who) + ' <small class="broadcast-system">YOUR TURN</small></strong>' +
      '<span>等待出牌</span><em>MANUAL</em></div>' +
      '<p>' + esc(who) + ' 正在组织发言<span class="typing-dots"><i></i><i></i><i></i></span></p></div>';
  }

  function setResponsePending(on) {
    var existing = $('#liveResponsePending');
    if (existing) existing.remove();
    if (!on || !S.state) return;
    if (S.mode === 'bilateral') {
      var dialogue = one('.dialogue-scroll');
      var label = ((S.state.opponent || {}).label || '对方') + ' 正在组织回应';
      if (dialogue) {
        dialogue.insertAdjacentHTML('beforeend', responsePendingHTML(label));
        dialogue.scrollTop = dialogue.scrollHeight;
      }
      return;
    }
    var broadcast = one('.council-speech');
    if (!broadcast) return;
    var waiting = S.mode === 'multi' ? '各方正在组织回应' : '下一个主体正在思考';
    /* 生成中：所有席位都回到待命，只保留“谁在思考”的提示 */
    $$('.seat.speaking').forEach(function (el) { el.classList.remove('speaking'); });
    $$('.seat small').forEach(function (el) { el.textContent = 'STANDBY'; });
    broadcast.classList.add('is-system', 'is-pending');
    broadcast.innerHTML = '<div class="broadcast-avatar"><span class="response-pending-icon">' +
      '<i></i><i></i><i></i></span></div><div class="council-speech-body"><div class="speech-meta">' +
      '<strong>会议播报 <small class="broadcast-system">SYSTEM</small></strong><span>WORKING</span>' +
      '<em>AUTO</em></div><p>' + waiting + '<span class="typing-dots"><i></i><i></i><i></i></span></p></div>';
  }

  async function submitTurn() {
    if (S.busy || !S.state) return;
    if (S.state.finished) { toast('本局谈判已结束，点右上角「结束谈判」查看复盘或重新开始'); return; }
    if (!S.selected.length) {
      toast('请选择至少一张策略卡，再点击「结束本轮」');
      return;
    }
    var cards = S.selected.slice();
    var started = Date.now();
    setBusy(true);
    animateSelectedCards();
    setResponsePending(true);
    try {
      var res = await api('/say', {
        text: '',
        card_ids: cards,
        target: S.target,
        perspective: S.perspective,
        follow: S.follow
      });
      var remaining = 650 - (Date.now() - started);
      if (remaining > 0) await new Promise(function (resolve) { setTimeout(resolve, remaining); });
      S.selected = [];
      applyView(res.view, res.event);
      if (res.warning) toast(res.warning);
      if (res.settle_notes && res.settle_notes.length) toast(res.settle_notes[0]);
      else toast('本轮已结算');
      if (S.mode === 'multi') {
        var mine = (res.view.messages || []).filter(function (m) { return m.role === 'player'; });
        S._ownPreview = mine[mine.length - 1] || null;
        applyView(res.view, res.event);
      }
      scheduleMultiAuto();
      if (res.view && res.view.finished) {
        stopAuto();
        toast(res.reason || res.view.finish_reason || '推演已结束');
      }
      var tasks = (res.view.player && res.view.player.hidden_tasks) || [];
      if (tasks.some(function (t) { return !t.done; }) && !res.view.finished) {
        setTimeout(refresh, 2800);
        setTimeout(refresh, 6500);
        setTimeout(refresh, 11000);
      }
    } catch (e) {
      applyView(S.state);
      toast(e.message || '本轮提交失败');
    } finally {
      setBusy(false);
    }
  }

  var MULTI_PACE_MS = 20000;
  function scheduleMultiAuto() {
    if (S.mode !== 'multi' || !S.state) return;
    if (!Number(S.state.auto_left || 0)) return;
    clearTimeout(S.multiTimer);
    S.multiTimer = setTimeout(function () {
      if (S.busy) { scheduleMultiAuto(); return; }
      nextSpeech();
    }, MULTI_PACE_MS);
  }

  async function nextSpeech() {
    if (S.busy || (S.mode !== 'observe' && S.mode !== 'multi') || !S.state) return;
    if (S.state.finished) { stopAuto(); toast('推演已结束'); return; }
    setBusy(true);
    setResponsePending(true);
    try {
      S._ownPreview = null;
      var res = await api('/say', {
        auto: true, perspective: S.perspective, follow: S.follow
      });
      applyView(res.view, res.event);
      if (res.warning) toast(res.warning);
      if (res.view && res.view.finished) {
        stopAuto();
        toast(res.reason || res.view.finish_reason || '推演已结束');
      }
    } catch (e) {
      applyView(S.state);
      toast(e.message || '推演失败');
      stopAuto();
    } finally {
      setBusy(false);
    }
  }

  function startAuto() {
    stopAuto();
    S.auto = true;
    S.timer = setInterval(function () {
      if (!S.auto || S.mode !== 'observe' || S.busy) return;
      if (window.NegotiationEventCard && window.NegotiationEventCard.isOpen()) {
        var status = $('#playStatus');
        if (status) status.textContent = '事件卡打开 · 推演已暂停';
        return;
      }
      nextSpeech();
    }, 20000);   /* 观战：每 20 秒推进一条发言，留足阅读时间 */
    var button = $('#autoButton');
    if (button) { button.classList.add('active'); button.textContent = 'AUTO'; }
    var status = $('#playStatus');
    if (status) status.textContent = '自动推演中';
  }

  function stopAuto() {
    S.auto = false;
    if (S.timer) { clearInterval(S.timer); S.timer = null; }
    var button = $('#autoButton');
    if (button) { button.classList.remove('active'); button.textContent = 'MANUAL'; }
    var status = $('#playStatus');
    if (status && S.mode === 'observe') status.textContent = '手动逐条播放';
  }

  function toggleAuto() {
    if (S.mode !== 'observe') return;
    if (S.auto) stopAuto();
    else startAuto();
  }

  async function refresh() {
    try {
      var res = await api('/state?perspective=' + encodeURIComponent(S.perspective) +
        '&follow=' + encodeURIComponent(S.follow));
      applyView(res.view);
    } catch (e) {
      toast(e.message || '刷新失败');
    }
  }

  // ---------------------------------------------------------------- 事件 / 复盘

  window.addEventListener('message', function (e) {
    var d = e.data || {};
    if (d.type !== 'secret-card') return;
    var layer = document.getElementById('secretCardLayer');
    if (d.action === 'accept') {
      if (layer) layer.remove();
      openPrivate();
      return;
    }
    if (layer) layer.remove();
  });

  function showSecretCard(deal) {
    var stale = document.getElementById('secretCardLayer');
    if (stale) stale.remove();
    var who = (deal && (deal.party_label || deal.party)) || '对方';
    var layer = document.createElement('div');
    layer.id = 'secretCardLayer';
    layer.className = 'secret-card-layer';
    layer.innerHTML = '<div class="secret-card-stage">' +
      '<iframe src="cards/secret-card.html?party=' + encodeURIComponent(who) +
        '&round=' + encodeURIComponent((S.state && S.state.round) || '') +
        '&desc=' + encodeURIComponent(deal && (deal.their_term || deal.our_term) || '') +
        '&term=' + encodeURIComponent(deal && (deal.status_label || '') || '') +
        '" title="非正式沟通卡" scrolling="no"></iframe>' +
      '';
    document.body.appendChild(layer);
    layer.addEventListener('click', function (e) {
      if (e.target === layer || e.target.classList.contains('secret-card-x')) layer.remove();
    });
  }

  function showRoundSpeech(round, speaker) {
    var msg = null;
    var list = (S.state && S.state.messages) || [];
    for (var i = list.length - 1; i >= 0; i--) {
      var m = list[i];
      if (Number(m.round) === Number(round) && (!speaker || m.key === speaker)) { msg = m; break; }
    }
    var old = document.getElementById('roundSpeech');
    if (old) old.remove();
    var box = document.createElement('div');
    box.id = 'roundSpeech';
    box.className = 'live-end-ask';
    box.innerHTML = '<section style="text-align:left">' +
      '<span class="kicker">ROUND ' + esc(round) + '</span>' +
      '<h2 style="font-size:20px;margin:8px 0 12px">' +
      esc(msg ? (msg.label || msg.sender || '') : '该轮发言') + '</h2>' +
      '<p style="font-size:13.5px;line-height:1.9;color:var(--text);max-height:52vh;overflow:auto">' +
      esc(msg ? msg.text : '没有找到这一轮的完整发言记录。') + '</p>' +
      '<button class="back" data-close-round>关闭</button></section>';
    document.body.appendChild(box);
    box.addEventListener('click', function (e) {
      if (e.target === box || e.target.closest('[data-close-round]')) box.remove();
    });
  }

  function showEventList() {
    var events = ((S.state && S.state.events) || []).slice().reverse();
    var old = document.getElementById('eventList');
    if (old) old.remove();
    var rows = events.length
      ? events.map(function (ev, i) {
          return '<button data-ev="' + i + '" class="event-row">' +
            '<b>第 ' + esc(ev.round) + ' 轮</b><span>' + esc(ev.title || '突发事件') + '</span>' +
            '<em>' + esc(ev.id || '') + '</em></button>';
        }).join('')
      : '<div class="fold-placeholder" style="padding:16px 0">本局还没有触发过突发事件。</div>';
    var box = document.createElement('div');
    box.id = 'eventList';
    box.className = 'live-end-ask';
    box.innerHTML = '<section style="text-align:left;position:relative">' +
      '<button class="modal-x" data-close-ev aria-label="关闭">' +
      '<svg viewBox="0 0 24 24"><path d="M5 5l14 14M19 5L5 19"/></svg></button>' +
      '<span class="kicker">EVENT LOG</span><h2 style="font-size:20px;margin:8px 0 14px">本局突发事件</h2>' +
      '<div class="event-rows" style="max-height:50vh;overflow:auto">' + rows + '</div></section>';
    document.body.appendChild(box);
    box.addEventListener('click', function (e) {
      var row = e.target.closest('[data-ev]');
      if (row) {
        var idx = Number(row.getAttribute('data-ev'));
        var ev = events[idx];
        box.remove();
        if (ev) showEvent(ev);
        return;
      }
      if (e.target === box || e.target.closest('[data-close-ev]')) box.remove();
    });
  }

  function showEvent(event) {
    if (!event) return;
    S.lastEvent = event;
    if (!window.NegotiationEventCard) { toast('事件卡脚本未加载'); return; }
    var payload = {};
    Object.keys(event).forEach(function (key) { payload[key] = event[key]; });
    /* 事件卡里的“我方/对方”要落到具体主体，多边才不会指代不明 */
    var me = (S.state && S.state.player) || null;
    var other = (_labelOf(S.state && S.state.speaker)) || '';
    payload.playerLabel = (me && me.label) ? (me.label + ' · 我方') : '我方';
    payload.agentLabel = (other && other !== (me && me.label)) ? other : '其他代表团';
    try {
      window.NegotiationEventCard.show(payload);
    } catch (err) {
      if (window.NegotiationEventCard && window.NegotiationEventCard.close) {
        try { window.NegotiationEventCard.close(); } catch (e2) {}
      }
      toast('事件卡渲染失败：' + (err && err.message ? err.message : err));
    }
    var status = $('#playStatus');
    if (status && S.mode === 'observe') status.textContent = '事件卡打开 · 推演已暂停';
  }

  function askEnd() {
    if (!S.state || S.busy) return;
    if (document.getElementById('liveEndAsk')) return;
    var st = S.state;
    var over = document.createElement('div');
    over.id = 'liveEndAsk';
    over.className = 'live-end-ask';
    over.innerHTML = '<section>' +
      '<span class="kicker">END SESSION</span>' +
      '<h2>结束本局谈判</h2>' +
      '<p class="sub">第 ' + (st.round || 0) + ' / ' + (st.rounds || 30) + ' 回合</p>' +
      '<p class="tip">结束本局后将生成本局复盘报告。<br>请选择本局的收尾方式。</p>' +
      '<div class="row"><button data-end="deal">达成协议</button>' +
      '<button data-end="break" class="ghost">谈判破裂</button></div>' +
      '<button class="back" data-end="">继续谈判</button></section>';
    document.body.appendChild(over);
    over.addEventListener('click', function (e) {
      var b = e.target.closest('[data-end]');
      if (b) { var v = b.getAttribute('data-end'); over.remove(); if (v) endSession(v); return; }
      if (e.target === over) over.remove();
    });
  }

  function endSession(result) {
    if (!S.state) return;
    if (S.busy) return;
    stopAuto();
    setBusy(true, '正在生成复盘…');
    api('/end', { perspective: S.perspective, follow: S.follow })
      .then(function (res) {
        setBusy(false);
        applyView(res.view);
        try {
          localStorage.setItem('neg-v2-report', JSON.stringify(res.report));
          localStorage.setItem('neg-v2-report-mode', S.mode);
        } catch (e) {}
        try {
          var _r = JSON.parse(localStorage.getItem('neg-report') || '{}');
          var _label = result === 'break' ? '谈判破裂' : (result === 'deal' ? '达成协议' : '推演完成');
          _r.meta = _r.meta || {};
          _r.meta.resultLabel = _label;
          _r.meta.result = result || 'deal';
          _r.channels = (res.report && (res.report.channels || res.report.deals)) || [];
          /* 把没谈成的暗线也带进复盘（谈判树里的 nonpublic 节点） */
          var _seen = {};
          (_r.channels || []).forEach(function (c) {
            _seen[(c.party_label || c.party || '') + '|' + (c.status || '')] = 1;
          });
          var _nodes = ((res.view && res.view.tree && res.view.tree.nodes) || []).filter(function (n) {
            return n.kind === 'nonpublic';
          });
          _nodes.forEach(function (n) {
            var other = (n.visibility || []).filter(function (k) {
              return k !== ((res.view.player || {}).key);
            })[0] || '';
            var label = '';
            ((res.view.parties) || []).forEach(function (p) { if (p.key === other) label = p.label; });
            var key = label + '|closed';
            if (_seen[key]) return;
            _seen[key] = 1;
            _r.channels.push({
              party_label: label || other, status: 'closed',
              status_label: '未达成', their_term: n.claim || ''
            });
          });
          var _rel = (res.view && res.view.relations) || null;
          _r.relations = [];
          if (_rel && _rel.parties && _rel.cells) {
            _r.relations = _rel.parties.map(function (k, i) {
              var row = { key: k, label: (_rel.labels || [])[i] || k, trust: {} };
              _rel.cells.forEach(function (c) {
                if (c.src !== k) return;
                var v = (c.values || {}).trust;
                if (!v) return;
                if (v.kind === 'exact') row.trust[c.dst] = v.value;
                else if (v.kind === 'estimate' && v.range) row.trust[c.dst] = Math.round((v.range[0] + v.range[1]) / 2);
              });
              return row;
            });
          }
          localStorage.setItem('neg-report', JSON.stringify(_r));
        } catch (e) {}
        location.href = 'report/loading.html';
      })
      .catch(function (e) {
        setBusy(false);
        toast(e.message || '复盘生成失败');
      });
  }

  function showSummary(report) {
    var old = $('#liveSummary');
    if (old) old.remove();
    var labels = report.labels || {};
    var indexes = report.indexes || {};
    var rows = Object.keys(indexes).map(function (key) {
      var row = indexes[key] || {};
      return '<tr><td>' + esc(labels[key] || key) + '</td><td>' +
        Math.round(row.interest || 0) + '</td><td>' + Math.round(row.image || 0) +
        '</td><td>' + Math.round(row.trust || 0) + '</td></tr>';
    }).join('');
    var counts = (report.camp || {}).counts || {};
    var stats = report.deal_stats || {};
    var intelRows = Object.keys(report.intel || {}).map(function (key) {
      var item = report.intel[key] || {};
      return '<span>' + esc(labels[key] || key) + '：证据 ' + (item.evidence || 0) +
        ' 条 / 准确度 ' + (item.accuracy || 0) + '</span>';
    }).join('');
    /* 把本局结果写入 localStorage，供复盘页读取 */
    try {
      var _me = (report.indexes && report.indexes[((S.state && S.state.player) || {}).key]) || {};
      var _tasks = (report.tasks || []);
      var _done = _tasks.filter(function (t) { return t.done; }).length;
      localStorage.setItem('neg-report', JSON.stringify({
        scores: {
          interest: Math.round(_me.interest || 0),
          image: Math.round(_me.image || 0),
          trust: Math.round(_me.trust || 0),
          hidden: _tasks.length ? Math.round(_done / _tasks.length * 100) : 0
        },
        tasks: _tasks.map(function (t) { return { title: t.title || t.name || '隐藏任务', done: !!t.done }; }),
        meta: {
          topic: report.topic || '', mode: S.mode,
          modeLabel: MODE_LABEL[S.mode] || '',
          rounds: report.rounds || 0, total: report.rounds || 0,
          resultLabel: '推演完成'
        }
      }));
    } catch (e) {}

    var overlay = document.createElement('div');
    overlay.id = 'liveSummary';
    overlay.className = 'live-summary';
    overlay.innerHTML = '<section class="live-summary-card"><header><div><span>DEBRIEF</span>' +
      '<h2>谈判结束</h2></div><button id="liveCloseSummary" aria-label="关闭">×</button></header>' +
      '<p class="live-summary-sub">' + esc(report.topic || '') + ' · ' + esc(MODE_LABEL[S.mode] || '') +
      ' · ' + esc(report.rounds || 0) + ' 轮</p>' +
      '<table class="live-summary-table"><thead><tr><th>代表团</th><th>利益</th><th>形象</th><th>信任</th></tr></thead>' +
      '<tbody>' + rows + '</tbody></table>' +
      '<div class="live-summary-grid"><div><strong>最终阵营</strong><span>支持 ' +
      (counts.support || 0) + ' / 摇摆 ' + (counts.swing || 0) + ' / 反对 ' +
      (counts.oppose || 0) + '</span></div><div><strong>非正式沟通</strong><span>共 ' +
      (stats.total || 0) + ' 份 · 确认 ' + (stats.confirmed || 0) + ' · 失效 ' +
      ((stats.broken || 0) + (stats.expired || 0)) + '</span></div></div>' +
      (intelRows ? '<div class="live-summary-intel"><strong>情报账本</strong>' + intelRows + '</div>' : '') +
      '<div class="live-summary-grid"><div><strong>隐藏任务</strong><span>' +
      (report.tasks || []).filter(function (t) { return t.done; }).length + ' / ' +
      (report.tasks || []).length + '</span></div><div><strong>复盘</strong><span>' +
      '<a href="report/index.html" class="live-report-link">打开完整复盘报告 →</a></span></div></div>' +
      '<footer><button class="secondary-button" id="liveCloseSummary2">关闭</button>' +
      '<button class="primary-button" id="liveRestart">重新谈判</button></footer></section>';
    document.body.appendChild(overlay);
  }

  // ---------------------------------------------------------------- 绑定

  function setView(view) {
    S.view = view === 'simple' ? 'simple' : 'strategy';
    var app = $('#app');
    if (app) {
      app.classList.remove('view-simple', 'view-strategy');
      app.classList.add('view-' + S.view);
    }
    var label = $('#viewLabel');
    if (label) label.textContent = S.view === 'simple' ? '简洁视图' : '策略视图';
    $$('#viewMenu button').forEach(function (button) {
      button.classList.toggle('selected', button.getAttribute('data-view') === S.view);
    });
    $('#viewMenu').classList.remove('open');
    $('#viewButton').setAttribute('aria-expanded', 'false');
    toast('已切换为' + (S.view === 'simple' ? '简洁视图' : '策略视图'));
  }

  async function setPerspective(perspective) {
    if (S.mode !== 'observe') return;
    var next = perspective === 'party' ? 'party' : 'omniscient';
    if (S.perspective === next) return;
    S.perspective = next;   /* 推演进行中也可以切，服务端读状态不取会话锁 */
    // 先给即时反馈，再等接口回来
    $$('[data-perspective]').forEach(function (button) {
      button.classList.toggle('active', button.getAttribute('data-perspective') === next);
    });
    var status = $('#perspectiveStatus');
    if (status) {
      var followed = (S.state && S.state.parties || []).filter(function (p) { return p.key === S.follow; })[0];
      status.textContent = next === 'omniscient' ? '全知' : ('跟随 · ' + ((followed || {}).label || S.follow));
    }
    var chips = document.querySelector('.perspective-card');
    if (chips) chips.classList.add('is-switching');
    try {
      var res = await api('/state?perspective=' + encodeURIComponent(S.perspective) +
        '&follow=' + encodeURIComponent(S.follow));
      applyView(res.view);
    } catch (e) {
      toast(e.message || '视角切换失败');
    } finally {
      if (chips) chips.classList.remove('is-switching');
    }
  }

  function bind() {
    document.addEventListener('click', function (event) {
      var target = event.target;
      var modeLink = target.closest ? target.closest('.mode-switch [data-mode]') : null;
      if (modeLink) {
        event.preventDefault();
        var mode = UI_TO_MODE[modeLink.getAttribute('data-mode')];
        if (mode && mode !== S.mode) startSession(mode);
        return;
      }
      if (target.closest('#viewButton')) {
        var menu = $('#viewMenu');
        var open = menu.classList.toggle('open');
        $('#viewButton').setAttribute('aria-expanded', String(open));
        return;
      }
      var viewButton = target.closest('#viewMenu [data-view]');
      if (viewButton) { setView(viewButton.getAttribute('data-view')); return; }
      if (!target.closest('.view-picker')) {
        $('#viewMenu').classList.remove('open');
        $('#viewButton').setAttribute('aria-expanded', 'false');
      }
      if (target.closest('#themeButton') && !window.toggleTheme) {
        var light = document.documentElement.getAttribute('data-theme') === 'light';
        document.documentElement.setAttribute('data-theme', light ? 'dark' : 'light');
        return;
      }
      var collapse = target.closest('[data-collapse]');
      if (collapse) {
        var side = collapse.getAttribute('data-collapse');
        if (side === 'right') $('#app').classList.toggle('right-open');
        else $('#app').classList.toggle('left-collapsed');
        return;
      }
      var reopen = target.closest('[data-reopen]');
      if (reopen) {
        var reopenSide = reopen.getAttribute('data-reopen');
        if (reopenSide === 'right') $('#app').classList.add('right-open');
        else $('#app').classList.remove('left-collapsed');
        return;
      }
      if (target.closest('#rightScrim')) { $('#app').classList.remove('right-open'); return; }
      var _tn = target.closest('.tree-node[data-tree-round]');
      if (_tn) {
        showRoundSpeech(_tn.getAttribute('data-tree-round'), _tn.getAttribute('data-tree-speaker'));
        return;
      }
      if (target.closest('#treeSecretToggle')) {
        var on = !secretTreeOn();
        setSecretTree(on);
        renderDrawer();
        toast(on ? '已开启暗线 · 谈判树将显示非公开因果' : '已关闭暗线 · 只显示公开因果');
        return;
      }
      if (target.closest('#openTreeTop')) { openDrawer('tree'); return; }
      if (target.closest('.back-button')) {
        var _h=(target.closest('.back-button')||{}).getAttribute&&target.closest('.back-button').getAttribute('data-home'); if(_h){location.href=_h;return;} toast('本地实时版 · 用顶部三个模式切换会场');
        return;
      }
      var seatTarget = target.closest('[data-target-key]');
    if (seatTarget && S.mode !== 'observe') {
      applyTarget(seatTarget.getAttribute('data-target-key'));
      return;
    }
    var opener = target.closest('[data-open]');
      if (opener) { openDrawer(opener.getAttribute('data-open')); return; }
      var card = target.closest('.strategy-card');
      if (card) { toggleCard(card.getAttribute('data-card-id')); return; }
      if (target.closest('#liveEndTurn') || target.closest('[data-end-turn]')) {
        event.preventDefault();
        submitTurn();
        return;
      }
      if (target.closest('#liveRefreshTasks')) { refresh(); toast('正在刷新任务与局势…'); return; }
      if (target.closest('[data-persona-toggle]')) {
        S.persona = (S.persona + 1) % PERSONA.length;
        if (S.state) renderNarrator(S.state);
        toast('解说口吻已切换为「' + PERSONA_LABEL[PERSONA[S.persona]] + '」');
        return;
      }
      var persp = target.closest('[data-perspective]');
      if (persp) { setPerspective(persp.getAttribute('data-perspective')); return; }
      if (target.closest('#autoButton')) { toggleAuto(); return; }
      if (target.closest('#nextSpeech')) { nextSpeech(); return; }
      if (target.closest('#eventDemo')) { showEventList(); return; }
      if (target.closest('.end-button')) { askEnd(); return; }
      if (target.closest('#restartButton')) { restartSession(); return; }
      var home = target.closest('[data-home]');
      if (home) { location.href = home.getAttribute('data-home'); return; }
      if (target.closest('#closeDrawer') || target.closest('#drawerBackdrop')) { closeDrawer(); return; }
      var tab = target.closest('#drawerTabs [data-tab]');
      if (tab) { openDrawer(tab.getAttribute('data-tab')); return; }
      var matrixButton = target.closest('#drawerContent [data-matrix]');
      if (matrixButton) { S.matrix = matrixButton.getAttribute('data-matrix'); renderDrawer(); return; }
      var relation = target.closest('#drawerContent [data-relation]');
      if (relation) { S.relation = relation.getAttribute('data-relation'); renderDrawer(); return; }
      if (target.closest('#drawerEnterPrivate')) { closeDrawer(); openPrivate(); return; }
      var inviteBtn = target.closest('[data-invite-key]');
      if (inviteBtn) { startInvite(inviteBtn.getAttribute('data-invite-key')); return; }
      var intelBtn = target.closest('[data-intel-action]');
      if (intelBtn) {
        var intelAction = intelBtn.getAttribute('data-intel-action');
        var intelBody = {
          action: intelAction,
          intel_id: intelBtn.getAttribute('data-intel-id'),
          target: intelAction === 'sell' ? (S.target || (S.state.opponent || {}).key) : null,
          perspective: S.perspective, follow: S.follow
        };
        api('/intel', intelBody).then(function (res) {
          if (res.view) { S.state = res.view; applyView(res.view); }
          toast(res.message || '情报已处理');
          renderDrawer();
        }).catch(function (e) { toast(e.message || '情报操作失败'); });
        return;
      }
      if (target.closest('#liveSecret')) {
        dealAction('secret');
        return;
      }
      if (target.closest('#closePrivate')) { closePrivate(); return; }
      if (target.closest('#returnPublic')) {
        if (target.closest('#returnPublic').dataset.decline === '1') {
          dealAction('decline');
        } else {
          closePrivate();
        }
        return;
      }
      if (target.closest('#modifyDeal')) {
        if (!confirm('拒绝这次非正式沟通邀请？')) return;
        dealAction('decline');
        return;
      }
      if (target.closest('#acceptDeal')) {
        var action = $('#acceptDeal').dataset.action;
        if (!action) return;
        if (action === 'confirm') {
          var confirmCard = S.selected.filter(function (id) { return CONFIRM_CARDS.indexOf(id) >= 0; })[0];
          if (!confirmCard) {
            toast('请先在手牌中选择一张正式卡牌（议题捆绑 / 正式议题捆绑 / 一揽子方案 / 分阶段表决）');
            return;
          }
          dealAction('confirm', { card_id: confirmCard });
        } else {
          dealAction('accept');
        }
        return;
      }
      if (target.closest('#expandOs')) {
        var os = $('#innerOs');
        var expanded = os.classList.toggle('expanded');
        target.closest('#expandOs').textContent = expanded ? '收起' : '展开';
        return;
      }
      if (target.closest('#liveRestart')) {
        var overlay = $('#liveSummary');
        if (overlay) overlay.remove();
        startSession(S.mode);
        return;
      }
      if (target.closest('#liveCloseSummary') || target.closest('#liveCloseSummary2')) {
        var box = $('#liveSummary');
        if (box) box.remove();
        return;
      }
      if (target.closest('#privateModal') === target) closePrivate();
    });

    var partySelect = $('#partySelect');
    if (partySelect) {
      partySelect.addEventListener('change', function () {
        S.follow = this.value;
        S.perspective = 'party';
        refresh();
      });
    }
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        closeDrawer();
        closePrivate();
        var app = $('#app');
        if (app) app.classList.remove('right-open');
        var overlay = $('#liveSummary');
        if (overlay) overlay.remove();
        $('#viewMenu').classList.remove('open');
      }
    });
    var drawer = $('#drawerBackdrop');
    if (drawer) drawer.addEventListener('click', closeDrawer);
  }

  function init() {
    document.title = 'Diplomat 2.0 · ' + (MODE_LABEL[FIXED_MODE] || '谈判');
    // 首屏的静态卡是设计稿残留，先清掉，等真实手牌
    $$('.strategy-cards').forEach(function (box) {
      box.innerHTML = '<div class="hand-placeholder">正在准备会场…</div>';
    });
    var app = $('#app');
    if (app && !$('#rightScrim')) {
      var scrim = document.createElement('div');
      scrim.id = 'rightScrim';
      scrim.className = 'right-scrim';
      app.appendChild(scrim);
    }
    hydrateFlags(document);
    bind();
    startSession();
  }

  init();
})();