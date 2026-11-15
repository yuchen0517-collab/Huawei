(function (D) {
  "use strict";
  var esc = D.dom.esc;
  var DEMOS = ["TIMEOUT", "SESSION_BUSY", "VERSION_CONFLICT", "INVALID_ACTION", "MODEL_UNAVAILABLE", "ROUND_LOCKED"];
  var timer = null;

  D.overlays = {
    toast: function (code, detail, raw) {
      var t = document.getElementById("toast");
      if (!t) return;
      t.innerHTML = (code ? '<span class="code">' + esc(code) + '</span>' : '') +
        '<div><div>' + esc(detail) + '</div>' + (raw ? '<span class="js">' + esc(raw) + '</span>' : '') + '</div>';
      t.classList.add("on");
      clearTimeout(timer);
      timer = setTimeout(function () { t.classList.remove("on"); }, 4200);
    },
    demoPanel: function (s) {
      return '<h4>DEMO 控制台</h4>' +
        '<div class="ds">选择下一笔提交要注入的后端错误，用于演示异常态。字段严格遵循 {"error","detail"}。</div>' +
        '<div class="dg" id="dg">' + DEMOS.map(function (c) {
          return '<button class="' + (s.demoError === c ? "on" : "") + '" data-act="demoErr" data-code="' + c + '">' + c + '</button>';
        }).join("") + '</div>' +
        '<button class="dr" id="demoReset" data-act="demoReset">复位场景</button>';
    }
  };
})(window.D = window.D || {});