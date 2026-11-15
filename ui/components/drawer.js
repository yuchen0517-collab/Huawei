(function (D) {
  "use strict";
  D.components = D.components || {};
  var esc = D.dom.esc;

  D.components.drawer = function (s) {
    var pending = D.store.pendingClauses(s);
    var pendingNos = pending.map(function (c) { return c.no; });

    var rows = s.clauses.map(function (c) {
      var statusClass = c.status === "decided" ? "agreed" : (c.status || "open");
      var label = statusClass === "agreed" ? "已决" : (statusClass === "pending" ? "未决" : (statusClass === "open" ? "待确认" : "未知"));
      var val = s.draft[c.id] !== undefined ? s.draft[c.id] : c.mine;
      return '<div class="drow' + (statusClass === "pending" ? " pending" : "") + '">' +
        '<div class="no">' + esc(c.no) + '</div>' +
        '<div class="body"><div class="nm">' + esc(c.name) + '</div>' +
        '<div class="tx">我方：' + esc(val == null ? "—" : val) + ' · 对方（估计）：' + esc(c.theirs == null ? "—" : c.theirs) + '</div></div>' +
        '<span class="st-tag ' + statusClass + '">' + label + '</span></div>';
    }).join("");

    var why = pending.length
      ? '无法接受：存在 <b>' + pending.length + '</b> 条未决条款（第 ' + pendingNos.join("、") + ' 条）。' +
        '原因：尚未被任一方报价覆盖。'
      : "";
    var whyInline = pending.length ? "未决条款未清零" : (s.roundLocked ? "本轮已锁定" : "");
    var acceptDisabled = pending.length > 0 || s.roundLocked || s.inflight || s.sessionLost || !s.clauses.length;

    return '<div class="dh"><h2>协议</h2><span class="ver" id="drVer">v' + s.version + '</span>' +
      '<button class="x" id="drawerClose" data-act="closeDrawer">✕</button></div>' +
      '<div class="dsub"><span>版本号与顶栏、报价板同源</span><span class="same" id="drSame">✓ 三处一致</span></div>' +
      '<div class="dlist" id="dlist">' + (s.clauses.length ? rows : '<div class="empty"><b>协议暂无条款</b><span class="hint">等待条款集下发后即可逐条签署</span></div>') + '</div>' +
      '<div class="dfoot">' +
        '<div id="acceptWhy"' + (why ? ' class="on"' : "") + '>' + why + '</div>' +
        '<div class="btns"><span class="why-inline" id="whyInline">' + whyInline + '</span>' +
        '<button class="btn" id="rejectBtn" data-act="reject">拒绝</button>' +
        '<button class="btn gold" id="acceptBtn" data-act="accept"' + (acceptDisabled ? " disabled" : "") + '>接受协议</button></div>' +
      '</div>';
  };
})(window.D = window.D || {});