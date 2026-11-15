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

  function readSessionId() {
    if (CONFIG.sessionId) return String(CONFIG.sessionId);
    try {
      return new URLSearchParams(window.location.search).get("session") || "";
    } catch (e) {
      return "";
    }
  }

  var SESSION_ID = readSessionId();

  // A 答复 2026-11-15：当前无鉴权；CORS 由 api.py 的 CORSMiddleware 配置 allow_origins=["*"]
  // TODO 待A确认: 是否需要 Authorization / X-Session-Id 头，跨域由谁配
  function buildHeaders(extra) {
    return Object.assign({ "Content-Type": "application/json" }, extra || {});
  }

  // G1：A 答复 session_id 放 path，不放 query/body/header。
  // TODO 待A确认: 若改为 query/body/header，只改本函数
  function withSession(suffix) {
    if (!SESSION_ID) return suffix;
    return "/session/" + encodeURIComponent(SESSION_ID) + suffix;
  }

  // G2：传输层不可用，不伪装成业务错误码
  function transport(kind, status, text) {
    return {
      kind: kind,
      status: status || 0,
      snippet: String(text == null ? "" : text).slice(0, 200)
    };
  }

  function isTransport(r) {
    return !!(r && r.transport);
  }

  // G3：显式空态，禁止借 mock 的业务数字
  function blankState() {
    return {
      version: 0,
      round: null,
      maxRound: 6,
      ap: null,
      apMax: 3,
      phase: "loading",
      serviceDown: null,
      sessionLost: false,
      slowSeconds: 0,
      slowHint: false,
      currentState: null,
      acceptKey: null,
      acceptRetryCount: 0,
      modelDown: false,
      roundLocked: false,
      conflict: false,
      serverVersion: null,
      inlineError: null,
      inflight: null,
      retryKey: null,
      demoError: null,
      selectedCard: null,
      draft: {},
      clauses: [],
      cards: [],
      actions: {},
      submittedKeys: {},
      openIssues: [],
      speakerScore: null,
      ended: false,
      audit: null,
      randomWarnings: [],
      topic: { name: "—", index: null, total: 6, randomCheck: "idle" },
      us: { leverage: null, timePressure: null, timePressureLabel: "—", gains: null },
      them: { concessionIntent: null, decisionChain: null, confidence: null, lastMove: "—" },
      channels: [],
      hiddenTasks: [],
      batnaComparison: { batna: "—", achieved: null, net_gain: null, better_than_batna: null },
      batnaThem: null,
      narration: { text: "等待服务端返回战情解说。", source: "未加载 · 不生成替代内容" },
      summaryPoints: [],
      facts: [],
      timeline: [],
      intelCards: [],
      dialogue: [],
      finale: { turningPoints: [], pendingHandling: [], reviewPoints: [] },
      rehearsal: { react: "等待服务端返回预演数据", apCost: "—", riskLevel: "—", riskClass: "ok", basis: "—" },
      ui: { view: "board", drawerOpen: false, finaleOpen: false, demoOpen: false }
    };
  }

  // G4：A 答复 offer_patch 与 open_issues 都用议题名，不用条款 id
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
    if (!payload || !payload.error) return null;
    if (SIX.indexOf(payload.error) >= 0) {
      return { error: payload.error, detail: payload.detail || MESSAGES[payload.error] };
    }
    // K2：6 码之外统一映射，不新增前端错误码，detail 原文展示
    return { error: "INVALID_ACTION", detail: payload.detail || payload.error };
  }

  // A 第三轮 Q1：clauses 支持 enum 与 numeric 两种形状
  function clauseFrom(def, offer, i, openIssues) {
    var type = def && def.type === "numeric" ? "numeric" : "enum";
    var opts = type === "numeric" ? [] : ((def && def.options) || []).slice();
    var mine = offer && offer.option != null
      ? offer.option
      : (def && def.initial != null ? def.initial : (opts[0] != null ? opts[0] : "—"));
    if (type === "enum" && mine != null && opts.indexOf(mine) < 0) opts.unshift(mine);
    if (type === "enum" && !opts.length) opts = [mine == null ? "—" : mine];
    var name = (def && def.name) || "—";
    return {
      id: "c" + (i + 1),
      no: ("0" + (i + 1)).slice(-2),
      name: name,
      type: type,
      unit: (def && def.unit) || "",
      range: (def && def.range) || null,
      mine: mine,
      opts: opts,
      theirs: null,
      conf: 0,
      status: openIssues.indexOf(name) >= 0 ? "pending" : "decided"
    };
  }

  // A 答复：所有成功响应都是同一份全量投影，前端整棵替换
  function projectState(state, payload) {
    var my = payload.my_offer || {};
    var opp = payload.opponent_offer || {};
    var offers = my.offers || {};
    var openIssues = Array.isArray(payload.open_issues) ? payload.open_issues : (state.openIssues || []);
    var defs = Array.isArray(payload.clauses) ? payload.clauses : null;
    if (!defs && CONFIG.clauseOptions) {
      defs = Object.keys(CONFIG.clauseOptions).map(function (name) {
        return { name: name, type: "enum", options: CONFIG.clauseOptions[name] };
      });
    }
    var defByName = {};
    if (defs) defs.forEach(function (d) { if (d && d.name) defByName[d.name] = d; });

    var clauses;
    if (defs && defs.length) {
      clauses = defs.map(function (d, i) { return clauseFrom(d, offers[d.name], i, openIssues); });
    } else if (state.clauses.length) {
      clauses = state.clauses.map(function (c, i) {
        var d = defByName[c.name] || {
          name: c.name, type: c.type, options: c.opts,
          initial: c.mine, unit: c.unit, range: c.range
        };
        return clauseFrom(d, offers[c.name], i, openIssues);
      });
    } else if (Object.keys(offers).length) {
      clauses = Object.keys(offers).map(function (name, i) {
        return clauseFrom({ name: name }, offers[name], i, openIssues);
      });
    } else {
      clauses = [];
    }

    var ap = state.ap;
    var apMax = state.apMax;
    if (payload.action_points != null) {
      ap = typeof payload.action_points === "object" ? payload.action_points.current : payload.action_points;
      if (typeof payload.action_points === "object" && payload.action_points.max != null) {
        apMax = payload.action_points.max;
      }
    }

    return {
      version: Math.max(my.version || 0, opp.version || 0) || state.version,
      round: payload.round != null ? payload.round : state.round,
      ap: ap,
      apMax: apMax,
      clauses: clauses,
      openIssues: openIssues,
      speakerScore: payload.speakerScore !== undefined ? payload.speakerScore
        : (payload.speaker_score !== undefined ? payload.speaker_score : state.speakerScore),
      ended: payload.status === "ended" ? true : state.ended,
      serviceDown: null,
      sessionLost: false
    };
  }

  function request(path, options) {
    var ctrl = new AbortController();
    var timedOut = false;
    var timer = setTimeout(function () { timedOut = true; ctrl.abort(); }, TIMEOUT_MS);

    if (options && options.signal) {
      if (options.signal.aborted) ctrl.abort();
      else options.signal.addEventListener("abort", function () { ctrl.abort(); }, { once: true });
    }

    var opts = Object.assign({}, options || {}, { signal: ctrl.signal });
    return fetch(BASE + path, opts)
      .then(function (res) {
        return res.text().then(function (text) {
          var body = null;
          var parseError = false;
          try { body = text ? JSON.parse(text) : null; } catch (e) { parseError = true; }
          return { status: res.status, ok: res.ok, body: body, text: text, parseError: parseError };
        });
      })
      .then(function (r) {
        clearTimeout(timer);
        if (r.status >= 500) {
          if (r.body && r.body.error === "MODEL_UNAVAILABLE") {
            return { status: r.status, ok: false, body: r.body, text: r.text, parseError: false };
          }
          var snippet = (r.body && r.body.detail) ? r.body.detail : r.text;
          return { status: r.status, ok: false, transport: transport("http5xx", r.status, snippet) };
        }
        if (r.parseError) {
          return { status: r.status, ok: false, transport: transport("invalid-json", r.status, r.text) };
        }
        return r;
      })
      .catch(function (err) {
        clearTimeout(timer);
        if (err && err.name === "AbortError") {
          if (timedOut) {
            return { status: 0, ok: false, body: { error: "TIMEOUT", detail: MESSAGES.TIMEOUT } };
          }
          return { status: 0, ok: false, aborted: true };
        }
        return {
          status: 0,
          ok: false,
          transport: transport("network", 0, err && err.message ? err.message : "network error")
        };
      });
  }

  function failure(r, state) {
    if (isTransport(r)) return { ok: false, transport: r.transport };
    if (r.status === 404 && r.body && r.body.error === "SESSION_NOT_FOUND") {
      return {
        ok: false,
        sessionLost: true,
        error: { error: "INVALID_ACTION", detail: r.body.detail || "会话不存在或服务已重启，请重新开局。" }
      };
    }
    if (r.status === 409 && r.body && r.body.error === "SESSION_BUSY") {
      return {
        ok: false,
        retryAfter: 700,
        error: { error: "SESSION_BUSY", detail: r.body.detail || MESSAGES.SESSION_BUSY }
      };
    }
    var e = mapError(r.body);
    if (!e) return { ok: false, transport: transport("invalid-payload", r.status, r.text) };
    return { ok: false, error: e };
  }

  // A 答复：开局 POST /session → {session_id, 全量投影}
  function openSession(config) {
    if (!BASE) {
      return Promise.resolve({
        ok: false,
        transport: transport("config", 0, "httpBase 未配置：保持空框架，等待后端就绪")
      });
    }
    var body = {
      scenario_id: (config && config.scenarioId) || CONFIG.scenarioId || "ai_governance",
      agent: (config && config.agent) || CONFIG.agent || "us"
    };
    var scenarioPath = (config && config.scenarioPath) || CONFIG.scenarioPath;

    body.scenario_path = scenarioPath || null;

    return request("/session", {
      method: "POST",
      headers: buildHeaders(),
      body: JSON.stringify(body)
    }).then(function (r) {
      if (isTransport(r)) return { ok: false, transport: r.transport };
      if (r.status === 404) {
        return { ok: false, transport: transport("http404", 404, r.text) };
      }
      if (!r.ok) return failure(r, null);
      if (!r.body || !r.body.session_id) {
        return { ok: false, transport: transport("invalid-payload", r.status, "开局响应缺少 session_id") };
      }
      SESSION_ID = r.body.session_id;
      var state = blankState();
      Object.assign(state, projectState(state, r.body));
      state.phase = "ready";
      return { ok: true, sessionId: SESSION_ID, state: state, raw: r.body };
    });
  }

  function submit(state, ctx) {
    if (!SESSION_ID) {
      return Promise.resolve({
        ok: false,
        error: { error: "INVALID_ACTION", detail: "尚未开局（缺少 session_id），请先重新开局。" }
      });
    }
    var body = buildRequest(state, ctx.key);
    if (!body.action_type) {
      return Promise.resolve({ ok: false, error: { error: "INVALID_ACTION", detail: "空草稿且未选卡，禁止提交（P6）。" } });
    }

    return request(withSession("/action"), {
      method: "POST",
      headers: buildHeaders(),
      body: JSON.stringify(body),
      signal: ctx.signal
    }).then(function (r) {
      if (r.aborted) return { ok: false, aborted: true };
      if (isTransport(r)) return { ok: false, transport: r.transport };

      if (r.status === 409) {
        if (r.body && r.body.error === "SESSION_BUSY") {
          return {
            ok: false,
            retryAfter: 700,
            error: { error: "SESSION_BUSY", detail: r.body.detail || MESSAGES.SESSION_BUSY }
          };
        }
        return {
          ok: false,
          patch: {
            serverVersion: newestVersion(r.body && r.body.current_state, state.version + 1),
            currentState: (r.body && r.body.current_state) || null
          },
          error: mapError(Object.assign({ error: "VERSION_CONFLICT" }, r.body || {})) ||
            { error: "VERSION_CONFLICT", detail: MESSAGES.VERSION_CONFLICT }
        };
      }

      if (!r.ok) return failure(r, state);
      if (!r.body) return { ok: false, transport: transport("invalid-payload", r.status, "空响应体") };

      var patch = projectState(state, r.body);
      patch.draft = {};
      patch.selectedCard = null;
      patch.retryKey = null;
      patch.demoError = null;
      patch.submittedKeys = Object.assign({}, state.submittedKeys, (function () { var o = {}; o[ctx.key] = true; return o; })());
      patch.actions = Object.assign({}, state.actions, (function () {
        var o = {};
        o[ctx.key] = { key: ctx.key, round: state.round, at: new Date().toISOString(), ap: 1 };
        return o;
      })());
      return { ok: true, patch: patch };
    });
  }

  function newestVersion(payload, fallback) {
    if (!payload) return fallback;
    var my = payload.my_offer || {};
    var opp = payload.opponent_offer || {};
    var v = Math.max(my.version || 0, opp.version || 0);
    return v || fallback;
  }

  // K1：409 的 current_state 优先用于合并，缺失时才 GET /state
  function merge(state) {
    if (state && state.currentState) {
      var patch = projectState(state, state.currentState);
      patch.conflict = false;
      patch.serverVersion = null;
      patch.currentState = null;
      patch.draft = state.draft;
      patch.selectedCard = state.selectedCard;
      return Promise.resolve({ ok: true, patch: patch });
    }
    return request(withSession("/state"), { method: "GET", headers: buildHeaders() }).then(function (r) {
      if (!r.ok) return failure(r, state);
      if (!r.body) return { ok: false, transport: transport("invalid-payload", r.status, "空响应体") };
      var p = projectState(state, r.body);
      p.conflict = false;
      p.serverVersion = null;
      p.currentState = null;
      p.draft = state.draft;
      p.selectedCard = state.selectedCard;
      return { ok: true, patch: p };
    });
  }

  // A 第二轮 Q1：accept 走 /action，action_type="accept"，offer_patch 必须 {}
  function accept(state, ctx) {
    if (!SESSION_ID) {
      return Promise.resolve({
        ok: false,
        error: { error: "INVALID_ACTION", detail: "尚未开局（缺少 session_id），请先重新开局。" }
      });
    }
    var key = (ctx && ctx.key) || D.util.newKey();
    var body = {
      client_action_id: key,
      base_version: state.version,
      action_type: "accept",
      offer_patch: {},
      conditions: [],
      expected_effect: "我方接受当前已达成的条款框架。",
      public_message: "我方正式接受本轮协议安排。"
    };

    return request(withSession("/action"), {
      method: "POST",
      headers: buildHeaders(),
      body: JSON.stringify(body),
      signal: ctx && ctx.signal
    }).then(function (r) {
      if (r.aborted) return { ok: false, aborted: true };
      if (isTransport(r)) return { ok: false, transport: r.transport };

      if (r.status === 409) {
        if (r.body && r.body.error === "SESSION_BUSY") {
          return {
            ok: false,
            retryAfter: 700,
            error: { error: "SESSION_BUSY", detail: r.body.detail || MESSAGES.SESSION_BUSY }
          };
        }
        return {
          ok: false,
          patch: {
            serverVersion: newestVersion(r.body && r.body.current_state, state.version + 1),
            currentState: (r.body && r.body.current_state) || null
          },
          error: mapError(Object.assign({ error: "VERSION_CONFLICT" }, r.body || {})) ||
            { error: "VERSION_CONFLICT", detail: MESSAGES.VERSION_CONFLICT }
        };
      }

      if (!r.ok) return failure(r, state);
      if (!r.body) return { ok: false, transport: transport("invalid-payload", r.status, "空响应体") };

      var patch = projectState(state, r.body);
      patch.draft = {};
      patch.selectedCard = null;
      patch.retryKey = null;
      patch.demoError = null;
      patch.submittedKeys = Object.assign({}, state.submittedKeys, (function () { var o = {}; o[key] = true; return o; })());
      patch.actions = Object.assign({}, state.actions, (function () {
        var o = {};
        o[key] = { key: key, round: state.round, at: new Date().toISOString(), ap: 0 };
        return o;
      })());
      return { ok: true, patch: patch };
    });
  }

  // A 答复：summary 走 POST /session/{id}/debrief，HTTP 202 {status:"accepted"}
  function summary(state) {
    return request(withSession("/debrief"), {
      method: "POST",
      headers: buildHeaders(),
      body: JSON.stringify({ base_version: state.version, round: state.round })
    }).then(function (r) {
      if (!r.ok) return failure(r, state);
      return { ok: true, accepted: true, status: (r.body && r.body.status) || "accepted" };
    });
  }

  // A 答复：无会话内议题切换接口，换议题 = 重新开局
  function nextTopic() {
    return Promise.resolve({
      ok: false,
      error: { error: "INVALID_ACTION", detail: "会话内不支持切换议题；换议题需重新开局（A 答复 G7）。" }
    });
  }

  // A 答复：随机检查随全量投影下发，前端不再单独调用
  function randomCheck() {
    return Promise.resolve({
      ok: false,
      error: { error: "INVALID_ACTION", detail: "随机检查随全量投影下发，前端不再单独调用（A 答复）。" }
    });
  }

  // A 答复：无 reset 接口；重新开局 = POST /session
  function reset(state, opts) {
    return openSession(opts || {});
  }

  D.adapters.http = {
    id: "http",
    messages: MESSAGES,
    createState: blankState,
    openSession: openSession,
    rehearsal: function (state) { return state.rehearsal; },
    submit: submit,
    merge: merge,
    accept: accept,
    summary: summary,
    nextTopic: nextTopic,
    randomCheck: randomCheck,
    reset: reset,
    buildHeaders: buildHeaders,
    withSession: withSession
  };
})(window.D = window.D || {});