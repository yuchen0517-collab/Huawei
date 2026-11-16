(function (D) {
  "use strict";
  D.components = D.components || {};
  var esc = D.dom.esc;

  function tab(s, view, label, badge) {
    return '<button class="tab' + (s.ui.view === view ? " on" : "") + '" data-act="tab" data-view="' + view + '">' +
      label +
      (badge != null ? '<span class="badge" id="bdBadge" style="display:' + (badge > 0 && s.phase !== "loading" ? "inline-block" : "none") + '">' + badge + '</span>' : "") +
      '</button>';
  }

  function skeleton() {
    var out = "";
    for (var i = 0; i < 5; i++) {
      out += '<div class="bd-row">' +
        '<div><div class="skel sk-l m"></div></div>' +
        '<div><div class="skel sk-l"></div></div>' +
        '<div><div class="skel sk-l s"></div></div><div></div></div>';
    }
    return out;
  }

  function row(s, c) {
    var changed = s.draft[c.id] !== undefined;
    var cur = changed ? s.draft[c.id] : c.mine;
    var statusClass = c.status === "decided" ? "agreed" : c.status;
    var label = statusClass === "agreed" ? "已决" : (statusClass === "open" ? "待确认" : "未决");
    var dis = !!s.inflight || s.roundLocked;

    return '<div class="bd-row" data-clause-name="' + esc(c.name) + '" data-clause-id="' + esc(c.id) + '">' +
      '<div class="cl"><span class="no">' + esc(c.no) + '</span><span class="nm">' + esc(c.name) + '</span></div>' +
      '<div><select data-clause="' + esc(c.id) + '"' + (dis ? " disabled" : "") + (changed ? ' class="changed"' : "") + '>' +
        c.opts.map(function (o) {
          return '<option value="' + esc(o) + '"' + (o === cur ? " selected" : "") + '>' + esc(o) + '</option>';
        }).join("") +
      '</select></div>' +
      '<div class="opp"><div class="val"><span class="est-tag">估计</span>' + esc(c.theirs) + '</div>' +
        '<div class="conf"><span class="bar"><i style="width:' + c.conf + '%"></i></span>' + c.conf + '% 可信</div></div>' +
      '<div class="st"><span class="st-tag ' + statusClass + '">' + label + '</span></div>' +
      '</div>';
  }

  function board(s) {
    var conflict = s.conflict
      ? "版本冲突：本地 <b>v" + s.version + "</b>，服务端 <b>v" + s.serverVersion + "</b>。" +
        (Object.keys(s.draft).length ? "草稿 " + Object.keys(s.draft).length + " 处改动已保留。" : "")
      : "";

    var inline = s.inlineError
      ? '<span class="code">' + esc(s.inlineError.error) + '</span><span>' + esc(s.inlineError.detail) + '</span>'
      : "";

    var draftCount = Object.keys(s.draft).length;
    var disabled = !!s.inflight || s.roundLocked || s.conflict || s.phase === "loading" || (!draftCount && !s.selectedCard);
    var btnText = s.inflight ? "提交中…" : (s.retryKey ? "重试提交（同一笔）" : "提交本轮报价");
    var blockReason = (!draftCount && !s.selectedCard) ? "请先修改至少一条条款或选择策略卡（P6）" : "";

    return '<div class="view' + (s.ui.view === "board" ? " on" : "") + '" id="view-board">' +
      '<div id="conflictBar"' + (s.conflict ? ' class="on"' : "") + '>' +
        '<span>⚠</span><span id="conflictTxt">' + conflict + '</span><span class="fill"></span>' +
        '<button class="btn sm gold" id="mergeBtn" data-act="merge">拉取最新并合并</button>' +
      '</div>' +
      '<div id="inlineErr"' + (s.inlineError ? ' class="on"' : "") + '><span class="code" id="ieCode">' +
        (s.inlineError ? esc(s.inlineError.error) : "INVALID_ACTION") + '</span><span id="ieDetail">' +
        (s.inlineError ? esc(s.inlineError.detail) : "") + '</span></div>' +
      '<div class="bd-head"><span>条款</span><span>我方立场</span><span class="est">对方立场 · 估计值</span><span style="text-align:right">状态</span></div>' +
      '<div class="bd-scroll" id="bdScroll">' + (s.phase === "loading" ? skeleton() : (s.clauses.length ? s.clauses.map(function (c) { return row(s, c); }).join("") : '<div class="empty"><b>本场暂无条款</b><span class="hint">等待服务端下发条款集；报价板保持可读</span></div>')) + '</div>' +
      '<div class="bd-foot">' +
        '<span class="note">数据源：服务端会话状态 · 只读派生，前端不计算金额 · 版本 <b id="bdVer">v' + s.version + '</b></span>' +
        '<button class="btn" id="openDrawerBtn" data-act="openDrawer">查看协议</button>' +
        '<button class="btn gold" id="submitBtn" data-act="submit" title="' + esc(blockReason) + '"' + (disabled ? " disabled" : "") + '>' + btnText + '</button>' +
      '</div>' +
      '</div>';
  }

  // B1：对话消息无轮次字段，按 timeline 的 R{n} 分组派生，不新增数据结构
  function dialogueRounds(s) {
    var out = [];
    (s.timeline || []).forEach(function (t) {
      var m = t && String(t.r || "").match(/(\d+)/);
      if (!m) return;
      var n = Number(m[1]);
      if (out.indexOf(n) < 0) out.push(n);
    });
    if (!out.length) out.push(Number(s.round) || 1);
    return out.sort(function (a, b) { return a - b; });
  }

  function dialogue(s) {
    var rounds = dialogueRounds(s);
    var total = s.dialogue.length;
    var msgs = s.dialogue.map(function (m, i) {
      var at = Math.floor(i * rounds.length / Math.max(1, total));
      var r = rounds[at >= rounds.length ? rounds.length - 1 : at];
      return '<div class="msg ' + m.who + '" data-round="' + esc(r) + '"><span class="who">' + esc(m.name) +
        (m.est ? ' <span class="est-tag">意图为估计</span>' : "") + '</span>' +
        '<div class="bub">' + esc(m.text) + '</div></div>';
    }).join("");
    return '<div class="view' + (s.ui.view === "dlg" ? " on" : "") + '" id="view-dlg"><div id="dlg">' +
      '<div id="dlgScroll">' + (s.dialogue.length ? msgs : '<div class="empty compact"><b>暂无对话记录</b><span class="hint">对话仅作复盘素材，不改变结构化报价</span></div>') + '</div>' +
      '<div id="dlgIn"><input id="dlgInput" placeholder="自由表达会进入对话记录，不会进入报价板条款" disabled>' +
      '<span class="tip">对话为复盘素材，不改变结构化报价</span><button class="btn" disabled>发送</button></div>' +
      '</div></div>';
  }

  function intel(s) {
    if (s.modelDown) {
      return '<div class="view' + (s.ui.view === "intel" ? " on" : "") + '" id="view-intel"><div id="intelScroll">' +
        '<div style="grid-column:1/-1;color:var(--ink-mute);font-size:12px;line-height:1.7;padding:8px">' +
        '<b style="color:var(--warn)">情报视图不可用</b> · 模型未返回内容，未生成任何替代性结论。</div>' +
        '</div></div>';
    }
    var cards = s.intelCards.map(function (c) {
      return '<div class="icard"><div class="ih"><h5>' + esc(c.h) + '</h5><span class="est-tag">' + esc(c.tag) + '</span></div>' +
        '<div class="ib">' + esc(c.b) + '</div>' +
        '<div class="if"><span>可信度</span><span class="bar"><i style="width:' + c.conf + '%"></i></span><span>' +
        (c.conf ? c.conf + "%" : "无") + '</span></div></div>';
    }).join("");
    return '<div class="view' + (s.ui.view === "intel" ? " on" : "") + '" id="view-intel"><div id="intelScroll">' +
      (s.intelCards.length ? cards : '<div class="empty compact" style="grid-column:1/-1"><b>暂无情报条目</b><span class="hint">模型未返回内容时不生成替代结论</span></div>') +
      '</div></div>';
  }

  function rehearsal(s) {
    var r = s.rehearsal;
    return '<div id="rehearsal">' +
      '<div class="rh-head"><h4>行动预演</h4><span class="tag">轻量 · 非承诺</span></div>' +
      '<div class="rh-body">' +
        '<div class="rh-cell"><span class="k">预计对方反应</span><span class="v sm" id="rhReact">' + esc(r.react) + '</span></div>' +
        '<div class="rh-cell"><span class="k">行动点消耗</span><span class="v" id="rhAp">' + esc(r.apCost) + '</span></div>' +
        '<div class="rh-cell"><span class="k">风险等级</span><span class="v ' + esc(r.riskClass) + '" id="rhRisk">' + esc(r.riskLevel) + '</span></div>' +
        '<div class="rh-cell"><span class="k">依据</span><span class="v sm" id="rhBasis">' + esc(r.basis) + '</span></div>' +
      '</div></div>';
  }

  D.components.stage = function (s) {
    var pending = D.store.pendingClauses(s).length;
    var draftCount = Object.keys(s.draft).length;
    var acted = Object.keys(s.actions).length;
    return '<section id="stage">' +
      '<div id="tabs">' +
        tab(s, "board", "报价板", pending) +
        tab(s, "dlg", "对话") +
        tab(s, "intel", "情报") +
        '<span class="sp"></span>' +
        '<div class="hint">' +
          '<span class="chip dirty" id="draftChip" style="display:' + (draftCount ? "inline-block" : "none") + '">草稿已保留 · ' + draftCount + ' 处改动</span>' +
          '<span class="chip' + (acted ? " ok" : "") + '" id="actChip">已记账行动 ' + acted + ' 笔</span>' +
        '</div>' +
      '</div>' +
      '<div class="views">' + board(s) + dialogue(s) + intel(s) + '</div>' +
      rehearsal(s) +
      '</section>';
  };
})(window.D = window.D || {});