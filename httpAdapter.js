(function (D) {
  "use strict";

  var CONFIG = window.DIPLOMAT_CONFIG || {};
  var BASE = CONFIG.httpBase || "";
  var TIMEOUT_MS = CONFIG.timeoutMs || 150000;
  var SIX = ["INVALID_ACTION", "SESSION_BUSY", "MODEL_UNAVAILABLE", "ROUND_LOCKED", "VERSION_CONFLICT", "TIMEOUT"];

  var MESSAGES = {
    INVALID_ACTION: "该行动不满足当前条款约束，未生效。",
    SESSION_BUSY: "会话正被另一笔行动占用，请求排队中。",
    MODEL_UNAVAILABLE: "解说与情报模型暂不可用，报价板不受影响。",
    ROUND_LOCKED: "本轮已锁定，无法再提交行动。",
    VERSION_CONFLICT: "客户端版本落后于服务端，需合并后重提。",
    TIMEOUT: "上游未在时限内返回，草稿已保留。"
  };

  function blankState() {
    var s = D.adapters.mock.createState();
    s.phase = "loading";
    s.clauses = [];
    s.cards = [];
    s.version = 0;
    return s;
  }

  function toOfferPatch(state) {
    var patch = {};
    Object.keys(state.draft).forEach(function (id) {
      var c = state.clauses.filter(function (x) { return x.id === id; })[0];
      if (!c) return;
      patch[c.name] = { option: state.draft[id], note: "我方立场调整为 " + state.draft[id] + "。" };
    });
    return patch;
  }

  function deriveActionType(state) {
    var hasDraft = Object.keys(state.draft).length > 0;
    var hasCard = !!state.selectedCard;
    if (hasDraft && hasCard) return "conditional_exchange";
    if (hasDraft) return "counter_offer";
    if (hasCard) return "probe";
    return null;
  }

  function expectedEffect(state) {
    var first = Object.keys(state.draft)[0];
    var c = first && state.clauses.filter(function (x) { return x.id === first; })[0];
    if (c) return "推动对方就「" + c.name + "」继续磋商。";
    return "试探对方本轮出价取向。";
  }

  function publicMessage(state) {
    var first = Object.keys(state.draft)[0];
    var c = first && state.clauses.filter(function (x) { return x.id === first; })[0];
    if (c) return "我方提议将「" + c.name + "」调整为 " + state.draft[first] + "。";
    return "我方暂不调整条款，先观察对方出价。";
  }

  function buildRequest(state, key) {
    return {
      client_action_id: key,
      base_version: state.version,
      action_type: deriveActionType(state),
      offer_patch: toOfferPatch(state),
      conditions: [],
      expected_effect: expectedEffect(state),
      public_message: publicMessage(state)
    };
  }

  function mapError(payload) {
    if (!payload || !payload.error) {
      return { error: "INVALID_ACTION", detail: "响应缺少 error 字段，已按行动未生效处理。" };
    }
    if (SIX.indexOf(payload.error) >= 0) {
      return { error: payload.error, detail: payload.detail || MESSAGES[payload.error] };
    }
    // K2：6 码之外统一映射，不新增前端错误码，detail 原文展示
    return { error: "INVALID_ACTION", detail: payload.detail || payload.error };
  }

  function newestVersion(payload, fallback) {
    var my = payload.my_offer || {};
    var opp = payload.opponent_offer || {};
    var v = Math.max(my.version || 0, opp.version || 0);
    return v || fallback;
  }

  function toPatch(payload, state, key) {
    var patch = {
      version: newestVersion(payload, state.version),
      draft: {},
      selectedCard: null,
      retryKey: null,
      demoError: null,
      submittedKeys: Object.assign({}, state.submittedKeys, { [key]: true })
    };
    if (payload.round != null) patch.round = payload.round;
    if (payload.action_points != null) {
      patch.ap = typeof payload.action_points === "object" ? payload.action_points.current : payload.action_points;
    }
    if (Array.isArray(payload.open_issues)) {
      patch.openIssues = payload.open_issues;
      patch.clauses = state.clauses.map(function (c) {
        var pending = payload.open_issues.indexOf(c.name) >= 0;
        var mine = (payload.my_offer && payload.my_offer.clauses && payload.my_offer.clauses[c.name]) || c.mine;
        return Object.assign({}, c, { mine: mine, status: pending ? "pending" : "decided" });
      });
    }
    if (payload.status === "ended") patch.ended = true;
    if (payload.speaker_score !== undefined) patch.speakerScore = payload.speaker_score;
    return patch;
  }

  function request(path, options) {
    var ctrl = new AbortController();
    var timer = setTimeout(function () { ctrl.abort(); }, TIMEOUT_MS);
    return fetch(BASE + path, Object.assign({ signal: ctrl.signal }, options))
      .then(function (res) {
        return res.text().then(function (text) {
          var body = null;
          try { body = text ? JSON.parse(text) : null; } catch (e) { body = null; }
          return { status: res.status, ok: res.ok, body: body, text: text };
        });
      })
      .then(function (r) { clearTimeout(timer); return r; })
      .catch(function (err) {
        clearTimeout(timer);
        if (err && err.name === "AbortError") {
          return { status: 0, ok: false, body: { error: "TIMEOUT", detail: MESSAGES.TIMEOUT } };
        }
        return { status: 0, ok: false, body: { error: "SESSION_BUSY", detail: "网络不可达，请稍后重试。" } };
      });
  }

  function submit(state, ctx) {
    var body = buildRequest(state, ctx.key);
    if (!body.action_type) {
      return Promise.resolve({ ok: false, error: { error: "INVALID_ACTION", detail: "空草稿且未选卡，禁止提交（P6）。" } });
    }
    return request(CONFIG.submitPath || "/session/actions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (r) {
      if (r.status === 409) {
        return {
          ok: false,
          patch: { serverVersion: newestVersion(r.body || {}, state.version + 1) },
          error: mapError(Object.assign({ error: "VERSION_CONFLICT" }, r.body || {}))
        };
      }
      if (!r.ok) return { ok: false, error: mapError(r.body), retryAfter: r.status === 503 ? 700 : 0 };
      return { ok: true, patch: toPatch(r.body || {}, state, ctx.key) };
    });
  }

  function merge(state) {
    return request(CONFIG.statePath || "/session/state", { method: "GET" }).then(function (r) {
      if (!r.ok) return { ok: false, error: mapError(r.body) };
      var payload = r.body || {};
      var patch = toPatch(payload, state, "__merge__");
      delete patch.submittedKeys;
      patch.conflict = false;
      patch.serverVersion = null;
      patch.draft = state.draft;
      patch.selectedCard = state.selectedCard;
      return { ok: true, patch: patch };
    });
  }

  function accept(state) {
    return request(CONFIG.acceptPath || "/session/accept", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ base_version: state.version })
    }).then(function (r) {
      if (!r.ok) return { ok: false, error: mapError(r.body) };
      return { ok: true, audit: (r.body && r.body.audit) || { ok: true, issues: [], summary: { blocking: 0, warning: 0 } } };
    });
  }

  function summary(state) {
    return request(CONFIG.summaryPath || "/session/summary", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ round: state.round, base_version: state.version })
    }).then(function (r) {
      if (!r.ok) return { ok: false, error: mapError(r.body) };
      return { ok: true, timeline: state.timeline };
    });
  }

  function nextTopic() {
    return request(CONFIG.topicPath || "/session/topic", { method: "GET" }).then(function (r) {
      if (!r.ok) return { ok: false, error: mapError(r.body) };
      return { ok: true, topic: r.body };
    });
  }

  function randomCheck(state) {
    return request(CONFIG.checkPath || "/session/random-check", { method: "POST" }).then(function (r) {
      if (!r.ok) return { ok: false, error: mapError(r.body) };
      var warnings = (r.body && r.body.warnings) || [];
      return {
        ok: true,
        status: warnings.length ? "conflict" : "pass",
        warnings: warnings,
        message: warnings.length ? "随机检查发现冲突，已标记待确认（不阻塞提交）" : "随机议题检查：已通过"
      };
    });
  }

  function reset(state, opts) {
    return request(CONFIG.resetPath || "/session/reset", { method: "POST" }).then(function () {
      var s = blankState();
      s.phase = "ready";
      return s;
    });
  }

  D.adapters.http = {
    id: "http",
    messages: MESSAGES,
    createState: blankState,
    rehearsal: function (state) { return state.rehearsal; },
    submit: submit,
    merge: merge,
    accept: accept,
    summary: summary,
    nextTopic: nextTopic,
    randomCheck: randomCheck,
    reset: reset
  };
})(window.D = window.D || {});