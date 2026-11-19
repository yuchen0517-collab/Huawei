#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""事实卡 xlsx -> 知识库.json

用法（在 Agent 目录下）：
    python knowledge\\导入事实卡.py
    python knowledge\\导入事实卡.py 某个新文件.xlsx

每次组员更新了 xlsx，重跑一次即可；服务不用重启（Prompt 每次请求重新构建）。
"""

import json
import sys
from pathlib import Path

from openpyxl import load_workbook

BASE = Path(__file__).resolve().parent
DEFAULT_SRC = BASE / "算力与芯片出口管制_事实卡_v2.xlsx"
OUT = BASE / "知识库.json"

TYPE_KEY = {"立场": "positions", "行动": "actions", "数字": "numbers",
            "引用": "quotes", "智库": "thinktank"}


def main() -> int:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SRC
    if not src.is_absolute():
        src = Path.cwd() / src
    if not src.exists():
        print(f"[错误] 找不到文件：{src}")
        return 1

    wb = load_workbook(src, data_only=True)
    out = {
        "_说明": ("由组员事实卡自动生成。us/cn 下的五类卡片会被拼进 agent 的 Prompt，"
                 "同时用于数字核查。修改请改 xlsx 后重新运行 knowledge\\导入事实卡.py，"
                 "不要直接编辑本文件。"),
        "_生成来源": src.name,
    }

    total_all = 0
    for sheet, key in (("中国_事实卡", "cn"), ("美国_事实卡", "us")):
        if sheet not in wb.sheetnames:
            print(f"[警告] 缺少工作表 {sheet}，跳过")
            continue
        ws = wb[sheet]
        head = [c.value for c in ws[1]]
        bucket = {v: [] for v in TYPE_KEY.values()}
        for r in ws.iter_rows(min_row=2, values_only=True):
            if not r or not r[0]:
                continue
            rec = {h: (r[i] if i < len(r) else "") or "" for i, h in enumerate(head)}
            slot = TYPE_KEY.get(str(rec.get("类型", "")).strip())
            if not slot:
                continue
            bucket[slot].append({
                "id": str(rec.get("编号", "")).strip(),
                "date": str(rec.get("时间", "")).strip(),
                "text": str(rec.get("内容（一句话，≤60字）", "")).strip(),
                "value": str(rec.get("数值", "")).strip(),
                "source": str(rec.get("来源名称", "")).strip(),
                "link": str(rec.get("来源链接", "")).strip(),
                "conf": str(rec.get("可信度", "")).strip(),
                "note": str(rec.get("备注", "")).strip(),
            })
        out[key] = bucket
        n = sum(len(v) for v in bucket.values())
        total_all += n
        print(f"[{sheet}] {n} 条 -> " +
              str({k: len(v) for k, v in bucket.items() if v}))

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n写入 {OUT}  {OUT.stat().st_size} 字节  共 {total_all} 条")
    print("提示：智库类不会注入 Prompt，只保留在知识库里备查。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
