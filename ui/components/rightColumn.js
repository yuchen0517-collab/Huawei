(function (D) {
  "use strict";
  D.components = D.components || {};

  // G3：业务字段未知时显示占位符，不用 0 或 mock 值填充
  function num(v) { return v == null ? "—" : v; }
  function pctWidth(v) { return v == null ? 0 : v; }

  D.components.rightColumn = function (s) {
    var chans = s.channels.map(function (c) {
      var ok = c.status === "ready";
      return '<div class="chan-row"><span class="n">' + D.dom.esc(c.name) + '</span>' +
        '<span class="chip mini ' + (ok ? "ok" : "bad") + '">' + (ok ? "可用" : "冷却中") + '</span></div>';
    }).join("");

    var tasks = s.hiddenTasks.map(function (t) {
      return '<div class="task-row' + (t.done ? " done" : "") + '">' +
        '<span class="box' + (t.done ? " done" : "") + '">' + (t.done ? "✓" : "") + '</span>' +
        '<span>' + D.dom.esc(t.text) + '</span></div>';
    }).join("");

    var doneCount = s.hiddenTasks.filter(function (t) { return t.done; }).length;
    var readyChans = s.channels.filter(function (c) { return c.status === "ready"; }).length;
    var conf = D.util.confidenceLevel(s.them.confidence);

    return '<aside class="col" id="right">' +
      '<section class="panel"><div class="ph"><h3>我方态势</h3><span class="meta">真实值</span></div>' +
        '<div class="pb"><div class="kv">' +
          '<div class="meter"><div class="lab"><span>谈判筹码</span><b>' + num(s.us.leverage) + ' / 100</b></div><div class="track"><i style="width:' + pctWidth(s.us.leverage) + '%"></i></div></div>' +
          '<div class="meter"><div class="lab"><span>时间压力</span><b>' + D.dom.esc(s.us.timePressureLabel || "—") + '</b></div><div class="track"><i class="warn" style="width:' + pctWidth(s.us.timePressure) + '%"></i></div></div>' +
          '<div class="kv-row"><span class="k">已获让步</span><span class="v">' + (s.us.gains == null ? "—" : s.us.gains + " 项") + '</span></div>' +
          '<div class="kv-row"><span class="k">本轮行动点</span><span class="v big" id="rvAp">' + (s.ap == null ? "—" : s.ap) + ' / ' + s.apMax + '</span></div>' +
        '</div></div>' +
      '</section>' +
      '<section class="panel"><div class="ph"><h3>对方态势</h3><span class="meta">估计值</span></div>' +
        '<div class="pb">' +
          '<div class="est-banner"><i>◈</i><span>以下全部为估计值与可信度，非对方真实底牌</span></div>' +
          '<div class="kv">' +
            '<div class="meter"><div class="lab"><span>让步意愿 <span class="est-tag">估计</span></span><b>' + (s.them.concessionIntent == null ? "—" : s.them.concessionIntent + "%") + '</b></div><div class="track"><i style="width:' + pctWidth(s.them.concessionIntent) + '%"></i></div></div>' +
            '<div class="meter"><div class="lab"><span>决策链长度 <span class="est-tag">估计</span></span><b>' + (s.them.decisionChain == null ? "—" : s.them.decisionChain + " 层") + '</b></div><div class="track"><i style="width:' + (s.them.decisionChain == null ? 0 : 45) + '%"></i></div></div>' +
            '<div class="kv-row"><span class="k">数据可信度</span><span class="v"><span class="conf-level ' + conf.cls + '" title="' + D.dom.esc(conf.tip) + '">估计 · ' + conf.label + '</span></span></div>' +
            '<div class="kv-row"><span class="k">最近动作</span><span class="v">' + D.dom.esc(s.them.lastMove || "—") + '</span></div>' +
          '</div>' +
        '</div>' +
      '</section>' +
      '<section class="panel"><div class="ph"><h3>外交渠道</h3><span class="meta">' + readyChans + ' / ' + s.channels.length + ' 可用</span></div>' +
        '<div class="pb"><div class="chan">' + (s.channels.length ? chans : '<div class="empty compact"><b>暂无可用渠道</b></div>') + '</div></div>' +
      '</section>' +
      '<section class="panel"><div class="ph"><h3>隐藏任务</h3><span class="meta">' + doneCount + ' / ' + s.hiddenTasks.length + ' 完成</span></div>' +
        '<div class="pb"><div class="task">' + (s.hiddenTasks.length ? tasks : '<div class="empty compact"><b>本场无隐藏任务</b></div>') + '</div></div>' +
      '</section>' +
      '<section class="panel"><div class="ph"><h3>BATNA</h3><span class="meta">最佳替代方案</span></div>' +
        '<div class="pb"><div class="batna">' +
          '<div class="batna-row"><div class="k">我方</div><div class="v">' + D.dom.esc(s.batnaComparison.batna || "—") + '</div></div>' +
          '<div class="batna-row unknown"><div class="k">对方</div><div class="v">未知 · 无任何可核验线索，不参与推演</div></div>' +
        '</div></div>' +
      '</section>' +
      '</aside>';
  };
})(window.D = window.D || {});