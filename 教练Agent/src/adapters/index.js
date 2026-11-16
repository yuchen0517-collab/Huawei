(function (D) {
  "use strict";

  var CONFIG = window.DIPLOMAT_CONFIG || {};
  var current = CONFIG.adapter === "http" ? D.adapters.http : D.adapters.mock;

  function use(name) {
    current = name === "http" ? D.adapters.http : D.adapters.mock;
    return current;
  }

  // 适配层统一签名；第 5 天只改 current 的指向，不改任何调用点
  D.adapters.current = current;
  D.adapters.use = use;
  D.adapters.signature = [
    "createState", "rehearsal", "submit", "merge",
    "accept", "summary", "nextTopic", "randomCheck", "reset", "coach"
  ];
})(window.D = window.D || {});