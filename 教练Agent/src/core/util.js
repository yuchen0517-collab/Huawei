(function (D) {
  "use strict";

  function newKey() {
    return "act-" + Date.now() + "-" + Math.random().toString(36).slice(2, 7);
  }

  function gradeOf(n) {
    return n >= 90 ? "S" : n >= 70 ? "A" : n >= 50 ? "B" : n >= 30 ? "C" : "D";
  }

  function v(n) { return "v" + n; }

  // T6 / K7：教练建议禁用词（小写归一后做包含匹配）
  var LEAK_WORDS = ["对方红线", "对方真实", "对方batna", "真实底线", "私有", "net_gain", "隐藏底牌"];

  function hasLeak(text) {
    var t = String(text == null ? "" : text).toLowerCase().replace(/\s+/g, "");
    return LEAK_WORDS.some(function (w) { return t.indexOf(w) >= 0; });
  }

  D.util = { newKey: newKey, gradeOf: gradeOf, v: v, LEAK_WORDS: LEAK_WORDS, hasLeak: hasLeak };
})(window.D = window.D || {});