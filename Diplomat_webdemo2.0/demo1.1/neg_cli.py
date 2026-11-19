#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
谈判对手 Agent · 命令行验证工具（MVP 第 1 步）

用途：在套 UI 之前，先验证「谈判对手Agent_prompt.md」是否真的能稳定产出
可解析的 JSON、三指数 delta 是否合理、评分是否自洽。

用法：
    python neg_cli.py --offline              # 不需要 API Key，跑一遍完整链路（自检）
    python neg_cli.py                        # 真实调用 DeepSeek，连打 3 轮
    python neg_cli.py --rounds 5             # 打 5 轮
    python neg_cli.py --agent eu             # 换成欧盟 Agent
    python neg_cli.py --interactive          # 你手动输入中方发言

环境变量：
    DEEPSEEK_API_KEY    必填（--offline 时不需要）
    DEEPSEEK_BASE_URL   默认 https://api.deepseek.com/chat/completions
    DEEPSEEK_MODEL      默认 deepseek-chat
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# ---------- 控制台编码（Windows 中文不乱码） ----------
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent
PROMPT_FILE = BASE_DIR / "谈判对手Agent_prompt.md"   # v1.1：prompt 与代码同目录，整个文件夹可直接拷走
AGENTS_FILE = BASE_DIR / "agents.json"
KB_FILE = BASE_DIR.parent / "knowledge" / "知识库.json"
TOPICS_DIR = BASE_DIR.parent / "knowledge" / "topics"

# 选择页的 topicId -> 知识库文件（没配的议题就没有事实卡）
TOPIC_ALIAS = {
    "unclos": "unclos",
    "compute": "compute-chip", "chipcase": "compute-chip",
    "semiconductor": "compute-chip", "compute-chip": "compute-chip",
    "dst": "dst", "digital-tax": "dst", "digital-services-tax": "dst",
}
LOG_DIR = BASE_DIR / "logs"

API_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/chat/completions")
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

# 评分权重，来自 prompt 文件 §3.2
SCORE_WEIGHTS = {
    "position_clarity": 0.30,
    "diplomatic_tact": 0.30,
    "emotional_control": 0.20,
    "substance_quality": 0.20,
}

INDEX_KEYS = ["interest", "image", "trust"]
DELTA_KEYS = ["interest_delta", "image_delta", "trust_delta"]
INDEX_LABELS = {
    "interest": "主体利益值",
    "image": "国际形象值",
    "trust": "盟友信任度",
}
DELTA_LIMIT = 10      # prompt §一：-10 到 +10
SHORT_SPEECH = 10     # v1.1 取消 80-200 字限制；只拦「几乎没有内容」的异常返回

# 内置的“中方发言”，让脚本可以无人值守连打 3 轮
CHINA_LINES = [
    "中方认为，全球 AI 治理应遵循共商共建共享原则。任何以「安全」为名的机制，都不应成为少数"
    "国家垄断技术、审查他国发展的工具。出口管制与「可核查」安排必须置于联合国框架之下，由所有"
    "国家平等参与监督，而非由任何小圈子单方面裁量。",

    "中方已注意到贵方将「可核查」与「审查」作区分。但机制的可信度不取决于措辞，而取决于授权来源。"
    "中方愿在透明度上展现建设性，前提是：第一，监督机构由联合国大会授权而非联盟内部产生；第二，"
    "核查标准对所有国家对称适用，包括最大技术持有国自身；第三，技术援助与算力配额写入约束性条款。",

    "我方愿在监督机制授权来源上作技术性调整，接受由联合国秘书长任命的独立技术专家组承担评估职能。"
    "作为对等，我方要求：贵方须承诺不将 AI 出口管制清单与本次框架挂钩；全球公共算力中，发展中国家"
    "的配额不低于 30%，并设立能力建设基金。这是我方可以讨论的范围。",
]


# ============================ 读取与注入 ============================

def load_prompt_markdown() -> str:
    if not PROMPT_FILE.exists():
        sys.exit(f"[错误] 找不到 prompt 文件：{PROMPT_FILE}")
    # utf-8-sig：记事本另存为「UTF-8 带 BOM」时也能正常读
    return PROMPT_FILE.read_text(encoding="utf-8-sig")


REQUIRED_AGENT_FIELDS = [
    "agent_identity", "agent_entity", "agent_position", "negotiation_style",
    "public_position", "core_interests_ranked", "red_lines", "batna",
    "hidden_task_card", "initial_interest", "initial_image", "initial_trust",
]


def load_agents() -> dict:
    """读 agents.json，并把「记事本改坏了」这类错误翻译成人话。"""
    if not AGENTS_FILE.exists():
        sys.exit(f"[错误] 找不到配置文件：{AGENTS_FILE}")

    try:
        text = AGENTS_FILE.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        sys.exit("[错误] agents.json 的编码不是 UTF-8（可能是记事本存成了 ANSI/GBK）。\n"
                 "       用记事本打开 → 另存为 → 编码选「UTF-8」→ 覆盖保存。")

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        lines = text.splitlines()
        shown = lines[e.lineno - 1] if 1 <= e.lineno <= len(lines) else ""
        print(f"\n[错误] agents.json 第 {e.lineno} 行第 {e.colno} 列有语法问题：{e.msg}\n")
        print(f"  {e.lineno:>4} | {shown}")
        print(f"       | {' ' * (e.colno - 1)}^")
        print("\n  常见的三个原因：")
        print("    1. 上一行结尾少写了英文逗号 ,")
        print("    2. 用了中文标点：“ ” ， ：  —— 必须是英文的 \" \" , :")
        print("    3. 最后一个字段后面多了逗号（JSON 不允许）")
        print("\n  改完可以用  .\\run.bat --check  验证一下。")
        sys.exit(2)


