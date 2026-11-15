(function (D) {
  "use strict";

  var CONFIG = window.DIPLOMAT_CONFIG || {};

  var MESSAGES = {
    INVALID_ACTION: "该行动不满足当前条款约束，未生效。",
    SESSION_BUSY: "会话正被另一笔行动占用，请求排队中。",
    MODEL_UNAVAILABLE: "解说与情报模型暂不可用，报价板不受影响。",
    ROUND_LOCKED: "本轮已锁定，无法再提交行动。",
    VERSION_CONFLICT: "客户端版本落后于服务端，需合并后重提。",
    TIMEOUT: "上游未在时限内返回，草稿已保留。"
  };

  function createState() {
    return {
      version: 12,
      round: 3,
      maxRound: 6,
      ap: 3,
      apMax: 5,
      phase: "loading",
      serviceDown: null,
      sessionLost: false,
      slowSeconds: 0,
      slowHint: false,
      currentState: null,
      modelDown: false,
      roundLocked: false,
      conflict: false,
      serverVersion: null,
      inlineError: null,
      inflight: null,
      retryKey: null,
      demoError: null,
      selectedCard: null,
      draft: {},
      clauses: [
        { id: "c1", no: "01", name: "监测站点数量", mine: "6 站点", opts: ["6 站点", "5 站点", "4 站点"], theirs: "4 站点", conf: 72, status: "agreed" },
        { id: "c2", no: "02", name: "数据共享频率", mine: "每月", opts: ["每月", "每双月", "每季"], theirs: "每季", conf: 64, status: "agreed" },
        { id: "c3", no: "03", name: "联合实验室选址", mine: "A 城", opts: ["A 城", "A/B 双址", "B 城"], theirs: "B 城", conf: 58, status: "open" },
        { id: "c4", no: "04", name: "争议仲裁归属", mine: "中立国仲裁", opts: ["中立国仲裁", "区域组织仲裁", "暂不写入"], theirs: "未表态", conf: 41, status: "pending" },
        { id: "c5", no: "05", name: "费用分摊比例", mine: "40 / 60", opts: ["40 / 60", "45 / 55", "50 / 50"], theirs: "未表态", conf: 33, status: "pending" }
      ],
      cards: [
        { id: "k1", title: "技术援助换取数据权", desc: "以折算表换共享频率", cost: 2 },
        { id: "k2", title: "引入第三方观察员", desc: "提升条款可核验性", cost: 1 },
        { id: "k3", title: "延迟表态", desc: "等待对方先出价", cost: 0 }
      ],
      actions: {},
      submittedKeys: {},
      openIssues: ["争议仲裁归属", "费用分摊比例"],
      speakerScore: {
        total: 75,
        position_clarity: 78,
        diplomatic_tact: 72,
        emotional_control: 85,
        substance_quality: 66,
        feedback: "情绪控制与立场表达稳定，但实质论据偏弱，费用分摊缺少可核验数据支撑。"
      },
      ended: false,
      audit: null,
      randomWarnings: [],
      topic: { name: "跨境水资源联合监测机制", index: 3, total: 6, randomCheck: "pass" },
      us: { leverage: 72, timePressure: 28, timePressureLabel: "低", gains: 2 },
      them: { concessionIntent: 58, decisionChain: 3, confidence: 64, lastMove: "R2 单向让步" },
      channels: [
        { id: "ch1", name: "技术工作组直联", status: "ready" },
        { id: "ch2", name: "第三方观察员", status: "ready" },
        { id: "ch3", name: "高层热线", status: "cooldown" }
      ],
      hiddenTasks: [
        { id: "t1", text: "在第 2 轮前引入至少 1 条可核验事实依据", done: true },
        { id: "t2", text: "在协议达成前，保留至少 1 条未决条款作为回撤空间", done: false }
      ],
      batnaComparison: {
        batna: "单边监测框架 · 可接受度 中 · 成本可控",
        achieved: null,
        net_gain: null,
        better_than_batna: null
      },
      batnaThem: null,
      narration: {
        text: "对方在上一轮将监测站点数由 5 降至 4，属于试探性让步；其真实约束在于国内预算审批窗口只剩两周，因此对「费用分摊」的敏感度高于「站点数量」。",
        source: "模型生成 · 仅供参考，不作为事实依据"
      },
      summaryPoints: [
        "已决 2 条，未决 2 条，1 条待确认。",
        "对方对我方「中立国仲裁」提案未表态，沉默超过 1 轮。",
        "本轮剩余行动点 3，距回合锁定 2 轮。"
      ],
      facts: [
        { t: "2026-11-04 · 澜江水文年鉴", c: "A 城站点年径流量高于 B 城 18%。", s: "来源：公开年鉴 · 可核验" },
        { t: "2026-11-06 · 北岸联合体预算公开稿", c: "北岸年度监测预算削减 12%。", s: "来源：公开稿 · 可核验" },
        { t: "2026-11-08 · 会场记录", c: "对方代表两次提及「审批窗口」。", s: "来源：本方纪要 · 单方记录" }
      ],
      timeline: [
        { r: "R1", x: "双方确认<em>议题边界</em>，排除第三方仲裁前置条件。" },
        { r: "R2", x: "对方就<em>站点数量</em>由 5 降至 4，我方维持 6。" },
        { r: "R2", x: "我方提出<em>中立国仲裁</em>，对方未回应。" },
        { r: "R3", x: "对方申请<em>延长本轮</em>，被议题条随机检查拦下后撤回。" }
      ],
      intelCards: [
        { h: "对方决策链长度", tag: "估计值", b: "线索显示对方表态需经 3 层审批，现场代表无最终签字权。", conf: 51 },
        { h: "预算审批窗口", tag: "估计值", b: "对方内部预算窗口预计两周内关闭，时间压力高于我方。", conf: 64 },
        { h: "让步意愿指数", tag: "估计值", b: "近 2 轮出现 1 次单向让步，趋势偏软，但幅度收窄。", conf: 58 },
        { h: "对方 BATNA", tag: "未知", b: "未获得任何可核验线索。不作为推演输入，仅记录为「未知」。", conf: 0 }
      ],
      dialogue: [
        { who: "them", name: "对方 · 北岸联合体", text: "我们可以接受把监测站点数压到 4，但费用分摊必须按 60/40，我方承担 60 已经是上限。", est: false },
        { who: "us", name: "我方 · 澜江代表团", text: "4 个站点可以谈，但必须包含 A 城。费用分摊我们提 40/60，差额用技术援助抵。", est: false },
        { who: "them", name: "对方 · 北岸联合体", text: "技术援助的折算口径需要写进附件，否则无法过审。仲裁归属我们暂不表态。", est: true }
      ],
      finale: {
        turningPoints: [
          { k: "R2", t: "对方站点数 5→4，首次单向让步。" },
          { k: "R3", t: "我方以技术援助换费用分摊口径，避免议题搁置。" },
          { k: "R3", t: "随机议题检查拦下对方延长本轮申请。" }
        ],
        pendingHandling: [
          { k: "04", t: "争议仲裁归属：保留为未决，写入附件二。" },
          { k: "05", t: "费用分摊比例：保留为未决，绑定技术援助折算表。" }
        ],
        reviewPoints: [
          { k: "01", t: "对方时间压力被低估，R2 可更早施压。" },
          { k: "02", t: "隐藏任务 2 未完成：回撤空间保留过晚。" }
        ]
      },
      rehearsal: {
        react: "未选择策略卡，按当前报价推演",
        apCost: "1 / 剩余 3",
        riskLevel: "低 · 常规推进",
        riskClass: "ok",
        basis: "估计值 · 可信度 64%"
      },
      ui: { view: "board", drawerOpen: false, finaleOpen: false, demoOpen: false }
    };
  }

  function rehearsal(state) {
    var k = state.cards.filter(function (x) { return x.id === state.selectedCard; })[0];
    if (!k) {
      return {
        react: "未选择策略卡，按当前报价推演",
        apCost: "1 / 剩余 " + state.ap,
        riskLevel: "低 · 常规推进",
        riskClass: "ok",
        basis: "估计值 · 可信度 64%"
      };
    }
    var map = {
      k1: { react: "倾向接受，但要求折算表附件", apCost: "2 / 剩余 " + state.ap, riskLevel: "中 · 审批链卡点", riskClass: "warn", basis: "估计值 · 可信度 58%" },
      k2: { react: "可能引入程序性异议", apCost: "1 / 剩余 " + state.ap, riskLevel: "低 · 可核验性提升", riskClass: "ok", basis: "估计值 · 可信度 64%" },
      k3: { react: "对方大概率先出价", apCost: "0 / 剩余 " + state.ap, riskLevel: "中 · 时间成本上升", riskClass: "warn", basis: "历史模式 · 可信度 47%" }
    };
    return map[k.id] || map.k3;
  }

  function fail(code, extra) {
    return Promise.resolve(Object.assign({ ok: false, error: { error: code, detail: MESSAGES[code] } }, extra || {}));
  }

  function submit(state, ctx) {
    return new Promise(function (resolve) {
      setTimeout(function () {
        if (ctx.signal && ctx.signal.aborted) return resolve({ ok: false, aborted: true });
        var injected = ctx.demoError;
        if (injected === "SESSION_BUSY") return resolve({ ok: false, retryAfter: 700, error: { error: "SESSION_BUSY", detail: MESSAGES.SESSION_BUSY } });
        if (injected === "TIMEOUT") return fail("TIMEOUT").then(resolve);
        if (injected === "VERSION_CONFLICT") return resolve({ ok: false, patch: { serverVersion: state.version + 1 }, error: { error: "VERSION_CONFLICT", detail: MESSAGES.VERSION_CONFLICT } });
        if (injected === "INVALID_ACTION") return fail("INVALID_ACTION").then(resolve);
        if (injected === "MODEL_UNAVAILABLE") return fail("MODEL_UNAVAILABLE").then(resolve);
        if (injected === "ROUND_LOCKED") return fail("ROUND_LOCKED").then(resolve);

        var nextRound = state.round < state.maxRound ? state.round + 1 : state.round;
        var ended = state.round >= state.maxRound;
        var actions = Object.assign({}, state.actions);
        actions[ctx.key] = { key: ctx.key, round: state.round, at: new Date().toISOString(), ap: 2 };
        var keys = Object.assign({}, state.submittedKeys);
        keys[ctx.key] = true;

        resolve({
          ok: true,
          patch: {
            version: state.version + 1,
            round: nextRound,
            ap: Math.max(0, state.ap - 2),
            draft: {},
            selectedCard: null,
            demoError: null,
            retryKey: null,
            actions: actions,
            submittedKeys: keys,
            ended: ended
          }
        });
      }, CONFIG.mockDelayMs || 900);
    });
  }

  function merge(state) {
    return Promise.resolve({
      ok: true,
      patch: { version: state.serverVersion || state.version, serverVersion: null, conflict: false }
    });
  }

  function accept(state) {
    return Promise.resolve({
      ok: true,
      audit: { ok: true, issues: [], summary: { blocking: 0, warning: 0 } }
    });
  }

  function summary(state) {
    return new Promise(function (resolve) {
      setTimeout(function () {
        var timeline = state.timeline.concat([
          { r: "R" + state.round, x: "本轮总结已记录（未推进轮次，K3=B）。" }
        ]);
        resolve({ ok: true, timeline: timeline });
      }, 400);
    });
  }

  function nextTopic() {
    var names = ["跨境数据流动规则", "联合科研基金分配", "边境外溢补偿机制"];
    var n = names[Math.floor(Math.random() * names.length)];
    var idx = Math.floor(Math.random() * 6) + 1;
    return Promise.resolve({ ok: true, topic: { name: n, index: idx } });
  }

  // P13：三态由编排层派生；conflict 不阻塞提交
  function randomCheck(state) {
    var isPass = state.topic.randomCheck === "pass";
    if (isPass) {
      return Promise.resolve({
        ok: true,
        status: "conflict",
        warnings: [{ code: "CLAUSE_CONFLICT", field: "c4", message: "条款 04 与议题边界冲突" }],
        message: "随机检查发现条款 04 与议题边界冲突，已标记待确认（不阻塞提交）"
      });
    }
    return Promise.resolve({
      ok: true,
      status: "pass",
      warnings: [],
      message: "随机议题检查：已通过"
    });
  }

  function reset(state, opts) {
    var s = createState();
    s.phase = "ready";
    if (opts && opts.newGame) {
      s.version = (state && state.version ? state.version : 12) + 1;
      s.round = 1;
      s.ap = s.apMax;
      s.speakerScore = null;
    }
    return Promise.resolve(s);
  }

  D.adapters = D.adapters || {};
  D.adapters.mock = {
    id: "mock",
    messages: MESSAGES,
    createState: createState,
    rehearsal: rehearsal,
    submit: submit,
    merge: merge,
    accept: accept,
    summary: summary,
    nextTopic: nextTopic,
    randomCheck: randomCheck,
    reset: reset
  };
})(window.D = window.D || {});