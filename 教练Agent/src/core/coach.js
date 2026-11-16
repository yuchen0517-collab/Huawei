(function (D) {
  "use strict";

  var GUARD_MS = 8000;
  var RETRY_MS = 3000;
  // C1：按 basis_version 记账；同版本重试期间不重复请求，新版本可并行
  var pending = {};

  // 契约 §1.3：证据可溯源，任一条失败则整条 item 不渲染
  function evidenceOk(ev, s) {
    if (!ev || typeof ev !== "object") return false;
    var round = Number(ev.round);
    if (!(round >= 1 && round <= (s.maxRound || round))) return false;
    if (ev.clause != null && !(s.clauses || []).some(function (c) { return c.name === ev.clause; })) return false;
    if (ev.kind === "action") {
      if (!ev.action_id) return false;
      var ledger = s.actions || {};
      var hit = Object.keys(ledger).some(function (k) {
        return k === ev.action_id || (ledger[k] && ledger[k].action_id === ev.action_id);
      });
      if (!hit) return false;
    }
    return true;
  }

  // 契约 §1.5：双重断言（证据 + 禁用词），命中即过滤并 console.warn，不打扰用户
  function sanitize(coach, s) {
    if (!coach || !Array.isArray(coach.items)) return coach;
    var kept = coach.items.filter(function (item) {
      var evs = Array.isArray(item.evidence) ? item.evidence : [];
      var bad = evs.filter(function (ev) { return !evidenceOk(ev, s); })[0];
      if (bad) {
        console.warn("[coach] filtered item:", item.id, "evidence");
        return false;
      }
      if (D.util.hasLeak(item.title) || D.util.hasLeak(item.text)) {
        console.warn("[coach] filtered item:", item.id, "leak");
        return false;
      }
      return true;
    });
    return Object.assign({}, coach, { items: kept });
  }

  function statusOf(coach) {
    if (!coach || coach.status === "pending") return "pending";
    if (coach.status === "failed") return "failed";
    return "ready";
  }

  // A3：fire-and-forget；教练不改变谈判事实状态，只写 coach / coachStatus。
  // 超时或异常最多自动重试 1 次，之后降级为 failed，不形成轮询。
  function request(s) {
    var key = s.version;
    if (pending[key]) return;
    pending[key] = true;
    D.store.patchCoach({ coachStatus: "pending" });
    var guard = null;
    var retried = false;

    function settle(coach, failed) {
      if (guard) { clearTimeout(guard); guard = null; }
      if (failed && !retried) { retried = true; setTimeout(run, RETRY_MS); return; }
      delete pending[key];
      // 已有更新一轮接管时，旧轮结果不写回，避免覆盖新一轮
      if (Number(key) < Number(D.store.get().version)) return;
      if (failed) {
        D.store.patchCoach({
          coach: { status: "failed", items: [], fail_reason: "模型暂不可用，请稍后重试" },
          coachStatus: "failed"
        });
        return;
      }
      if (!coach) {
        D.store.patchCoach({ coach: null, coachStatus: "idle" });
        return;
      }
      var safe = sanitize(coach, s);
      D.store.patchCoach({ coach: safe, coachStatus: statusOf(safe) });
    }

    function run() {
      guard = setTimeout(function () { settle(null, true); }, GUARD_MS);
      var p;
      try { p = D.adapters.current.coach(s); } catch (e) { p = Promise.reject(e); }
      Promise.resolve(p).then(function (res) {
        if (!res || res.ok === false) return settle(null, true);
        settle(res.coach || null, false);
      }, function () { settle(null, true); });
    }

    run();
  }

  D.coachAgent = { request: request, sanitize: sanitize, evidenceOk: evidenceOk };
})(window.D = window.D || {});