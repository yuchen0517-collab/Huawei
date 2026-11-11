# -*- coding: utf-8 -*-
"""临时自测：确认 validate_action 的硬校验真的拦得住坏输出。跑完即删。"""
import copy
import neg_cli

BASE = {
    "action": {
        "action_type": "offer",
        "offer_patch": {"AI安全监管框架": {"option": "方案A", "note": "说明"}},
        "conditions": [],
        "expected_effect": "推进",
    },
    "public_message": "我方提出报价，请各方考虑。",
    "mood": "平和",
    "round_summary": "提出报价",
}

cases = []


def case(name, mutate, expect_ok):
    cases.append((name, mutate, expect_ok))


case("合法 offer（带 patch）", lambda o: None, True)
case("合法 statement（空 patch）",
     lambda o: o["action"].update(action_type="statement", offer_patch={}), True)
case("action_type 拼错", lambda o: o["action"].update(action_type="offerr"), False)
case("action_type 缺失", lambda o: o["action"].pop("action_type"), False)
case("action 不是对象", lambda o: o.update(action="offer"), False)
case("accept 带非空 patch",
     lambda o: o["action"].update(action_type="accept"), False)
case("accept patch 为 null",
     lambda o: o["action"].update(action_type="accept", offer_patch=None), False)
case("counter_offer 的 patch 不是对象",
     lambda o: o["action"].update(action_type="counter_offer", offer_patch="x"), False)
case("counter_offer 缺 patch",
     lambda o: (o["action"].update(action_type="counter_offer"), o["action"].pop("offer_patch")), False)
case("public_message 为空串", lambda o: o.update(public_message="   "), False)
case("public_message 缺失", lambda o: o.pop("public_message"), False)
case("public_message 不是字符串", lambda o: o.update(public_message=123), False)

failed = 0
for name, mutate, expect_ok in cases:
    obj = copy.deepcopy(BASE)
    mutate(obj)
    snapshot = copy.deepcopy(obj)
    try:
        neg_cli.validate_action(obj)
        ok = True
        err = ""
    except ValueError as e:
        ok = False
        err = str(e)
    except Exception as e:  # 非 ValueError 也视为不合格
        ok = False
        err = type(e).__name__ + ": " + str(e)

    passed = (ok == expect_ok)
    # 校验失败时不得写入/修改任何字段
    untouched = True if ok else (obj == snapshot)
    if not passed or not untouched:
        failed += 1
    if passed:
        detail = ("通过" if ok else "拦截：" + err)
        if not untouched:
            detail += "（但对象被改动了！）"
        print(f"[PASS] {name} → {detail}")
    else:
        print(f"[FAIL] {name} → 预期 {'通过' if expect_ok else '拦截'}，实际 {'通过' if ok else '拦截：' + err}")

print()
print("全部符合预期" if failed == 0 else f"{failed} 项不符合预期")
raise SystemExit(0 if failed == 0 else 1)