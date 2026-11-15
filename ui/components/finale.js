(function (D) {
  "use strict";
  D.components = D.components || {};
  var esc = D.dom.esc;

  var SCORE_DEF = [
    { k: "position_clarity", label: "立场清晰度", w: 30 },
    { k: "diplomatic_tact", label: "外交策略运用", w: 30 },
    { k: "emotional_control", label: "情绪控制力", w: 20 },
    { k: "substance_quality", label: "实质内容质量", w: 20 }
  ];

  D.components.finale = function (s) {
    var sc = s.speakerScore;
    // K5：只以 speaker_score===null 判定，不用 round===1 兜底
    var isNull = !sc;
    var grade = isNull ? "—" : D.util.gradeOf(sc.total);
    var note = isNull
      ? "四维评分自对方首次发言后开始计算。"
      : "总分与四维分均由服务端 speaker_score 返回，前端只做展示与评级映射。";

    var dims = isNull ? "" : SCORE_DEF.map(function (d) {
      var v = sc[d.k];
      return '<div class="fdim"><div class="dl"><span>' + d.label + ' · ' + d.w + '%</span><b>' + v + '</b></div>' +
        '<div class="track"><i style="width:' + v + '%"></i></div></div>';
    }).join("");

    var feedback = isNull
      ? "首轮不计分：第 1 轮对方尚未发言，speaker_score 返回 null，不填零分，也不生成替代分数。"
      : sc.feedback;

    return '<div class="fbox">' +
      '<div class="fhead"><div class="txt"><div class="k">终局 · 基础复盘</div><h2>协议达成 · 有限共识</h2></div>' +
        '<button class="btn" id="finaleClose" data-act="closeFinale">返回会场</button></div>' +
      '<div class="fbody">' +
        '<div class="fcard wide"><h4>结局判定 · 发言评分 speaker_score</h4>' +
          '<div class="fscore-wrap"><div class="fgrade' + (isNull ? " null" : "") + '" id="fGrade">' + grade + '</div>' +
            '<div class="fscore-main"><div class="score"><span class="n" id="fScore">' + (isNull ? "—" : sc.total) + '</span>' +
            '<span class="d">/ 100 · 四维加权：立场 30% / 策略 30% / 情绪 20% / 内容 20%</span></div>' +
            '<div class="fdims" id="fDims">' + dims + '</div></div></div>' +
          '<div class="ffeedback' + (isNull ? " null" : "") + '" id="fFeedback">' + esc(feedback) + '</div>' +
          '<div class="fnote" id="fScoreNote">' + note + '</div>' +
        '</div>' +
        '<div class="fcard"><h4>关键转折</h4><ul>' +
          s.finale.turningPoints.map(function (x) { return '<li><b>' + esc(x.k) + '</b><span>' + esc(x.t) + '</span></li>'; }).join("") +
        '</ul></div>' +
        '<div class="fcard"><h4>未决条款处理</h4><ul>' +
          s.finale.pendingHandling.map(function (x) { return '<li><b>' + esc(x.k) + '</b><span>' + esc(x.t) + '</span></li>'; }).join("") +
        '</ul></div>' +
        '<div class="fcard"><h4>复盘要点</h4><ul>' +
          s.finale.reviewPoints.map(function (x) { return '<li><b>' + esc(x.k) + '</b><span>' + esc(x.t) + '</span></li>'; }).join("") +
        '</ul></div>' +
        '<div class="fcard"><h4>数据来源声明</h4><p>本轮所有数字来自同一份服务端会话状态，版本 <span id="fv">v' + s.version + '</span>。模型生成内容已在左栏单独标注，未计入任何收益数据。</p></div>' +
      '</div>' +
      '<div class="ffoot"><button class="btn" id="toStory" data-act="exportStory">导出复盘记录</button>' +
        '<button class="btn gold" id="toNew" data-act="newGame">开始新一场</button></div>' +
      '</div>';
  };
})(window.D = window.D || {});