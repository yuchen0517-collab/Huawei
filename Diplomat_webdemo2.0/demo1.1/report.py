#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对局体检报告：读 logs/ 里最新的一次对局，直接给出结论。

用法：
    python report.py                 # 分析最新一局
    python report.py logs/run-xxx.json   # 分析指定某一局
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"

sys.path.insert(0, str(BASE_DIR))
from neg_cli import INDEX_KEYS, INDEX_LABELS, bar, pad  # noqa: E402

# v1.1：不设字数上限，篇幅只作参考信息
# 评分四维满分 100，这里给一条“像样”的参考线
GOOD_SCORE = 70


def pick_log(argv: list[str]) -> Path:
    if len(argv) > 1:
        p = Path(argv[1])
        if not p.exists():
            sys.exit(f"[错误] 找不到文件：{p}")
        return p
    if not LOG_DIR.exists():
        sys.exit("[错误] 还没有任何对局记录。先跑一次：.\\run.bat --rounds 5")
    logs = sorted(LOG_DIR.glob("run-*.json"))
    if not logs:
        sys.exit("[错误] logs/ 里没有 run-*.json。先跑一次：.\\run.bat --rounds 5")
    return logs[-1]


def classify(warning: str) -> str:
    """把告警归类，决定它是硬伤还是提醒。"""
    if "泄露隐藏任务卡" in warning:
        return "leak"
    if "兜底" in warning:
        return "fallback"
    if "无法解析" in warning:
        return "json"
    if "拼合修复" in warning:
        return "repair"
    if "feedback 被写到" in warning:
        return "repair"
    if "超出" in warning and "裁剪" in warning:
        return "clamp"
    if "越界" in warning and "截断" in warning:
        return "clamp"
    if "字" in warning and ("低于" in warning or "超出" in warning):
        return "length"
    if "player_indexes_update" in warning:
        return "missing_player"
    if "feedback" in warning:
        return "feedback"
    if "加权值" in warning:
        return "score_math"
    return "other"


CATEGORY_LABEL = {
    "leak": "隐藏任务泄露",
    "fallback": "JSON 兜底降级",
    "json": "JSON 解析失败",
    "repair": "JSON 括号错位（已自动修复）",
    "clamp": "数值越界（已被代码裁剪）",
    "length": "发言字数不合规",
    "missing_player": "缺 player_indexes_update",
    "feedback": "点评字数不合规",
    "score_math": "评分总分不自洽",
    "other": "其他",
}


