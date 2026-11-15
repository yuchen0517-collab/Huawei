(function (D) {
  "use strict";
  D.components = D.components || {};

  D.components.hand = function (s) {
    var cards = s.cards.map(function (k) {
      var sel = s.selectedCard === k.id;
      var dis = s.roundLocked || s.phase === "loading" || k.cost > s.ap;
      return '<button class="card' + (sel ? " sel" : "") + '" data-act="card" data-id="' + D.dom.esc(k.id) + '"' +
        (dis ? " disabled" : "") + '>' +
        '<div class="ct">' + D.dom.esc(k.title) + '</div>' +
        '<div class="cd">' + D.dom.esc(k.desc) + '</div>' +
        '<div class="cc"><span class="ap">◆</span>' + k.cost + ' 行动点</div>' +
        '</button>';
    }).join("");

    var pips = "";
    for (var i = 0; i < s.apMax; i++) pips += '<span class="pip' + (i < s.ap ? "" : " off") + '"></span>';
    pips += '<span class="n">' + s.ap + ' / ' + s.apMax + '</span>';

    // K3=B：按钮为「提交本轮总结」，不推进轮次
    return '<footer id="hand">' +
      '<div class="cards" id="cards">' + (s.cards.length ? cards : '<div class="empty compact"><b>暂无可用策略卡</b><span class="hint">仍可编辑条款并提交</span></div>') + '</div>' +
      '<div class="hand-side"><div class="ap-box"><span class="k">行动点</span><div class="pips" id="pips">' + pips + '</div></div></div>' +
      '<button id="endRound" data-act="endRoundSummary"' +
        (s.roundLocked || s.inflight || s.phase === "loading" ? " disabled" : "") + '>提交本轮总结</button>' +
      '</footer>';
  };
})(window.D = window.D || {});