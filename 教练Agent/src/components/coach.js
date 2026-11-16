(function (D) {
  "use strict";
  D.components = D.components || {};
  var esc = D.dom.esc;

  var KIND_LABEL = { stage: "阶段建议", alternative: "替代行动" };

  // B1：证据可点击定位；kind 为 action / offer / event，clause 为空时不写该属性
  function evidenceList(evs) {
    if (!evs || !evs.length) return "";
    return '<div class="coach-ev">' + evs.map(function (ev) {
      var kind = ev.kind == null ? "" : ev.kind;
      return '<button type="button" class="coach-ev-i" data-act="coachEvidence"' +
        ' data-round="' + esc(ev.round) + '"' +
        (ev.clause == null || ev.clause === "" ? "" : ' data-clause="' + esc(ev.clause) + '"') +
        ' data-ev-kind="' + esc(kind) + '"' +
        ' aria-label="定位到 R' + esc(ev.round) + " " + esc(ev.label) + '">' +
        '<b>R' + esc(ev.round) + '</b>' + esc(ev.label) + '</button>';
    }).join("") + "</div>";
  }

  // 只读渲染：apply_hint 仅作灰字提示，绝不生成「一键应用」入口
  function item(it) {
    var kind = it.kind === "alternative" ? "alternative" : "stage";
    return '<article class="coach-item" data-coach-id="' + esc(it.id) + '">' +
      '<div class="coach-item-h"><span class="coach-kind ' + kind + '">' + KIND_LABEL[kind] + "</span>" +
        "<b>" + esc(it.title) + "</b></div>" +
      "<p>" + esc(it.text) + "</p>" +
      evidenceList(it.evidence) +
      (it.ap_cost == null ? "" : '<div class="coach-ap">预计消耗 ' + esc(String(it.ap_cost)) + " 行动点</div>") +
      (it.apply_hint ? '<div class="coach-hint">' + esc(it.apply_hint) + "</div>" : "") +
      "</article>";
  }

  // 三态渲染：pending（呼吸点）/ ready（逐条）/ failed（原因 + 重试）
  D.components.coach = function (s) {
    var st = s.coachStatus || "idle";
    var coach = s.coach;
    var items = coach && Array.isArray(coach.items) ? coach.items : [];
    var collapsed = s.coachCollapsed !== false;
    var ver = coach && coach.basis_version;
    var stale = st === "ready" && typeof ver === "number" && ver < s.version;

    var head = st === "pending" ? "教练建议生成中"
      : st === "ready" ? "教练建议 · " + items.length + " 条 · 基于 v" + ver
        : st === "failed" ? "教练建议暂不可用"
          : "教练建议";

    var meta = st === "pending" ? '<span class="coach-dot" aria-hidden="true"></span><span>异步生成</span>'
      : st === "ready" ? (stale ? '<span class="coach-stale">基于 v' + esc(ver) + " 的建议</span>" : "<span>不阻塞下一轮</span>")
        : st === "failed" ? '<span class="coach-stale">' + esc(coach && coach.fail_reason ? coach.fail_reason : "生成失败") + "</span>"
          : "<span>提交本轮报价后生成</span>";

    var body = "";
    if (!collapsed) {
      if (st === "ready") {
        body = items.length
          ? items.map(item).join("")
          : '<div class="empty compact"><b>本轮暂无建议</b><span class="hint">模型返回空数组，不编造建议</span></div>';
      } else if (st === "pending") {
        body = '<div class="coach-wait">正在分析本轮策略选择，不影响你继续改条款或提交下一轮。</div>';
      } else if (st === "failed") {
        body = '<div class="coach-wait">' + esc(coach && coach.fail_reason ? coach.fail_reason : "生成失败") + "</div>" +
          '<button class="btn coach-retry" data-act="coachRetry">重试</button>';
      } else {
        body = '<div class="coach-wait">本轮提交成功后异步生成，不占用行动点、不改变报价。</div>';
      }
    }

    return '<section class="panel coach" id="coachPanel">' +
      '<div class="ph"><h3>' + esc(head) + "</h3>" +
        '<span class="meta">' + meta + "</span>" +
        '<button class="coach-toggle" data-act="coachToggle" aria-expanded="' + (!collapsed) + '">' +
          (collapsed ? "展开" : "收起") + "</button></div>" +
      (!collapsed ? '<div class="pb coach-pb">' + body + "</div>" : "") +
      "</section>";
  };
})(window.D = window.D || {});