def main() -> int:
    path = pick_log(sys.argv)
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    trace = data.get("trace") or []
    if not trace:
        sys.exit("[错误] 这份记录里没有对局内容。")

    label = data.get("label", "对手")
    player = data.get("player", "我方")
    scenario = (data.get("scenario") or {}).get("name", "")
    model = data.get("model", "?")

    # ---------- 统计 ----------
    warnings: list[str] = []
    for t in trace:
        warnings.extend(t.get("warnings") or [])
    cats = Counter(classify(w) for w in warnings)

    lengths = [len(t.get("agent_response") or "") for t in trace]
    scores = [t["speaker_score"]["score"] for t in trace
              if isinstance(t.get("speaker_score"), dict)]
    dims = {k: [] for k in ("position_clarity", "diplomatic_tact",
                            "emotional_control", "substance_quality")}
    for t in trace:
        ss = t.get("speaker_score")
        if isinstance(ss, dict) and isinstance(ss.get("dimension"), dict):
            for k in dims:
                v = ss["dimension"].get(k)
                if isinstance(v, (int, float)):
                    dims[k].append(float(v))

    # ---------- 打印 ----------
    print()
    print("=" * 74)
    print("  对局体检报告")
    print("=" * 74)
    print(f"  记录文件    {path.name}")
    print(f"  谈判主题    {scenario}")
    print(f"  双方        {player}（你）  vs  {label}（对手）")
    print(f"  模型        {model}")
    print(f"  轮次        {len(trace)}")
    print()

    # 1. 格式稳定性
    bad_json = cats.get("fallback", 0) + cats.get("json", 0)
    ok_rounds = len(trace) - cats.get("fallback", 0)
    print("  ── 1. 输出格式稳定性 ──")
    print(f"     可解析轮次    {ok_rounds}/{len(trace)}")
    if bad_json == 0:
        print("     [OK] 每轮都拿到了合法 JSON")
    else:
        print(f"     [!]  {bad_json} 轮没能拿到合法 JSON（已走兜底，数据不可信）")
    print()

    # 2. 发言篇幅（v1.1 不设上限，只看是否空洞）
    print("  ── 2. 发言篇幅（v1.1 不设字数限制）──")
    if lengths:
        print(f"     最短 {min(lengths)} / 平均 {sum(lengths)//len(lengths)} / 最长 {max(lengths)}")
        empty = sum(1 for n in lengths if n < 10)
        if empty:
            print(f"     [!]  {empty} 轮几乎没有内容（不足 10 字）")
        else:
            print("     [OK] 每轮都有实质内容")
    print()

    # 3. 三指数
    print("  ── 3. 三指数轨迹 ──")
    first_p = trace[0].get("player_indexes_after") or {}
    last_p = trace[-1].get("player_indexes_after") or {}
    first_a = trace[0].get("indexes_after") or {}
    last_a = trace[-1].get("indexes_after") or {}
    if last_p and last_a:
        for key in INDEX_KEYS:
            print(f"     {pad(INDEX_LABELS[key], 12)}"
                  f"{player} {first_p.get(key, '-'):>3} → {last_p.get(key, '-'):>3}   "
                  f"{label} {first_a.get(key, '-'):>3} → {last_a.get(key, '-'):>3}")
        moved = sum(1 for k in INDEX_KEYS
                    if first_p.get(k) != last_p.get(k) or first_a.get(k) != last_a.get(k))
        if moved == 0:
            print("     [!]  三指数完全没动 —— 模型可能在敷衍，或者没在认真评估")
        else:
            print(f"     [OK] {moved}/3 项指数发生了变化")
    else:
        print("     ·   这局记录缺少指数数据（旧版本日志）")
    print()

    # 4. 评分
    print("  ── 4. 对我方发言的评分 ──")
    if scores:
        print(f"     总分平均 {sum(scores)/len(scores):.1f}   最低 {min(scores):.1f}   最高 {max(scores):.1f}")
        for k, v in dims.items():
            if v:
                print(f"     {pad(CAT_LABEL_DIM.get(k, k), 12)}{sum(v)/len(v):5.1f}")
        avg = sum(scores) / len(scores)
        if avg >= GOOD_SCORE:
            print(f"     [OK] 平均分 {avg:.1f} 高于参考线 {GOOD_SCORE}")
        else:
            print(f"     ·   平均分 {avg:.1f} 低于参考线 {GOOD_SCORE} —— 可能是模型评分偏严，也可能是你的打法有问题")
    else:
        print("     ·   没有评分数据")
    print()

    # 5. 告警
    print("  ── 5. 校验告警 ──")
    if not warnings:
        print("     [OK] 0 条告警")
    else:
        print(f"     共 {len(warnings)} 条：")
        for cat, n in cats.most_common():
            print(f"       {pad(CAT_LABEL_DIM.get(cat, CATEGORY_LABEL.get(cat, cat)), 26)}{n} 条")
        print()
        print("     明细（前 12 条）：")
        for w in warnings[:12]:
            print(f"       · {w}")
        if len(warnings) > 12:
            print(f"       ... 还有 {len(warnings) - 12} 条")
    print()

    # ---------- 结论 ----------
    print("=" * 74)
    print("  结论")
    print("=" * 74)

    blockers = []
    if cats.get("leak"):
        blockers.append(f"隐藏任务泄露 {cats['leak']} 次 —— Demo 会被评委一眼看穿，必须改 Prompt 的保密段")
    if cats.get("fallback") or cats.get("json"):
        blockers.append(f"{cats.get('fallback',0) + cats.get('json',0)} 轮 JSON 失败 —— 格式约束不可靠，先解决再加 UI")

    hints = []
    if cats.get("repair"):
        hints.append(f"JSON 括号错位 {cats['repair']} 次（代码已拼合修复，数据可用；"
                     f"频繁出现说明输出格式对模型太复杂，可考虑拆分字段）")
    if cats.get("clamp"):
        hints.append(f"数值越界 {cats['clamp']} 次（代码已裁剪，但说明模型在瞎编 delta，可在 Prompt 里加取值表）")
    if cats.get("missing_player"):
        hints.append(f"缺 player_indexes_update {cats['missing_player']} 次 —— 我方指数会停住")
    if cats.get("feedback"):
        hints.append(f"点评字数不合规 {cats.get('feedback')} 次")
    if len(trace) < 5:
        hints.append(f"只跑了 {len(trace)} 轮，样本太少，建议至少 5 轮再下结论")

    if blockers:
        print("  ✗ 还不能进 UI 阶段。先解决：")
        for b in blockers:
            print(f"     · {b}")
    else:
        print("  ✓ 通过。Prompt 这一关可以过了，可以进 UI 阶段。")
    if hints:
        print()
        print("  提醒（不阻塞，但建议处理）：")
        for h in hints:
            print(f"     · {h}")
    print()
    print(f"  生成时间 {datetime.now():%Y-%m-%d %H:%M:%S}")
    print()
    return 0 if not blockers else 1


CAT_LABEL_DIM = {
    "position_clarity": "立场清晰度",
    "diplomatic_tact": "外交策略",
    "emotional_control": "情绪控制",
    "substance_quality": "实质内容",
}

if __name__ == "__main__":
    sys.exit(main())
