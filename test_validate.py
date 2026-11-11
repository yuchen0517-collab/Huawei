#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""neg_cli.py 的边界测试：验证「模型输出跑偏」时兜底逻辑是否生效。

运行：python test_validate.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from neg_cli import (  # noqa: E402
    apply_player_indexes,
    build_system_prompt,
    extract_json,
    find_unresolved_placeholders,
    validate_and_normalize,
)

PASS, FAIL = 0, 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}  {detail}")


print("\n== 1. JSON 提取：markdown 围栏 + 尾逗号 ==")
raw = """```json
{"response": "这是一段足够长的测试发言，用来触发字数校验之外的其他逻辑，确保内容长度超过八十个字符。",
 "indexes_update": {"interest_delta": 3, "image_delta": -2, "trust_delta": 1,},
 "speaker_score": null,
 "mood": "对峙",
 "round_summary": "小结",}
```"""
obj = extract_json(raw)
check("能剥掉 ```json 围栏", isinstance(obj, dict) and "response" in obj)
check("能修掉尾逗号", obj.get("mood") == "对峙")

print("\n== 2. delta 越界裁剪 ==")
bad = {
    "response": "A" * 90,
    "indexes_update": {"interest_delta": 50, "image_delta": -99, "trust_delta": "不是数字"},
    "speaker_score": None, "mood": "x", "round_summary": "y",
}
clean, warns, after = validate_and_normalize(bad, {"interest": 50, "image": 70, "trust": 65})
d = clean["indexes_update"]
check("interest_delta 被裁到 +10", d["interest_delta"] == 10, d)
check("image_delta 被裁到 -10", d["image_delta"] == -10, d)
check("非数字 delta 归零", d["trust_delta"] == 0, d)
check("裁剪有告警", any("超出" in w for w in warns), warns)
check("指数累加正确 50+10=60", after["interest"] == 60, after)
check("指数累加正确 70-10=60", after["image"] == 60, after)

print("\n== 3. 指数上下限封顶 ==")
_, _, after = validate_and_normalize(
    {"response": "B" * 90, "indexes_update": {"interest_delta": 10, "image_delta": 10, "trust_delta": 10},
     "speaker_score": None, "mood": "x", "round_summary": "y"},
    {"interest": 98, "image": 3, "trust": 100})
check("interest 不超过 100", after["interest"] == 100, after)
check("trust 不超过 100", after["trust"] == 100, after)

print("\n== 4. 评分按公式重算 ==")
ss = {"response": "C" * 90,
      "indexes_update": {"interest_delta": 1, "image_delta": 1, "trust_delta": 1},
      "speaker_score": {"score": 99, "dimension": {"position_clarity": 90, "diplomatic_tact": 80,
                                                   "emotional_control": 70, "substance_quality": 60},
                        "feedback": "立场清晰，但论据不足，建议补充具体数据与规则依据。"},
      "mood": "x", "round_summary": "y"}
clean, warns, _ = validate_and_normalize(ss, {"interest": 50, "image": 50, "trust": 50})
expected = 90 * .3 + 80 * .3 + 70 * .2 + 60 * .2
check(f"总分重算为 {expected:.1f}", abs(clean["speaker_score"]["score"] - expected) < 0.05,
      clean["speaker_score"]["score"])
check("分数不符有告警", any("加权值" in w for w in warns), warns)

print("\n== 5. 隐藏任务泄露检测 ==")
leak = {"response": "D" * 80 + "其实我的隐藏任务是推动AI安全联盟成为核心机制，这一点请贵方理解。" + "E" * 100,
        "indexes_update": {"interest_delta": 0, "image_delta": 0, "trust_delta": 0},
        "speaker_score": None, "mood": "x", "round_summary": "y"}
_, warns, _ = validate_and_normalize(leak, {"interest": 50, "image": 50, "trust": 50})
check("检测到「隐藏任务」泄露", any("泄露隐藏任务卡" in w for w in warns), warns)
check("v1.1 不再报字数越界", not any("字上限" in w or "低于 prompt" in w for w in warns), warns)