def check_config(md: str, agents: dict) -> int:
    """只检查配置，不跑对局。改完 agents.json 用它验一下。"""
    scenario = agents.get("_scenario", {})
    print()
    print("=" * 72)
    print("  检查 agents.json")
    print("=" * 72)
    sc_name = scenario.get("name", "（未配置 _scenario，谈判主题将为空）")
    print(f"  谈判主题：{sc_name}")
    print()
    ok = True
    for key, cfg in agents.items():
        if key.startswith("_"):
            continue
        problems = []
        for f in REQUIRED_AGENT_FIELDS:
            if f not in cfg:
                problems.append(f"缺少字段 {f}")
        for f in ("initial_interest", "initial_image", "initial_trust"):
            v = cfg.get(f)
            if not isinstance(v, int) or not (0 <= v <= 100):
                problems.append(f"{f} 必须是 0-100 的整数（当前 {v!r}）")
        try:
            sp = build_system_prompt(md, cfg, scenario,
                                     side=key if key in ("us", "cn") else None)
            left = find_unresolved_placeholders(sp)
            if left:
                problems.append(f"占位符没填：{', '.join(left)}")
        except SystemExit:
            raise
        label = cfg.get("label", key)
        if problems:
            ok = False
            print(f"  [FAIL] {key:<4} {label}")
            for p in problems:
                print(f"         - {p}")
        else:
            print(f"  [OK]   {key:<4} {label:<4}  System {len(sp)} 字，"
                  f"初始指数 {cfg['initial_interest']}/"
                  f"{cfg['initial_image']}/{cfg['initial_trust']}")
    print()
    print("  全部通过，可以跑对局了。" if ok else "  有配置问题，见上。")
    print()
    return 0 if ok else 1


def extract_system_prompt(md: str) -> str:
    """取出 §一 里那段被 ``` 包起来的 System Prompt。"""
    blocks = md.split("```")
    for i in range(1, len(blocks), 2):
        if "## 你的身份" in blocks[i]:
            return blocks[i].strip("\n")
    sys.exit("[错误] 没在 md 文件里找到 System Prompt 代码块（应包含「## 你的身份」）。")


def scenario_vars(scenario: dict, cfg: dict) -> dict:
    """把 _scenario 里的主题信息转成 prompt 中的占位符变量（v1.1 起）。

    v1.0 是代码在末尾追加一段「本次谈判背景」；v1.1 改成 prompt 自己带占位符，
    代码只负责填值 —— 这样 prompt 是完整自包含的，可以单独拿去 Coze 用。
    """
    player = scenario.get("player") or {}
    return {
        "negotiation_topic": scenario.get("name", ""),
        "negotiation_venue": scenario.get("venue", ""),
        "negotiation_agenda": "、".join(scenario.get("agenda") or []),
        "player_entity": player.get("full") or player.get("label", "对方"),
        "player_position": player.get("role", ""),
    }


SLOT_LABEL = {"positions": "立场", "actions": "行动", "numbers": "数字",
              "quotes": "引用", "thinktank": "智库"}


def topic_kb_path(topic_id: str | None) -> Path | None:
    if not topic_id:
        return None
    key = str(topic_id).strip().lower()
    key = TOPIC_ALIAS.get(key, key)
    p = TOPICS_DIR / (key + ".json")
    return p if p.exists() else None


