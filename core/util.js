(function (D) {
  "use strict";

  function newKey() {
    return "act-" + Date.now() + "-" + Math.random().toString(36).slice(2, 7);
  }

  function gradeOf(n) {
    return n >= 90 ? "S" : n >= 70 ? "A" : n >= 50 ? "B" : n >= 30 ? "C" : "D";
  }

  function v(n) { return "v" + n; }

  D.util = { newKey: newKey, gradeOf: gradeOf, v: v };
})(window.D = window.D || {});