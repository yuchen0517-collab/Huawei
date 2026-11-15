(function (D) {
  "use strict";

  function newKey() {
    return "act-" + Date.now() + "-" + Math.random().toString(36).slice(2, 7);
  }

  function gradeOf(n) {
    return n >= 90 ? "S" : n >= 70 ? "A" : n >= 50 ? "B" : n >= 30 ? "C" : "D";
  }

  function v(n) { return "v" + n; }

  // C 回 D（2026-11-15）：可信度百分比改为定性分级，规则公开在 tooltip。
  // 仅用于对方估计值的展示，不是业务真值；组件只读 label/pct/cls。
  var CONF_TIP = "可信度分级（前端按线索推导，非对方真值）：高 ≥70；中 40–69；低 1–39；未知 无数据。";
  function confidenceLevel(value) {
    var n = (value == null || value === "") ? null : Number(value);
    if (n == null || isNaN(n) || n <= 0) {
      return { label: "未知", cls: "unknown", pct: 0, tip: CONF_TIP };
    }
    if (n >= 70) return { label: "高", cls: "high", pct: 100, tip: CONF_TIP };
    if (n >= 40) return { label: "中", cls: "mid", pct: 60, tip: CONF_TIP };
    return { label: "低", cls: "low", pct: 30, tip: CONF_TIP };
  }

  D.util = { newKey: newKey, gradeOf: gradeOf, v: v, confidenceLevel: confidenceLevel };
})(window.D = window.D || {});