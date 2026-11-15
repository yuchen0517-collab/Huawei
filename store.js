(function (D) {
  "use strict";

  var listeners = [];
  var state = null;

  function init(initial) {
    state = initial;
    notify();
    return state;
  }

  function get() { return state; }

  function subscribe(fn) {
    listeners.push(fn);
    return function () {
      listeners = listeners.filter(function (x) { return x !== fn; });
    };
  }

  function notify() {
    listeners.slice().forEach(function (fn) { fn(state); });
  }

  function patch(partial) {
    Object.keys(partial).forEach(function (k) { state[k] = partial[k]; });
    notify();
  }

  function patchUi(partial) {
    Object.assign(state.ui, partial);
    notify();
  }

  function setDraft(clauseId, value) {
    if (state.ui.finaleOpen) return;
    var c = state.clauses.filter(function (x) { return x.id === clauseId; })[0];
    if (!c || value == null || value === "" || value === c.mine) delete state.draft[clauseId];
    else state.draft[clauseId] = value;
    notify();
  }

  function selectCard(id) {
    if (state.ui.finaleOpen) return;
    state.selectedCard = state.selectedCard === id ? null : id;
    state.rehearsal = D.adapters.current.rehearsal(state);
    notify();
  }

  function setView(view) { patchUi({ view: view }); }
  function openDrawer() { patchUi({ drawerOpen: true }); }
  function closeDrawer() { patchUi({ drawerOpen: false }); }
  function openFinale() { patchUi({ finaleOpen: true }); }
  function closeFinale() { patchUi({ finaleOpen: false }); }
  function toggleDemo() { patchUi({ demoOpen: !state.ui.demoOpen }); }
  function closeDemo() { patchUi({ demoOpen: false }); }

  function setDemoError(code) {
    state.demoError = state.demoError === code ? null : code;
    notify();
    D.overlays.toast(null, state.demoError ? "下一次提交将注入 " + code : "已关闭错误注入");
  }

  function pendingClauses(s) {
    var open = s.openIssues || [];
    return s.clauses.filter(function (c) {
      return c.status === "pending" || open.indexOf(c.name) >= 0;
    });
  }

  function hardError(code, detail) {
    D.overlays.toast(code, detail, JSON.stringify({ error: code, detail: detail }));
    return Promise.resolve({ error: { error: code, detail: detail } });
  }

  function commit() {
    var s = state;
    if (!s || s.inflight || s.ui.finaleOpen) return Promise.resolve();
    if (s.roundLocked) {
      return hardError("ROUND_LOCKED", D.adapters.current.messages.ROUND_LOCKED);
    }
    if (s.conflict) return Promise.resolve();

    // P6：空草稿且未选卡禁止提交
    if (!Object.keys(s.draft).length && !s.selectedCard) {
      return hardError(
        "INVALID_ACTION",
        "当前没有任何条款变更或策略卡，无法提交本轮报价（P6）。请先修改至少一条条款。"
      );
    }

    var key = s.retryKey || D.util.newKey();
    return doSubmit(key);
  }

  function doSubmit(key) {
    var s = state;
    if (s.submittedKeys[key]) {
      D.overlays.toast(null, "该行动已记账，未重复提交（幂等键 " + key + "）");
      return Promise.resolve();
    }

    s.inflight = key;
    s.retryKey = null;
    s.inlineError = null;
    s.phase = "submitting";
    notify();

    return D.adapters.current.submit(s, { key: key, demoError: s.demoError }).then(function (res) {
      if (res.retryAfter) {
        s.phase = "submitting";
        s.demoError = null;
        notify();
        D.overlays.toast(
          "SESSION_BUSY",
          D.adapters.current.messages.SESSION_BUSY,
          JSON.stringify({ error: "SESSION_BUSY", detail: D.adapters.current.messages.SESSION_BUSY })
        );
        setTimeout(function () { doSubmit(key); }, res.retryAfter);
        return;
      }

      s.inflight = null;

      if (!res.ok) {
        applyError(key, res);
        return;
      }

      Object.assign(s, res.patch);
      s.rehearsal = D.adapters.current.rehearsal(s);
      s.phase = "ready";
      notify();
      D.overlays.toast(null, "本轮报价已入账 · 版本推进到 v" + s.version);

      if (s.ended) openFinale();
    });
  }

  function applyError(key, res) {
    var s = state;
    var e = res.error;
    if (e.error === "TIMEOUT") { s.retryKey = key; s.demoError = null; }
    if (e.error === "VERSION_CONFLICT") {
      s.conflict = true;
      s.serverVersion = (res.patch && res.patch.serverVersion) || s.version + 1;
      s.retryKey = key;
    }
    if (e.error === "INVALID_ACTION") s.inlineError = e;
    if (e.error === "MODEL_UNAVAILABLE") s.modelDown = true;
    if (e.error === "ROUND_LOCKED") s.roundLocked = true;
    s.phase = "ready";
    notify();
    D.overlays.toast(e.error, e.detail, JSON.stringify(e));
  }

  function merge() {
    if (state.ui.finaleOpen) return Promise.resolve();
    return D.adapters.current.merge(state).then(function (res) {
      if (!res.ok) {
        D.overlays.toast(res.error.error, res.error.detail, JSON.stringify(res.error));
        return;
      }
      Object.assign(state, res.patch);
      state.demoError = null;
      notify();
      D.overlays.toast(null, "已拉取服务端 v" + state.version + "，草稿保留，请确认后重提");
    });
  }

  function accept() {
    var pending = pendingClauses(state);
    if (pending.length || state.roundLocked || state.ui.finaleOpen) return Promise.resolve();
    return D.adapters.current.accept(state).then(function (res) {
      if (!res.ok) {
        D.overlays.toast(res.error.error, res.error.detail, JSON.stringify(res.error));
        return;
      }
      state.audit = res.audit;
      state.ui.finaleOpen = true;
      notify();
    });
  }

  function reject() {
    D.overlays.toast(null, "已记录拒绝 · 对方将收到正式回复");
  }

  // K3=B：提交本轮总结只记录，不推进 round、不扣 ap
  function endRoundSummary() {
    var s = state;
    if (s.roundLocked || s.inflight || s.ui.finaleOpen) return Promise.resolve();
    var hadDraft = Object.keys(s.draft).length > 0;
    return D.adapters.current.summary(s).then(function (res) {
      if (!res.ok) {
        D.overlays.toast(res.error.error, res.error.detail, JSON.stringify(res.error));
        return;
      }
      s.timeline = res.timeline;
      notify();
      D.overlays.toast(null, (hadDraft ? "草稿仍保留 · " : "") + "本轮总结已记录 · 轮次仍为 R" + s.round + "（报价提交才推进轮次）");
    });
  }

  function nextTopic() {
    if (state.ui.finaleOpen) return Promise.resolve();
    return D.adapters.current.nextTopic(state).then(function (res) {
      Object.assign(state.topic, res.topic);
      notify();
      D.overlays.toast(null, "已切换议题：" + res.topic.name);
    });
  }

  function randomCheck() {
    if (state.ui.finaleOpen) return Promise.resolve();
    return D.adapters.current.randomCheck(state).then(function (res) {
      state.topic.randomCheck = res.status;
      state.randomWarnings = res.warnings;
      notify();
      D.overlays.toast(null, res.message);
    });
  }

  function newGame() {
    return D.adapters.current.reset(state, { newGame: true }).then(function (fresh) {
      init(fresh);
      D.overlays.toast(null, "新一场会话已初始化 · 版本 v" + state.version);
      return state;
    });
  }

  function resetDemo() {
    return D.adapters.current.reset(state, { resetDemo: true }).then(function (fresh) {
      init(fresh);
      state.ui.demoOpen = false;
      notify();
      D.overlays.toast(null, "演示场景已复位 · v" + state.version + " · R" + state.round + "/" + state.maxRound);
    });
  }

  function snapshot() {
    var copy = JSON.parse(JSON.stringify(state));
    return copy;
  }

  D.store = {
    init: init,
    get: get,
    subscribe: subscribe,
    notify: notify,
    patch: patch,
    patchUi: patchUi,
    setDraft: setDraft,
    selectCard: selectCard,
    setView: setView,
    openDrawer: openDrawer,
    closeDrawer: closeDrawer,
    openFinale: openFinale,
    closeFinale: closeFinale,
    toggleDemo: toggleDemo,
    closeDemo: closeDemo,
    setDemoError: setDemoError,
    pendingClauses: pendingClauses,
    commit: commit,
    merge: merge,
    accept: accept,
    reject: reject,
    endRoundSummary: endRoundSummary,
    nextTopic: nextTopic,
    randomCheck: randomCheck,
    newGame: newGame,
    resetDemo: resetDemo,
    snapshot: snapshot
  };
})(window.D = window.D || {});