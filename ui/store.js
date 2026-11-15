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
    if (!c) { delete state.draft[clauseId]; notify(); return; }
    // A 第三轮 Q1：numeric 型按数值比较，避免 "800" 与 800 不相等
    if (c.type === "numeric") {
      if (value === "" || value == null || isNaN(Number(value))) {
        delete state.draft[clauseId];
      } else if (Number(value) === Number(c.mine)) {
        delete state.draft[clauseId];
      } else {
        state.draft[clauseId] = Number(value);
      }
      notify();
      return;
    }
    if (value == null || value === "" || value === c.mine) delete state.draft[clauseId];
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

  // G8：10 秒软提示；150 秒硬超时在 httpAdapter 内保持不变
  var slowTimer = null;
  var inflightCtrl = null;

  function startSlow() {
    stopSlow();
    var threshold = (window.DIPLOMAT_CONFIG || {}).slowHintSeconds || 10;
    state.slowSeconds = 0;
    state.slowHint = false;
    slowTimer = setInterval(function () {
      if (!state.inflight) { stopSlow(); notify(); return; }
      state.slowSeconds += 1;
      if (state.slowSeconds >= threshold) state.slowHint = true;
      notify();
    }, 1000);
  }

  function stopSlow() {
    if (slowTimer) { clearInterval(slowTimer); slowTimer = null; }
    if (state) { state.slowSeconds = 0; state.slowHint = false; }
  }

  function cancelInflight() {
    if (!state || !state.inflight) return;
    if (state._ctx) state._ctx.cancelled = true;
    if (inflightCtrl) inflightCtrl.abort();
    stopSlow();
    state.inflight = null;
    state.phase = "ready";
    notify();
    D.overlays.toast(null, "已取消等待，草稿保留");
  }

  // T3/A 答复：真实模式开局 POST /session；失败保持空框架并提示服务不可用
  function open() {
    var ad = D.adapters.current;
    state.phase = "loading";
    notify();
    if (!ad.openSession) {
      state.phase = "ready";
      notify();
      return Promise.resolve({ ok: true });
    }
    return ad.openSession().then(function (res) {
      if (!res || !res.ok) {
        state.phase = "ready";
        if (res && res.transport) reportServiceDown(res.transport);
        else if (res && res.error) {
          D.overlays.toast(res.error.error, res.error.detail, JSON.stringify(res.error));
          notify();
        } else {
          notify();
        }
        return res || { ok: false };
      }
      init(res.state);
      return res;
    });
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
    s.sessionLost = false;
    s.phase = "submitting";
    inflightCtrl = (typeof AbortController !== "undefined") ? new AbortController() : null;
    var ctx = {
      key: key,
      demoError: s.demoError,
      signal: inflightCtrl ? inflightCtrl.signal : null,
      cancelled: false
    };
    s._ctx = ctx;
    startSlow();
    notify();

    return D.adapters.current.submit(s, ctx).then(function (res) {
      if (res && res.aborted) {
        if (s.inflight === key) {
          stopSlow();
          s.inflight = null;
          s.phase = "ready";
          notify();
          D.overlays.toast(null, "已取消等待，草稿保留");
        }
        return;
      }
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

      stopSlow();
      s.inflight = null;

      if (!res.ok) {
        applyError(key, res);
        return;
      }

      Object.assign(s, res.patch);
      s.serviceDown = null;
      s.currentState = null;
      s.sessionLost = false;
      s.rehearsal = D.adapters.current.rehearsal(s);
      s.phase = "ready";
      notify();
      D.overlays.toast(null, "本轮报价已入账 · 版本推进到 v" + s.version);

      if (s.ended) openFinale();
    });
  }

  // G2：传输层不可用，不伪装成业务错误码、不自动重试、不改草稿
  function reportServiceDown(t) {
    state.serviceDown = t;
    state.inlineError = null;
    state.phase = "ready";
    notify();
    D.overlays.toast(null, "服务暂不可用，草稿已保留",
      JSON.stringify({ status: t.status, body: t.snippet }));
  }

  function reportFailure(res) {
    if (res.transport) { reportServiceDown(res.transport); return; }
    if (res.error) D.overlays.toast(res.error.error, res.error.detail, JSON.stringify(res.error));
  }

  function applyError(key, res) {
    var s = state;
    if (res.transport) { reportServiceDown(res.transport); return; }
    if (res.sessionLost) {
      s.sessionLost = true;
      s.inlineError = null;
      s.phase = "ready";
      notify();
      D.overlays.toast(null, "会话不存在或服务已重启，请重新开局");
      return;
    }
    var e = res.error;
    if (!e) { s.phase = "ready"; notify(); return; }
    if (e.error === "TIMEOUT") { s.retryKey = key; s.demoError = null; }
    if (e.error === "VERSION_CONFLICT") {
      s.conflict = true;
      s.serverVersion = (res.patch && res.patch.serverVersion) || s.version + 1;
      s.currentState = (res.patch && res.patch.currentState) || null;
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
        reportFailure(res);
        return;
      }
      Object.assign(state, res.patch);
      state.serviceDown = null;
      state.currentState = null;
      state.sessionLost = false;
      state.acceptRetryCount = 0;
      state.demoError = null;
      notify();
      D.overlays.toast(null, "已拉取服务端 v" + state.version + "，草稿保留，请确认后重提");
    });
  }

  function applyAcceptError(key, res) {
    if (res.transport) { reportServiceDown(res.transport); return; }
    if (res.sessionLost) {
      state.sessionLost = true;
      state.inlineError = null;
      state.phase = "ready";
      notify();
      D.overlays.toast(null, "会话不存在或服务已重启，请重新开局");
      return;
    }
    if (res.retryAfter && state.acceptRetryCount < 1) {
      state.acceptRetryCount += 1;
      state.phase = "submitting";
      notify();
      setTimeout(function () { D.store.accept(true); }, res.retryAfter);
      return;
    }
    if (res.retryAfter) {
      state.phase = "ready";
      notify();
      D.overlays.toast("SESSION_BUSY", res.error && res.error.detail, JSON.stringify(res.error));
      return;
    }
    if (res.error && res.error.error === "VERSION_CONFLICT") {
      state.conflict = true;
      state.serverVersion = (res.patch && res.patch.serverVersion) || state.version + 1;
      state.currentState = (res.patch && res.patch.currentState) || null;
      state.phase = "ready";
      notify();
      D.overlays.toast("VERSION_CONFLICT", res.error.detail, JSON.stringify(res.error));
      return;
    }
    if (res.error) {
      state.inlineError = res.error;
      state.phase = "ready";
      notify();
      D.overlays.toast(res.error.error, res.error.detail, JSON.stringify(res.error));
    }
  }

  // A 第二轮 Q1：接受协议 = action_type="accept"，同一幂等键可重试
  function accept(isRetry) {
    var pending = pendingClauses(state);
    if (pending.length || state.roundLocked || state.ui.finaleOpen ||
        state.sessionLost || state.inflight) return Promise.resolve();

    if (!isRetry) state.acceptRetryCount = 0;
    state.acceptRetryCount = state.acceptRetryCount || 0;

    var key = state.acceptKey || D.util.newKey();
    state.acceptKey = key;
    state.inflight = key;
    state.phase = "submitting";
    notify();

    return D.adapters.current.accept(state, { key: key }).then(function (res) {
      state.inflight = null;
      if (res && res.aborted) {
        state.phase = "ready";
        notify();
        return;
      }
      if (!res.ok) {
        applyAcceptError(key, res);
        return;
      }
      Object.assign(state, res.patch || {});
      state.acceptKey = null;
      state.acceptRetryCount = 0;
      state.serviceDown = null;
      state.phase = "ready";
      state.ui.finaleOpen = true;
      notify();
      D.overlays.toast(null, "协议已接受 · 进入终局");
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
        reportFailure(res);
        return;
      }
      if (res.accepted) {
        D.overlays.toast(null, (hadDraft ? "草稿仍保留 · " : "") + "本轮总结已受理（异步），内容本轮不返回");
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
      if (!res.ok) {
        reportFailure(res);
        return;
      }
      Object.assign(state.topic, res.topic);
      notify();
      D.overlays.toast(null, "已切换议题：" + res.topic.name);
    });
  }

  function randomCheck() {
    if (state.ui.finaleOpen) return Promise.resolve();
    return D.adapters.current.randomCheck(state).then(function (res) {
      if (!res.ok) {
        reportFailure(res);
        return;
      }
      state.topic.randomCheck = res.status;
      state.randomWarnings = res.warnings;
      notify();
      D.overlays.toast(null, res.message);
    });
  }

  function newGame() {
    return D.adapters.current.reset(state, { newGame: true }).then(function (fresh) {
      if (fresh && fresh.ok === false) { reportFailure(fresh); return state; }
      init(fresh.state || fresh);
      D.overlays.toast(null, "新一场会话已初始化 · 版本 v" + state.version);
      return state;
    });
  }

  function resetDemo() {
    return D.adapters.current.reset(state, { resetDemo: true }).then(function (fresh) {
      if (fresh && fresh.ok === false) { reportFailure(fresh); return; }
      init(fresh.state || fresh);
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
    open: open,
    cancelInflight: cancelInflight,
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