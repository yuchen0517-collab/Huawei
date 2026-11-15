(function (D) {
  "use strict";
  D.components = D.components || {};

  function narration(s) {
    if (s.modelDown) {
      return '<div style="color:var(--ink-mute);font-size:12px;line-height:1.7">' +
        '<b style="color:var(--warn)">模型不可用</b> · 战情解说暂无内容。<br>' +
        '这不影响报价板与行动预演：两项数据来自会话状态，不依赖模型生成。</div>' +
        '<div class="src">MODEL_UNAVAILABLE · 已降级为空态</div>';
    }
    if (s.phase === "loading") {
      return '<div class="skel sk-l"></div><div class="skel sk-l m"></div><div class="skel sk-l"></div><div class="skel sk-l s"></div>';
    }
    return '<div id="narration">' + D.dom.esc(s.narration.text) + '</div>' +
      '<div class="src">' + D.dom.esc(s.narration.source) + '</div>';
  }

  D.components.leftColumn = function (s) {
    return '<aside class="col" id="left">' +
      '<section class="panel grow" style="flex:0 0 auto">' +
        '<div class="ph"><h3>战情解说</h3><span class="meta" id="narrMeta">' + (s.modelDown ? "已降级" : "AI 生成") + '</span></div>' +
        '<div class="pb" id="narrBox">' + narration(s) + '</div>' +
      '</section>' +
      '<section class="panel"><div class="ph"><h3>局势摘要</h3><span class="meta">结构化</span></div>' +
        '<div class="pb">' + (s.summaryPoints.length ? '<ul class="sum-list">' +
          s.summaryPoints.map(function (p, i) {
            return '<li><b>0' + (i + 1) + '</b><span>' + D.dom.esc(p) + '</span></li>';
          }).join("") +
        '</ul>' : '<div class="empty compact"><b>暂无结构化摘要</b><span class="hint">模型未返回时不编造要点</span></div>') + '</div>' +
      '</section>' +
      '<section class="panel"><div class="ph"><h3>事实依据</h3><span class="meta">带来源</span></div>' +
        '<div class="pb">' + (s.facts.length ? '<div class="ev">' +
          s.facts.map(function (f) {
            return '<div class="ev-item"><div class="t">' + D.dom.esc(f.t) + '</div>' +
              '<div class="c">' + D.dom.esc(f.c) + '</div>' +
              '<div class="s">' + D.dom.esc(f.s) + '</div></div>';
          }).join("") +
        '</div>' : '<div class="empty compact"><b>暂无可核验依据</b><span class="hint">单方记录不得与可核验来源混排</span></div>') + '</div>' +
      '</section>' +
      '<section class="panel grow"><div class="ph"><h3>会场纪要与事件</h3><span class="meta">R1 → R' + s.round + '</span></div>' +
        '<div class="pb">' + (s.timeline.length ? '<div class="tl">' +
          s.timeline.map(function (t) {
            return '<div class="tl-item"><div class="rt">' + D.dom.esc(t.r) + '</div><div class="tx">' + t.x + '</div></div>';
          }).join("") +
        '</div>' : '<div class="empty compact"><b>本场暂无纪要</b><span class="hint">按轮次记录结论，原文留在对话视图</span></div>') + '</div>' +
      '</section>' +
      '</aside>';
  };
})(window.D = window.D || {});