def load_knowledge(topic_id: str | None = None) -> dict:
    """优先读该议题的库；没有就回落到旧的单一库（兼容）。"""
    p = topic_kb_path(topic_id)
    if p:
        try:
            return json.loads(p.read_text(encoding="utf-8-sig"))
        except Exception:
            return {}
    if not KB_FILE.exists():
        return {}
    try:
        return json.loads(KB_FILE.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _is_topic_kb(kb: dict) -> bool:
    return isinstance(kb.get("parties"), dict)


def _render_block(block: dict, title: str) -> list[str]:
    """把一方的卡片渲染成若干行。智库类不作为事实注入。"""
    lines = [f"### {title}"]
    for slot in ("positions", "actions", "numbers", "quotes"):
        for c in block.get(slot) or []:
            tag = SLOT_LABEL.get(slot, slot)
            est = "（估算/预测）" if c.get("conf") == "C" else ""
            lines.append(f"- 【{tag}】{c.get('date', '')} {c.get('text', '')}{est}")
    return lines


def facts_block(side: str, opp: str, topic_id: str | None = None,
                include_all: bool = False) -> str:
    """把事实卡拼成「可引用的事实」段落。

    - 议题库（topics/*.json）：公共事实 + 本局参与方；多边/观战时带上全部各方
    - 旧库（知识库.json）：只有 us/cn 两块
    """
    kb = load_knowledge(topic_id)
    if not kb:
        return ""

    body: list[str] = []

    if _is_topic_kb(kb):
        common = kb.get("common") or {}
        if any(common.get(s) for s in ("positions", "actions", "numbers", "quotes")):
            body += _render_block(common, "会议进程与制度（公共事实，各方共享）")
            body.append("")
        parties = kb.get("parties") or {}
        keys = list(parties.keys()) if include_all else [side, opp]
        for k in keys:
            if k in parties:
                body += _render_block(parties[k], f"{str(k).upper()} 代表团已公开的立场、行动与数据")
                body.append("")
    else:
        body += _render_block(kb.get(side) or {}, f"我方（{side.upper()}）已公开的立场、行动与数据")
        body.append("")
        body += _render_block(kb.get(opp) or {}, f"对方（{opp.upper()}）已公开的立场、行动与数据")
        body.append("")

    if len([x for x in body if x.startswith("- 【")]) == 0:
        return ""

    return "\n".join(
        ["## 可引用的事实（唯一依据，不得编造）"] + body + [
            "### 引用规则",
            "1. 数字、地名、条款号必须与上文完全一致，不要四舍五入、不要自己造。",
            "2. 标注「估算/预测」的，说话时要带「据估算」「预计」等措辞。",
            "3. 不要编造来源、公约条款号、会议文件编号、人名。",
            "4. 没有依据的事改用定性表述（「我方关切」「有待评估」），不要给数字。",
            "5. 引用他方立场时，以它自己那一节的表述为准。",
        ])


def key_numbers(side: str, limit: int = 6, topic_id: str | None = None) -> list[str]:
    """给顾问用的精简数据清单。"""
    kb = load_knowledge(topic_id)
    if _is_topic_kb(kb):
        nums = ((kb.get("parties") or {}).get(side) or {}).get("numbers") or []
    else:
        nums = (kb.get(side) or {}).get("numbers") or []
    return [c.get("text", "") for c in nums[:limit]]


def build_system_prompt(md: str, cfg: dict, scenario: dict | None = None,
                        side: str | None = None, topic_id: str | None = None,
                        include_all: bool = False) -> str:
    """用 str.replace 逐个填占位符。

    不能用 str.format —— prompt 正文里的 JSON 输出格式本身就带大量花括号。
    """
    text = extract_system_prompt(md)
    fill = {k: v for k, v in cfg.items() if k != "label"}
    if scenario:
        fill.update(scenario_vars(scenario, cfg))
    for key, value in fill.items():
        token = "{" + key + "}"
        if token in text:
            text = text.replace(token, str(value))

    if side:
        opp = "cn" if side == "us" else "us"
        block = facts_block(side, opp, topic_id=topic_id, include_all=include_all)
        if block:
            marker = "## 输出格式"
            if marker in text:
                text = text.replace(marker, block + "\n\n" + marker, 1)
            else:
                text = text.rstrip() + "\n\n" + block
    return text


def find_unresolved_placeholders(text: str) -> list[str]:
    """System Prompt 里不该再残留 {xxx} 占位符（JSON 格式示例里的除外）。"""
    known = {"response", "indexes_update", "speaker_score", "interest_delta",
             "image_delta", "trust_delta", "score", "dimension", "position_clarity",
             "diplomatic_tact", "emotional_control", "substance_quality", "feedback"}
    found = set(re.findall(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", text))
    return sorted(found - known)


# ============================ 模型调用 ============================

def build_user_message(round_no: int, indexes: dict, user_message: str) -> str:
    """按 prompt §6.2 的每轮输入格式构造 user 消息。"""
    payload = {
        "round": round_no,
        "current_indexes": {k: indexes[k] for k in INDEX_KEYS},
        "user_message": user_message,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def call_deepseek(messages: list[dict], json_mode: bool = True,
                  temperature: float = 0.7) -> tuple[str, str | None]:
    """返回 (content, finish_reason)。content 可能是空字符串，交给上层判定。"""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        sys.exit("[错误] 未设置 DEEPSEEK_API_KEY。\n"
                 "       PowerShell 里执行：$env:DEEPSEEK_API_KEY = \"sk-xxxx\"\n"
                 "       或先跑 --offline 验证链路。")

    body = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 3000,   # 观战单次发言可达千字，1200 会被截断
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    last_err = None
    for attempt in range(1, 4):
        req = urllib.request.Request(
            API_URL,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            choice = data["choices"][0]
            content = choice["message"].get("content") or ""
            finish = choice.get("finish_reason")
            return content, finish
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:400]
            last_err = f"HTTP {e.code}: {detail}"
            # 有些兼容端点不支持 response_format，退一步再试
            if e.code == 400 and "response_format" in body:
                body.pop("response_format")
                continue
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 * attempt)
                continue
            break
        except Exception as e:  # 网络层
            last_err = f"{type(e).__name__}: {e}"
            if attempt < 3:
                time.sleep(2 * attempt)
                continue
    sys.exit(f"[错误] 调用模型失败：{last_err}")


# ============================ 解析与校验 ============================

def _salvage_objects(text: str) -> dict | None:
    """抢救「对象提前闭合」的 JSON。

    模型常见的括号错误长这样（真实案例）：
        {"response": "...", "speaker_score": {"score": 70.5, "dimension": {...}}, "feedback": "..."}
        , "mood": "陷入僵局", "round_summary": "..."}
                                     ↑ 大括号提前关掉了，后半截变成游离数据

    做法：先按 JSONDecoder 把「第一个完整对象」解析出来，再把后面那段残片
    当独立对象解析，最后合并。合并不全也不怕，能救多少救多少。
    """
    dec = json.JSONDecoder()
    try:
        obj, end = dec.raw_decode(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None

    rest = text[end:].strip()
    if rest:
        frag = rest.lstrip(",").strip()
        if frag and not frag.startswith("{"):
            frag = "{" + frag
        if not frag.endswith("}"):
            frag += "}"
        try:
            extra, _ = dec.raw_decode(frag)
            if isinstance(extra, dict):
                for k, v in extra.items():
                    obj.setdefault(k, v)
                obj["_json_repaired"] = True
        except json.JSONDecodeError:
            obj["_json_repaired"] = True
    return obj


def extract_json(raw: str) -> dict:
    """模型偶尔会包 ```json、加前后废话、数错大括号，这里逐级兜底。"""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("返回内容里没有大括号，根本没有 JSON 对象")
    text = text[start:end + 1]

    first_err = None
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        first_err = e

    # 修尾逗号
    try:
        return json.loads(re.sub(r",(\s*[}\]])", r"\1", text))
    except json.JSONDecodeError:
        pass

    # 修「对象提前闭合」——括号数错，后半截游离在对象之外
    salvaged = _salvage_objects(text)
    if salvaged is not None:
        return salvaged

    raise ValueError(f"JSON 语法错误：{first_err.msg}"
                     f"（第 {first_err.lineno} 行第 {first_err.colno} 列）")


def try_parse(raw: str) -> tuple[bool, dict | None]:
    try:
        return True, extract_json(raw)
    except Exception:
        return False, None


RETRY_NUDGE = (
    "\n\n# 输出铁律（自动重试提示）\n"
    "你上一次的回复无法被解析为 JSON。本次必须只输出一个合法的 JSON 对象：\n"
    "不要 Markdown 代码块，不要 ```json 标记，不要任何解释、道歉或思考过程，不要前后缀文字。\n"
    "第一个字符必须是 {，最后一个字符必须是 }。"
)


def describe_bad(raw: str, finish: str | None) -> str:
    if not raw.strip():
        return f"内容为空（finish_reason={finish}）"
    if finish == "length":
        return f"输出被 max_tokens 截断（finish_reason=length，已收到 {len(raw)} 字符）"
    return f"finish_reason={finish}，收到 {len(raw)} 字符但没有 JSON"


def call_with_retry(messages: list[dict], system_prompt: str,
                    args) -> tuple[dict | None, str, str | None]:
    """调用模型并解析；失败就收紧约束重试，最多 3 次。"""
    raw, finish = "", None
    for attempt in range(1, 4):
        msgs = messages
        if attempt > 1:
            # 重试用更硬的 system 提示，而不是连发两条 user（有的端点不接受）
            msgs = [{"role": "system", "content": system_prompt + RETRY_NUDGE}] + messages[1:]
        json_mode = attempt <= 2 and not args.no_json_mode
        raw, finish = call_deepseek(msgs, json_mode=json_mode, temperature=args.temperature)
        ok, obj = try_parse(raw)
        if ok:
            if attempt > 1:
                print(f"    [重试成功] 第 {attempt} 次拿到合法 JSON")
            return obj, raw, finish
        print(f"    [!] 第 {attempt}/3 次返回无法解析：{describe_bad(raw, finish)}")
        if attempt < 3:
            time.sleep(1)
    return None, raw, finish


def validate_and_normalize(obj: dict, prev: dict) -> tuple[dict, list[str], dict]:
    """校验 + 裁剪 + 累加三指数。返回 (干净对象, 警告列表, 新指数)。"""
    warns: list[str] = []

    if not isinstance(obj, dict):
        raise ValueError("顶层不是 JSON 对象")
    if "response" not in obj or not isinstance(obj["response"], str):
        raise ValueError("缺少 response 字段或类型不对")

    # 抢救回来的 JSON：如实告诉用户，别让修复悄悄发生
    if obj.pop("_json_repaired", False):
        warns.append("模型输出的 JSON 大括号错位（对象提前闭合），已自动拼合修复 —— 这轮数据可用，但要盯着")

    # 模型常把 feedback 写到 speaker_score 外面，挪回去
    top_fb = obj.pop("feedback", None)
    if top_fb is not None:
        ss = obj.get("speaker_score")
        if isinstance(ss, dict):
            if not ss.get("feedback"):
                ss["feedback"] = top_fb
                warns.append("feedback 被写到了 speaker_score 外面，已自动归位")
        elif ss is None:
            warns.append("模型输出了 feedback 但 speaker_score 为 null，已丢弃该点评")

    resp = obj["response"].strip()
    n = len(resp)
    # v1.1：谈判不设字数上限。只在「几乎没有内容」时才告警，防止空回复
    if n < SHORT_SPEECH:
        warns.append(f"发言仅 {n} 字，基本没有实质内容")

    # ---- 三指数 delta ----
    upd = obj.get("indexes_update") or {}
    if not isinstance(upd, dict):
        warns.append("indexes_update 不是对象，已按 0 处理")
        upd = {}
    deltas = {}
    for k in DELTA_KEYS:
        v = upd.get(k, 0)
        try:
            v = float(v)
        except (TypeError, ValueError):
            warns.append(f"{k} 不是数字（{upd.get(k)!r}），按 0 处理")
            v = 0.0
        if abs(v) > DELTA_LIMIT:
            warns.append(f"{k}={v:+.0f} 超出 ±{DELTA_LIMIT} 约定，已裁剪")
            v = max(-DELTA_LIMIT, min(DELTA_LIMIT, v))
        deltas[k] = int(round(v))
    obj["indexes_update"] = deltas

    new_indexes = {}
    for key, dk in zip(INDEX_KEYS, DELTA_KEYS):
        raw = prev[key] + deltas[dk]
        val = max(0, min(100, raw))
        if val != raw:
            warns.append(f"{key} 累加后 {raw} 越界，已截断到 {val}")
        new_indexes[key] = int(val)

    # ---- 评分自洽性 ----
    ss = obj.get("speaker_score")
    if ss is None:
        if obj.get("_round", 1) > 1:
            warns.append("非首轮但 speaker_score 为 null")
    elif isinstance(ss, dict):
        dim = ss.get("dimension") or {}
        vals, ok = {}, True
        for k, w in SCORE_WEIGHTS.items():
            v = dim.get(k)
            try:
                v = float(v)
            except (TypeError, ValueError):
                warns.append(f"评分维度 {k} 缺失/非数字")
                ok = False
                v = 0.0
            vals[k] = max(0.0, min(100.0, v))
        if ok:
            recomputed = sum(vals[k] * w for k, w in SCORE_WEIGHTS.items())
            claimed = ss.get("score")
            try:
                claimed = float(claimed)
            except (TypeError, ValueError):
                warns.append("speaker_score.score 非数字")
                claimed = recomputed
            if abs(claimed - recomputed) > 1.0:
                warns.append(f"总分 {claimed:.1f} 与四维加权值 {recomputed:.1f} 不符（差 {claimed - recomputed:+.1f}），已按公式重算")
            ss["score"] = round(recomputed, 1)
            ss["dimension"] = {k: int(round(v)) for k, v in vals.items()}
        fb = ss.get("feedback")
        if not isinstance(fb, str) or not fb.strip():
            warns.append("feedback 为空")
        elif not (15 <= len(fb) <= 60):
            warns.append(f"feedback 长度 {len(fb)} 字，偏离 prompt 要求的 20-40 字")
    else:
        warns.append("speaker_score 类型异常")

    # ---- 隐藏任务泄露检测 ----
    leak_marks = ["隐藏任务", "隐藏目标", "我的底牌", "底牌是", "秘密任务"]
    hit = [m for m in leak_marks if m in resp]
    if hit:
        warns.append(f"疑似泄露隐藏任务卡（命中：{'、'.join(hit)}）")

    for k in ("mood", "round_summary"):
        if not isinstance(obj.get(k), str) or not obj.get(k).strip():
            warns.append(f"缺少 {k}")

    return obj, warns, new_indexes


def apply_player_indexes(obj: dict, prev: dict) -> tuple[dict, list[str], dict]:
    """累加【玩家一方】的三指数。

    数据来源：模型额外输出的 player_indexes_update（含义：本轮它的发言对玩家一方的影响）。
    若模型没给，本轮按 0 计并告警 —— 不猜、不镜像，宁可显示没变化。
    """
    warns: list[str] = []
    upd = obj.get("player_indexes_update")
    if not isinstance(upd, dict):
        upd = {}
        warns.append("模型未输出 player_indexes_update，本轮我方指数按 0 计")

    deltas: dict[str, int] = {}
    for k in DELTA_KEYS:
        v = upd.get(k, 0)
        try:
            v = float(v)
        except (TypeError, ValueError):
            warns.append(f"player_{k} 不是数字，按 0 处理")
            v = 0.0
        if abs(v) > DELTA_LIMIT:
            warns.append(f"player_{k}={v:+.0f} 超出 ±{DELTA_LIMIT}，已裁剪")
            v = max(-DELTA_LIMIT, min(DELTA_LIMIT, v))
        deltas[k] = int(round(v))
    obj["player_indexes_update"] = deltas

    new = {}
    for key, dk in zip(INDEX_KEYS, DELTA_KEYS):
        raw = prev[key] + deltas[dk]
        val = max(0, min(100, raw))
        if val != raw:
            warns.append(f"我方 {key} 累加后 {raw} 越界，已截断到 {val}")
        new[key] = int(val)
    return obj, warns, new


# ============================ 立场与关系 ============================

STANCE_ALIASES = {
    "support": "support", "支持": "support", "赞成": "support", "同意": "support",
    "conditional_support": "support", "有条件支持": "support", "倾向支持": "support",
    "swing": "swing", "摇摆": "swing", "中立": "swing", "观望": "swing", "保留": "swing",
    "oppose": "oppose", "反对": "oppose", "拒绝": "oppose", "倾向反对": "oppose",
}
RELATION_LIMIT = 5


def _as_party_key(value, party_keys, name_to_key):
    text = str(value or "").strip().lower()
    if not text:
        return None
    if text in party_keys:
        return text
    if text in name_to_key:
        return name_to_key[text]
    for name, key in name_to_key.items():
        if name and name in text:
            return key
    return None


def normalize_diplomacy(obj: dict, party_keys=None, name_to_key=None) -> list[str]:
    """规范化模型输出的立场、发言对象与关系判断。

    模型可以提出判断，但对象必须真实存在于本局、数值必须落在约定范围内，
    否则丢弃并告警 —— 不能让它凭空给一个不存在的主体打分。
    """
    warns: list[str] = []
    party_keys = [str(key) for key in (party_keys or [])]
    name_to_key = {str(k): str(v) for k, v in (name_to_key or {}).items()}

    # ---- stance ----
    raw_stance = obj.get("stance")
    position, reason, conditions = "swing", "", []
    if isinstance(raw_stance, str):
        position = STANCE_ALIASES.get(raw_stance.strip().lower())
        if position is None:
            warns.append("stance 写成字符串但无法识别（" + raw_stance[:12] + "），按 swing 处理")
            position = "swing"
    elif isinstance(raw_stance, dict):
        raw_position = raw_stance.get("position") or raw_stance.get("stance")
        position = STANCE_ALIASES.get(str(raw_position or "").strip().lower())
        if position is None:
            warns.append("stance.position 缺失或无法识别，按 swing 处理")
            position = "swing"
        reason = str(raw_stance.get("reason") or "").strip()[:60]
        raw_conditions = raw_stance.get("conditions")
        if isinstance(raw_conditions, str):
            raw_conditions = [raw_conditions]
        if isinstance(raw_conditions, list):
            conditions = [str(item).strip()[:40] for item in raw_conditions if str(item).strip()][:2]
    else:
        warns.append("模型未输出 stance，本局立场按 swing 处理")
        position = "swing"
    obj["stance"] = {"position": position, "reason": reason, "conditions": conditions}

    # ---- addressed_to ----
    raw_targets = obj.get("addressed_to")
    missing = "addressed_to" not in obj
    if isinstance(raw_targets, str):
        raw_targets = [raw_targets]
    targets: list[str] = []
    if isinstance(raw_targets, list):
        for item in raw_targets:
            key = _as_party_key(item, party_keys, name_to_key)
            if key and key not in targets:
                targets.append(key)
            elif str(item or "").strip():
                warns.append("addressed_to 里的「" + str(item)[:10] + "」不是本局参与方，已忽略")
    elif raw_targets not in (None, ""):
        warns.append("addressed_to 类型异常，按面向全体处理")
    obj["addressed_to"] = targets[:6]
    # 模型完全没写这个字段时，允许调用方用规则补一个默认对象；
    # 显式写 [] 表示"面向全体"，必须尊重。
    obj["_addressed_auto"] = missing

    # ---- relation_assessment ----
    raw_relations = obj.get("relation_assessment")
    relations: dict[str, dict] = {}
    if isinstance(raw_relations, dict):
        for raw_key, value in raw_relations.items():
            key = _as_party_key(raw_key, party_keys, name_to_key)
            if not key:
                warns.append("relation_assessment 里的「" + str(raw_key)[:10] + "」不在本局，已忽略")
                continue
            if not isinstance(value, dict):
                warns.append("relation_assessment." + key + " 不是对象，已忽略")
                continue
            try:
                delta = int(round(float(value.get("trust_delta", 0) or 0)))
            except (TypeError, ValueError):
                warns.append("relation_assessment." + key + ".trust_delta 不是数字，按 0 处理")
                delta = 0
            if abs(delta) > RELATION_LIMIT:
                warns.append("relation_assessment." + key + " 的 trust_delta 超出 ±" + str(RELATION_LIMIT) + "，已裁剪")
                delta = max(-RELATION_LIMIT, min(RELATION_LIMIT, delta))
            relations[key] = {"trust_delta": delta, "reason": str(value.get("reason") or "").strip()[:60]}
    elif raw_relations not in (None, "", {}):
        warns.append("relation_assessment 类型异常，已忽略")
    obj["relation_assessment"] = relations

    # ---- claim：对外宣称的动作与强度（可能夸大，实际数值仍按牌面结算）----
    raw_claim = obj.get("claim")
    claim: dict = {}
    if isinstance(raw_claim, dict):
        action = str(raw_claim.get("action") or "").strip().lower()
        if action in ("offer", "concede", "demand", "threat", "disclose", "probe", "procedure"):
            claim["action"] = action
        try:
            strength = int(round(float(raw_claim.get("strength"))))
        except (TypeError, ValueError):
            strength = None
        if strength is not None:
            claim["strength"] = max(1, min(10, strength))
        note = str(raw_claim.get("note") or "").strip()[:60]
        if note:
            claim["note"] = note
    elif raw_claim not in (None, ""):
        warns.append("claim 类型异常，已忽略")
    obj["claim"] = claim

    return warns


# ============================ 离线自检数据 ============================

OFFLINE_RESPONSES = [
    {
        "response": "我方欢迎各方与会。美国的立场是一贯而明确的：AI 治理必须以规则为基础，由负责任的技术领先国家共同塑造标准。"
                    "我们建议以「AI 安全联盟」的既有实践为蓝本，设立高风险 AI 出口管制的可核查机制，并在此基础上讨论算力"
                    "与数据议题。我方愿听取各方意见，但任何框架都必须承认技术领先者的责任与权益——这一点没有讨论余地。",
        "indexes_update": {"interest_delta": 2, "image_delta": -2, "trust_delta": 2},
        "player_indexes_update": {"interest_delta": -2, "image_delta": 1, "trust_delta": -1},
        "speaker_score": None,
        "mood": "审慎观望，初步对峙",
        "round_summary": "美方以「规则＋技术领先」为锚，前置抛出可核查机制与联盟蓝本两项条件。",
    },
    {
        "response": "我方注意到中方的关切。需要指出的是，「可核查」并非审查，而是建立信任的技术手段——我方愿在透明度上展现"
                    "灵活性，例如接受联合国框架下的技术性通报。但前提是：监督机制必须具备实际约束力，且不削减现有出口管制的"
                    "有效性。作为交换，我方可以考虑在能力建设议题上增加投入，以回应发展中国家的关切。",
        "indexes_update": {"interest_delta": 1, "image_delta": -2, "trust_delta": -1},
        "player_indexes_update": {"interest_delta": 2, "image_delta": 1, "trust_delta": 1},
        "speaker_score": {
            "score": 82.7,
            "dimension": {"position_clarity": 85, "diplomatic_tact": 80,
                          "emotional_control": 88, "substance_quality": 78},
            "feedback": "立场鲜明且以多边框架反击有力，但未提出具体替代方案，施压色彩略重。",
        },
        "mood": "分歧明确，进入交锋",
        "round_summary": "美方以「可核查≠审查」澄清立场，用能力建设投入作交换，同时划定监督约束力底线。",
    },
    {
        "response": "我方可对专家组授权来源作技术性处理，这一点不构成障碍。但我方必须强调：评估专家组的职能应限于风险通报，"
                    "不得延伸至对既有出口管制措施的复核，否则将动摇整个框架的可行性。关于算力配额，我方不反对设立公共算力池，"
                    "但出资与管理须遵循市场原则，由贡献度决定份额。倘若各方接受这一逻辑，我方愿在基金出资上给出具体数字。",
        "indexes_update": {"interest_delta": 3, "image_delta": 2, "trust_delta": 1},
        "player_indexes_update": {"interest_delta": -1, "image_delta": 2, "trust_delta": 2},
        "speaker_score": {
            "score": 80.4,
            "dimension": {"position_clarity": 84, "diplomatic_tact": 78,
                          "emotional_control": 82, "substance_quality": 75},
            "feedback": "让步姿态明确且提出了独立专家组构想，但未守住算力配额的核心分歧点。",
        },
        "mood": "温和推进，出现交集",
        "round_summary": "美方接受专家组授权来源调整，但把职能限制在风险通报，并把配额分配拉回市场原则。",
    },
]


# ============================ 输出 ============================

def disp_width(text: str) -> int:
    """终端显示宽度：东亚宽字符（汉字、全角标点）算 2 列，其余算 1 列。"""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def pad(text: str, width: int) -> str:
    return text + " " * max(0, width - disp_width(text))


def bar(value: float, width: int = 20) -> str:
    filled = int(round(value / 100 * width))
    return "█" * filled + "·" * (width - filled)


def print_round_header(round_no: int, agent_label: str, total: int) -> None:
    print()
    print("=" * 72)
    print(f"  第 {round_no} / {total} 轮 · 对手：{agent_label}")
    print("=" * 72)
    print()


def print_speech(who: str, text: str) -> None:
    print(f"[{who}的发言]  ({len(text)} 字)")
    for line in wrap_cn(text, 68):
        print("    " + line)
    print()


def index_cell(before: int, after: int, delta: int) -> str:
    arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "–")
    return f"{before:>3} → {after:>3} {arrow}{delta:>+3}  {bar(after, 9)}"


def print_indexes(player_label: str, agent_label: str,
                  p_before: dict, p_after: dict, p_delta: dict,
                  a_before: dict, a_after: dict, a_delta: dict) -> None:
    print("    双方三指数")
    print("    " + pad("", 12)
          + pad(f"{player_label}（你）", 30)
          + f"{agent_label}（对手）")
    for key, dk in zip(INDEX_KEYS, DELTA_KEYS):
        print("    " + pad(INDEX_LABELS[key], 12)
              + pad(index_cell(p_before[key], p_after[key], p_delta[dk]), 30)
              + index_cell(a_before[key], a_after[key], a_delta[dk]))
    print()


def print_eval(obj: dict, warns: list[str]) -> None:
    ss = obj.get("speaker_score")
    if isinstance(ss, dict):
        dim = ss["dimension"]
        print(f"    对我方发言的评分  {ss['score']}   "
              f"(立场 {dim['position_clarity']} / 策略 {dim['diplomatic_tact']} / "
              f"情绪 {dim['emotional_control']} / 内容 {dim['substance_quality']})")
        print(f"    点评              {ss.get('feedback', '')}")
    else:
        print("    对我方发言的评分  —（首轮无我方发言可评）")
    print(f"    氛围              {obj.get('mood', '')}")
    print(f"    本轮小结          {obj.get('round_summary', '')}")
    if warns:
        print()
        for w in warns:
            print(f"    [!] {w}")
    print()


def wrap_cn(text: str, width: int) -> list[str]:
    """按显示宽度折行（中文算 2 列），并避免标点落在行首。"""
    NO_LEAD = "，。、；：！？）》」』】…—"
    lines, cur, w = [], "", 0
    for ch in text:
        cw = disp_width(ch)
        if w + cw > width:
            lines.append(cur)
            cur, w = "", 0
        cur += ch
        w += cw
    if cur:
        lines.append(cur)
    # 行首标点回拉到上一行末尾
    for i in range(1, len(lines)):
        while lines[i] and lines[i][0] in NO_LEAD:
            lines[i - 1] += lines[i][0]
            lines[i] = lines[i][1:]
    return [ln for ln in lines if ln]


# ============================ 主流程 ============================

def main() -> int:
    ap = argparse.ArgumentParser(description="谈判对手 Agent 命令行验证工具")
    ap.add_argument("--agent", default="us", help="扮演哪个 Agent（agents.json 里的键）")
    ap.add_argument("--rounds", type=int, default=3, help="打几轮，默认 3")
    ap.add_argument("--offline", action="store_true", help="不联网，用内置数据跑通链路")
    ap.add_argument("--interactive", action="store_true", help="手动输入中方发言")
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--no-json-mode", action="store_true", help="关闭 response_format=json_object")
    ap.add_argument("--check", action="store_true", help="只检查 agents.json 配置，不跑对局")
    args = ap.parse_args()

    # 没配 Key 就自动降级到离线自检，避免双击 run.bat 直接报错退出
    notice = None
    if not args.offline and not os.environ.get("DEEPSEEK_API_KEY", "").strip():
        args.offline = True
        notice = ("未检测到 DEEPSEEK_API_KEY，已自动切换为【离线自检】模式。\n"
                  "       要接真模型：先执行  $env:DEEPSEEK_API_KEY = \"sk-xxxx\"  再重新运行。")

    md = load_prompt_markdown()
    agents = load_agents()

    if args.check:
        return check_config(md, agents)

    if args.agent not in agents:
        sys.exit(f"[错误] agents.json 里没有 '{args.agent}'，可选：{', '.join(k for k in agents if not k.startswith('_'))}")
    cfg = agents[args.agent]
    label = cfg.get("label", args.agent)
    scenario = agents.get("_scenario", {})
    player_cfg = scenario.get("player", {})
    p_label = player_cfg.get("label", "我方")
    p_role = player_cfg.get("role", "")

    system_prompt = build_system_prompt(md, cfg, scenario,
                                        side=args.agent if args.agent in ("us", "cn") else None)
    leftovers = find_unresolved_placeholders(system_prompt)

    indexes = {k: int(cfg[f"initial_{k}"]) for k in INDEX_KEYS}
    player_idx = {k: int(player_cfg.get(f"initial_{k}", 50)) for k in INDEX_KEYS}

    print()
    print("╔" + "═" * 70 + "╗")
    print("║" + pad("  谈判对手 Agent · 命令行验证", 70) + "║")
    print("╚" + "═" * 70 + "╝")
    print(f"  谈判主题    : {scenario.get('name') or '（agents.json 未配置 _scenario）'}")
    if scenario.get("venue"):
        print(f"  会议场合    : {scenario['venue']}")
    agenda = scenario.get("agenda") or []
    if agenda:
        for i, item in enumerate(agenda):
            head = "  核心议题    : " if i == 0 else "                "
            print(f"{head}{item}")
    else:
        print("  核心议题    : （未配置）")
    print(f"  你扮演      : {p_label}" + (f"（{p_role}）" if p_role else ""))
    print(f"  对手        : {label}（{cfg.get('agent_position', '')}）")
    print(f"  模型        : {'离线自检（不联网）' if args.offline else MODEL}")
    print(f"  轮次        : {args.rounds}")
    print(f"  Prompt 文件 : {PROMPT_FILE.name}  (System {len(system_prompt)} 字)")
    if leftovers:
        print(f"  [!] 未填充的占位符：{', '.join(leftovers)}")
    else:
        print("  [OK] 占位符已全部填充")
    print(f"  初始指数    : {p_label}（你）  主体利益值 {player_idx['interest']}  "
          f"国际形象值 {player_idx['image']}  盟友信任度 {player_idx['trust']}")
    print(f"                {label}（对手）  主体利益值 {indexes['interest']}  "
          f"国际形象值 {indexes['image']}  盟友信任度 {indexes['trust']}")
    print()
    if notice:
        print("  " + notice.replace("\n", "\n  "))
        print()

    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    history: list[dict] = []
    all_warns: list[list[str]] = []
    trace: list[dict] = []

    for r in range(1, args.rounds + 1):
        print_round_header(r, label, args.rounds)
        if args.interactive:
            print(f"--- 请输入第 {r} 轮{p_label}发言（直接回车 = 使用内置示例）---")
            line = input(f"{p_label} > ").strip()
            if not line:
                line = CHINA_LINES[(r - 1) % len(CHINA_LINES)]
        else:
            line = CHINA_LINES[(r - 1) % len(CHINA_LINES)]
        line = line.replace("\n", " ")

        print_speech(p_label, line)

        user_msg = build_user_message(r, indexes, line)
        messages.append({"role": "user", "content": user_msg})

        if args.offline:
            raw = json.dumps(OFFLINE_RESPONSES[(r - 1) % len(OFFLINE_RESPONSES)],
                             ensure_ascii=False)
            obj, finish = extract_json(raw), "offline"
        else:
            obj, raw, finish = call_with_retry(messages, system_prompt, args)

        if obj is None:
            print(f"\n[失败] 第 {r} 轮重试 3 次后仍无法解析为 JSON。")
            print(f"        原因：{describe_bad(raw, finish)}")
            print("-------- 原始返回（repr，能看见空串和隐藏字符）--------")
            print(repr(raw))
            print("-----------------------------------------------------")
            LOG_DIR.mkdir(exist_ok=True)
            bad_path = LOG_DIR / f"bad-{datetime.now():%Y%m%d-%H%M%S}-r{r}.txt"
            bad_path.write_text(
                f"round={r}\nfinish_reason={finish}\nlen={len(raw)}\n\n{raw}",
                encoding="utf-8")
            print(f"        原始返回已存到：{bad_path}")

            # 兜底：如果模型给的是一段能当发言用的文字，就别让整局崩掉
            prose = raw.strip()
            if 20 <= len(prose) <= 600 and finish != "length":
                print("        [兜底] 上面这段文字将作为本轮发言，本轮的指数变化与评分按 0 计。")
                obj = {
                    "response": prose,
                    "_fallback": True,
                }
                raw_note = "fallback"
            else:
                return 2

        obj["_round"] = r
        before = dict(indexes)
        p_before = dict(player_idx)
        if obj.get("_fallback"):
            obj.setdefault("indexes_update", {"interest_delta": 0, "image_delta": 0, "trust_delta": 0})
            obj.setdefault("player_indexes_update", {"interest_delta": 0, "image_delta": 0, "trust_delta": 0})
            obj.setdefault("speaker_score", None)
            obj.setdefault("mood", "（模型未提供，本轮降级）")
            obj.setdefault("round_summary", "（模型未按 JSON 格式输出，已用兜底模式）")
        try:
            obj, warns, indexes = validate_and_normalize(obj, before)
            obj, p_warns, player_idx = apply_player_indexes(obj, p_before)
            warns.extend(p_warns)
        except Exception as e:
            print(f"\n[失败] 第 {r} 轮校验不通过：{e}")
            print(repr(raw))
            return 2

        if obj.get("_fallback"):
            warns.insert(0, "【兜底】模型未输出 JSON，本轮发言取原始文本，指数与评分未计入 —— 该轮数据不可信")

        all_warns.append(warns)
        print_speech(label, obj["response"])
        print_indexes(p_label, label, p_before, player_idx, obj["player_indexes_update"],
                      before, indexes, obj["indexes_update"])
        print_eval(obj, warns)

        # 历史里放【完整 JSON】，让模型模仿自己上一轮的正确格式。
        # （早先只存纯发言文本，结果模型第 2 轮就开始说大白话、不再吐 JSON）
        hist_obj = {k: v for k, v in obj.items() if not k.startswith("_")}
        messages.append({"role": "assistant",
                         "content": json.dumps(hist_obj, ensure_ascii=False)})
        history.append({"round": r, "china": line, "agent_raw": obj})

        trace.append({
            "round": r,
            "china_message": line,
            "agent_response": obj["response"],
            "indexes_update": obj["indexes_update"],
            "indexes_after": dict(indexes),
            "player_indexes_update": obj["player_indexes_update"],
            "player_indexes_after": dict(player_idx),
            "speaker_score": obj.get("speaker_score"),
            "mood": obj.get("mood"),
            "round_summary": obj.get("round_summary"),
            "warnings": warns,
        })

    # ---------- 汇总 ----------
    total_warns = sum(len(w) for w in all_warns)
    scores = [t["speaker_score"]["score"] for t in trace
              if isinstance(t.get("speaker_score"), dict)]
    print("=" * 72)
    print("  跑完汇总")
    print("=" * 72)
    print(f"  谈判主题        {scenario.get('name', '')}")
    print(f"  轮次            {args.rounds}")
    print("  最终指数  " + pad(f"{p_label}（你）", 14)
          + pad(f"主体利益值 {player_idx['interest']}", 18)
          + pad(f"国际形象值 {player_idx['image']}", 18)
          + f"盟友信任度 {player_idx['trust']}")
    print("            " + pad(f"{label}（对手）", 14)
          + pad(f"主体利益值 {indexes['interest']}", 18)
          + pad(f"国际形象值 {indexes['image']}", 18)
          + f"盟友信任度 {indexes['trust']}")
    print(f"  我方平均得分    {sum(scores)/len(scores):.1f}" if scores else "  我方平均得分    —")
    fallbacks = sum(1 for wl in all_warns if any("兜底" in w for w in wl))
    if fallbacks == 0:
        print(f"  JSON 解析       全部通过 ({args.rounds}/{args.rounds})")
    else:
        print(f"  JSON 解析       {args.rounds - fallbacks}/{args.rounds} 通过，"
              f"{fallbacks} 轮降级为纯文本兜底")
    print(f"  校验告警        {total_warns} 条")
    if total_warns:
        for i, wl in enumerate(all_warns, 1):
            for w in wl:
                print(f"      第 {i} 轮：{w}")
    print()

    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"run-{datetime.now():%Y%m%d-%H%M%S}.json"
    log_path.write_text(json.dumps({
        "agent": args.agent,
        "label": label,
        "scenario": scenario,
        "player": p_label,
        "model": "offline" if args.offline else MODEL,
        "prompt_file": str(PROMPT_FILE),
        "rounds": args.rounds,
        "final_indexes": indexes,
        "final_player_indexes": player_idx,
        "trace": trace,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  对局记录已存    {log_path}")
    print()

    return 0 if total_warns == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
