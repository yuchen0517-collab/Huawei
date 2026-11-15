(function (D) {
  "use strict";

  var $ = D.dom.$;

  function render(s) {
    $("app").innerHTML =
      D.components.topbar(s) +
      D.components.topicbar(s) +
      '<main id="body">' +
        D.components.leftColumn(s) +
        D.components.stage(s) +
        D.components.rightColumn(s) +
      "</main>" +
      D.components.hand(s);

    $("drawer").innerHTML = D.components.drawer(s);
    $("finale").innerHTML = D.components.finale(s);
    $("demoPanel").innerHTML = D.overlays.demoPanel(s);

    D.dom.toggle("mask", "on", s.ui.drawerOpen);
    D.dom.toggle("drawer", "on", s.ui.drawerOpen);
    D.dom.toggle("finale", "on", s.ui.finaleOpen);
    D.dom.toggle("demoPanel", "on", s.ui.demoOpen);
  }

  function bind() {
    document.addEventListener("click", function (e) {
      var t = e.target.closest("[data-act]");
      if (!t) return;
      var act = t.getAttribute("data-act");
      switch (act) {
        case "tab": D.store.setView(t.getAttribute("data-view")); break;
        case "submit": D.store.commit(); break;
        case "endRoundSummary": D.store.endRoundSummary(); break;
        case "merge": D.store.merge(); break;
        case "openDrawer": D.store.openDrawer(); break;
        case "closeDrawer": D.store.closeDrawer(); break;
        case "accept": if (!t.disabled) D.store.accept(); break;
        case "reject": D.store.reject(); break;
        case "finale": D.store.openFinale(); break;
        case "closeFinale": D.store.closeFinale(); break;
        case "newGame": D.store.newGame(); break;
        case "exportStory": D.overlays.toast(null, "复盘记录已导出到会话归档（演示态）"); break;
        case "nextTopic": D.store.nextTopic(); break;
        case "randomCheck": D.store.randomCheck(); break;
        case "demo": D.store.toggleDemo(); break;
        case "demoErr": D.store.setDemoError(t.getAttribute("data-code")); break;
        case "demoReset": D.store.resetDemo(); break;
        case "card": D.store.selectCard(t.getAttribute("data-id")); break;
      }
    });

    document.addEventListener("change", function (e) {
      var sel = e.target.closest("[data-clause]");
      if (!sel) return;
      D.store.setDraft(sel.getAttribute("data-clause"), sel.value);
    });

    document.addEventListener("click", function (e) {
      var p = $("demoPanel");
      if (p && p.classList.contains("on") && !p.contains(e.target) && !e.target.closest("#demoBtn")) {
        D.store.closeDemo();
      }
    });
  }

  function boot() {
    window.DIPLOMAT = {
      snapshot: function () { return D.store.snapshot(); },
      print: function () {
        var snap = D.store.snapshot();
        console.log("%c[Diplomat] 当前完整状态快照", "color:#c9a227;font-weight:bold");
        console.log(JSON.stringify(snap, null, 2));
        return snap;
      },
      measure: function () {
        var ids = ["stage", "rehearsal", "hand", "finaleBtn", "bdScroll", "mVer", "bdVer", "drVer"];
        var scroller = document.scrollingElement;
        var vp = {
          w: window.innerWidth,
          h: window.innerHeight,
          scrollW: scroller.scrollWidth,
          clientW: scroller.clientWidth
        };
        var items = {};
        ids.forEach(function (id) {
          var el = document.getElementById(id);
          if (!el) { items[id] = null; return; }
          var r = el.getBoundingClientRect();
          items[id] = {
            top: Math.round(r.top),
            bottom: Math.round(r.bottom),
            left: Math.round(r.left),
            right: Math.round(r.right),
            inViewport: r.top >= 0 && r.bottom <= vp.h && r.left >= 0 && r.right <= vp.w
          };
        });
        var result = { viewport: vp, items: items, noHorizontalScroll: vp.scrollW <= vp.clientW };
        console.table(items);
        console.log("[Diplomat] noHorizontalScroll:", result.noHorizontalScroll);
        console.log(JSON.stringify(result, null, 2));
        return result;
      },
      store: D.store,
      adapters: D.adapters,
      config: window.DIPLOMAT_CONFIG || { adapter: "mock" }
    };

    D.store.init(D.adapters.current.createState());
    D.store.subscribe(render);
    render(D.store.get());
    bind();

    setTimeout(function () {
      D.store.get().phase = "ready";
      D.store.notify();
      window.DIPLOMAT.print();
    }, 1100);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})(window.D = window.D || {});