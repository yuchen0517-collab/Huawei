(function (D) {
  "use strict";
  D.components = D.components || {};

  D.components.topicbar = function (s) {
    var chk = s.topic.randomCheck;
    var cls = chk === "pass" ? "chk pass" : (chk === "conflict" ? "chk warn" : "chk idle");
    var icon = chk === "pass" ? "✓" : (chk === "conflict" ? "!" : "·");
    var text = chk === "pass" ? "随机议题检查：已通过"
      : (chk === "conflict" ? "随机议题检查：发现 1 处冲突" : "随机议题检查：待检查");
    var idx = ("0" + s.topic.index).slice(-2) + " / " + ("0" + s.topic.total).slice(-2);
    return '<div id="topicbar">' +
      '<span class="tag">议题</span>' +
      '<span class="name" id="topicName">' + D.dom.esc(s.topic.name) + '</span>' +
      '<span class="idx" id="topicIdx">' + idx + '</span>' +
      '<span class="fill"></span>' +
      '<div class="' + cls + '" id="randChk" data-act="randomCheck"><i>' + icon + '</i><span>' + text + '</span></div>' +
      '<button class="btn sm" id="nextTopic" data-act="nextTopic">切换议题</button>' +
      '</div>';
  };
})(window.D = window.D || {});