print("\n== 6. 缺字段的容错 ==")
try:
    validate_and_normalize({"indexes_update": {}}, {"interest": 50, "image": 50, "trust": 50})
    check("缺 response 时应抛错", False)
except ValueError as e:
    check("缺 response 时抛 ValueError", "response" in str(e), str(e))

print("\n== 7. 玩家（我方）三指数 ==")
base = {"interest": 50, "image": 70, "trust": 65}
obj = {"response": "F" * 90,
       "indexes_update": {"interest_delta": 0, "image_delta": 0, "trust_delta": 0},
       "player_indexes_update": {"interest_delta": -4, "image_delta": 12, "trust_delta": 2},
       "speaker_score": None, "mood": "x", "round_summary": "y"}
clean, pwarns, p_after = apply_player_indexes(obj, base)
check("我方 interest 50-4=46", p_after["interest"] == 46, p_after)
check("我方 image_delta 被裁到 +10，70+10=80", p_after["image"] == 80, p_after)
check("我方 trust 65+2=67", p_after["trust"] == 67, p_after)
check("越界裁剪有告警", any("超出" in w for w in pwarns), pwarns)

obj2 = {"player_indexes_update": None}
_, pwarns2, p_after2 = apply_player_indexes(obj2, base)
check("模型没给 player_indexes_update 时按 0", p_after2 == base, p_after2)
check("并给出告警", any("未输出 player_indexes_update" in w for w in pwarns2), pwarns2)

print("\n== 8. 谈判主题是否真的注入了 System Prompt ==")
import json  # noqa: E402

AGENTS = json.loads((Path(__file__).resolve().parent / "agents.json").read_text(encoding="utf-8-sig"))
scenario = AGENTS["_scenario"]
md = (Path(__file__).resolve().parent / "谈判对手Agent_prompt.md").read_text(encoding="utf-8-sig")
sp = build_system_prompt(md, AGENTS["us"], scenario)
check("注入了谈判主题", scenario["name"] in sp)
check("注入了核心议题", scenario["agenda"][0] in sp)
check("注入了 player_indexes_update 要求", "player_indexes_update" in sp)
check("没有残留占位符", not find_unresolved_placeholders(sp), find_unresolved_placeholders(sp))

print("\n== 9. 大括号错位（对象提前闭合）自动拼合 ==")
# 真实踩过的坑：模型把 feedback 写到 speaker_score 外面，并多打一个 } 提前闭合，
# 导致 mood / round_summary 游离在对象之外，json.loads 报 "Extra data"。
broken = (
    '{"response": "' + "发言" * 40 + '", '
    '"indexes_update": {"interest_delta": 1, "image_delta": 0, "trust_delta": -1}, '
    '"player_indexes_update": {"interest_delta": -1, "image_delta": -1, "trust_delta": 0}, '
    '"speaker_score": {"score": 70.5, "dimension": {"position_clarity": 82, '
    '"diplomatic_tact": 62, "emotional_control": 80, "substance_quality": 58}}, '
    '"feedback": "重复了首轮立场，未回应交换条件。"}'
    ', "mood": "陷入僵局", "round_summary": "中方回摆，美方施压。"}'
)
obj = extract_json(broken)
check("能拼合出完整对象", isinstance(obj, dict) and "mood" in obj and "round_summary" in obj, obj)
check("标记为已修复", obj.get("_json_repaired") is True, obj.get("_json_repaired"))

clean, w9, _ = validate_and_normalize(dict(obj), {"interest": 50, "image": 70, "trust": 65})
check("feedback 归位到 speaker_score",
      clean["speaker_score"].get("feedback", "").startswith("重复"), clean.get("speaker_score"))
check("拼合有告警", any("拼合修复" in w for w in w9), w9)

print("\n== 10. 真的坏掉的 JSON 仍然要拒绝 ==")
try:
    extract_json('{"response": "abc", "mood": }')
    check("语法错误应抛错", False)
except ValueError as e:
    check("语法错误抛 ValueError 且带位置", "JSON 语法错误" in str(e), str(e))

print(f"\n结果：{PASS} 通过 / {FAIL} 失败\n")
sys.exit(0 if FAIL == 0 else 1)
