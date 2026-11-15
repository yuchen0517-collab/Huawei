(function (D) {
  "use strict";
  D.components = D.components || {};

  D.components.topbar = function (s) {
    // G2：传输层不可用只改连接态，不伪装成业务错误码
    var down = s.serviceDown;
    var connCls = s.inflight ? "busy" : (s.roundLocked || down ? "down" : "");
    var connTxt = s.inflight ? "处理中" : (s.roundLocked ? "本轮锁定" : (down ? "服务不可用" : "已连接"));
    // G3：真实模式首帧未知轮次显示 R?/6，不用 mock 的 R3/6
    var roundTxt = s.round == null ? "R? / " + s.maxRound : "R" + s.round + " / " + s.maxRound;
    var verTxt = s.version == null ? "v—" : "v" + s.version;
    return '<header id="topbar">' +
      '<div class="brand"><b>DIPLOMAT</b><span>战情室</span></div>' +
      '<div class="tb-sep"></div>' +
      '<div class="tb-id">' +
        '<div class="side us"><span class="dot"></span>我方 · 澜江代表团</div>' +
        '<span class="vs">VS</span>' +
        '<div class="side them"><span class="dot"></span>对方 · 北岸联合体</div>' +
      '</div>' +
      '<div class="tb-sep"></div>' +
      '<div class="tb-metric"><span class="k">ROUND</span><span class="v" id="mRound">' + roundTxt + '</span></div>' +
      '<div class="tb-metric ver" title="全局版本号：与报价板、协议抽屉同源"><span class="k">SESSION VERSION</span><span class="v gold" id="mVer">' + verTxt + '</span></div>' +
      '<div class="tb-spacer"></div>' +
      '<div id="conn" class="' + connCls + '"><span class="led"></span><span id="connTxt">' + connTxt + '</span></div>' +
      '<button class="btn sm" id="demoBtn" data-act="demo">DEMO</button>' +
      '<button class="btn gold" id="finaleBtn" data-act="finale">终局 / 复盘</button>' +
      '</header>';
  };
})(window.D = window.D || {});