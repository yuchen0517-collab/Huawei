#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo1.1"))

import server  # noqa: E402
from multi_agent import CountryAgent  # noqa: E402
from settlement import SettlementEngine  # noqa: E402

PASS, FAIL = 0, 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print("  [PASS] " + name)
    else:
        FAIL += 1
        print("  [FAIL] " + name + "  " + str(detail))


def reply(messages, prompt):
    return {
        "response": "本方提出一项可供各方讨论的具体方案。",
        "private_note": "只供本方使用的内部判断",
        "round_summary": "提出方案",
        "mood": "审慎",
    }, "{}", "stop"


print("\n== 1. 国家 Agent 的公共信息与私有记忆 ==")
us = CountryAgent("us", "美国")
eu = CountryAgent("eu", "欧盟")
us_turn = us.act(
    system_prompt="美国 Prompt",
    public_messages=[{"role": "player", "sender": "中国代表", "text": "建议先确认共同事实。"}],
    turn_input="请回应",
    call_model=reply,
)
us.remember(1, us_turn["obj"])
eu_turn = eu.act(
    system_prompt="欧盟 Prompt",
    public_messages=[{"role": "agent", "sender": "美国代表", "text": "美国公开发言"}],
    turn_input="请回应",
    call_model=reply,
)
check("公共会场记录对其他国家可见", "美国公开发言" in eu_turn["user_content"])
check("美国私有记忆不会泄露给欧盟", "只供本方使用" not in eu_turn["user_content"])
us_second = us.act(
    system_prompt="美国 Prompt",
    public_messages=[],
    turn_input="继续谈判",
    call_model=reply,
)
check("美国自己能读取私有记忆", "只供本方使用" in us_second["user_content"])
check("公开 Agent 信息不含记忆正文", "memory_count" in us.public_info() and "private_memory" not in us.public_info())
check("只有完成校验的国家回合才累计记忆", us.turns == 1 and eu.turns == 0)

print("\n== 2. 结算引擎统一更新指数、任务与事件 ==")
settlement = SettlementEngine(server.engine)
st = {
    "mode": "multi",
    "you_key": "cn",
    "speaker_key": "us",
    "party_indexes": {
        "cn": {"interest": 50, "image": 70, "trust": 65},
        "us": {"interest": 50, "image": 70, "trust": 65},
        "eu": {"interest": 50, "image": 75, "trust": 60},
    },
    "player_indexes": {"interest": 50, "image": 70, "trust": 65},
    "agent_indexes": {"interest": 50, "image": 70, "trust": 65},
    "game_log": [],
    "payoff_total": {"player": 0, "agent": 0},
}
game = {
    "agent_interest": 55,
    "player_interest": 48,
    "record": {"payoff": {"player": -2, "agent": 5}},
}
settlement.apply_turn(
    st,
    speaker_key="us",
    player_key="cn",
    speaker_indexes={"interest": 55, "image": 68, "trust": 66},
    player_indexes={"interest": 48, "image": 69, "trust": 64},
    game_result=game,
)
check("发言国指数写入自己的状态", st["party_indexes"]["us"]["interest"] == 55)
check("玩家指数独立更新", st["party_indexes"]["cn"]["interest"] == 48)
check("未行动国家指数不被覆盖", st["party_indexes"]["eu"] == {"interest": 50, "image": 75, "trust": 60})
check("博弈日志由结算引擎记录", len(st["game_log"]) == 1 and st["payoff_total"]["agent"] == 5)
check("本轮增量与累计指数分开", st["party_delta"]["us"]["interest"] == 5 and st["party_indexes"]["us"]["interest"] == 55)
settlement.apply_event(st, {"effects": {
    "player": {"trust_delta": -3},
    "agent": {"image_delta": 2},
}})
check("事件同步影响玩家与发言国", st["party_indexes"]["cn"]["trust"] == 61 and st["party_indexes"]["us"]["image"] == 70)
tasks = [{"text": "任务一", "done": False}, {"text": "任务二", "done": False}]
changed = settlement.apply_task_results(tasks, [0, "1", 9, "无效"])
check("任务序号统一校验并更新", changed == [0, 1] and all(task["done"] for task in tasks))
check("重复任务判定不会重复结算", settlement.apply_task_results(tasks, [0]) == [])

print("\n== 3. 三个知识库均可提供多方主体 ==")
for topic_id, expected in (
    ("compute-chip", {"cn", "us"}),
    ("unclos", {"cn", "us", "su", "br", "id", "jp", "in", "eg", "sg"}),
    ("dst", {"cn", "us", "eu", "in", "uk", "tr"}),
):
    kb = server.engine.load_knowledge(topic_id)
    parties = set((kb.get("parties") or {}).keys())
    check(topic_id + " 主体完整", expected <= parties, parties)
check("英国使用数字税专属人设", "数字服务税" in server.scene_ctx({"mode": "multi", "rivals": ["uk"], "topic": "数字服务税与跨境征税权分配", "topic_id": "dst"}, speaker="uk")["agent_cfg"]["public_position"])
check("土耳其使用数字税专属人设", "第7194号法" in server.scene_ctx({"mode": "multi", "rivals": ["tr"], "topic": "数字服务税与跨境征税权分配", "topic_id": "dst"}, speaker="tr")["agent_cfg"]["public_position"])

print("\n== 4. 三个国家 Agent 连续完成真实回合流程 ==")
scene = {
    "mode": "multi",
    "player": "cn",
    "rivals": ["us", "eu", "in"],
    "topic": "算力资源分配与芯片出口管制",
    "topic_id": "compute-chip",
}
session = server.initial_state(scene)
with patch.object(server, "current_key", return_value=""), patch.object(server, "maybe_event", return_value=None):
    results = [server._do_turn(session, "我方建议各方提出可核查的交换条件。") for _ in range(3)]
check("三轮均成功结算", all("error" not in result for result in results), results)
check("三个国家依次独立行动", [message.get("key") for message in session["messages"] if message.get("role") == "agent"] == ["us", "eu", "in"])
check("每个国家都有独立运行时", set(session["country_agents"]) == {"us", "eu", "in"})
check("每个国家只行动一次", all(agent.turns == 1 for agent in session["country_agents"].values()))
check("多方状态包含玩家与三个国家", set(session["party_indexes"]) == {"cn", "us", "eu", "in"})
public = server.public_state(session)
check("公开状态可以正常 JSON 序列化", isinstance(json.dumps(public, ensure_ascii=False), str))
check("公开状态不暴露私有记忆", "private_memory" not in json.dumps(public, ensure_ascii=False))

print("\n== 5. 数字税六国 Agent 全部参与自动推演 ==")
dst_scene = {
    "mode": "observe",
    "rivals": ["cn", "us", "eu", "in", "uk", "tr"],
    "topic": "数字服务税与跨境征税权分配",
    "topic_id": "dst",
}
dst_session = server.initial_state(dst_scene)
with patch.object(server, "current_key", return_value=""), patch.object(server, "maybe_event", return_value=None):
    dst_results = [server._do_turn(dst_session, "", auto=True) for _ in range(6)]
dst_speakers = [message.get("key") for message in dst_session["messages"] if message.get("role") == "agent"]
check("六轮均成功结算", all("error" not in result for result in dst_results), dst_results)
check("六国全部依次行动", dst_speakers == ["cn", "us", "eu", "in", "uk", "tr"], dst_speakers)
check("英国和土耳其都有独立 Agent", {"uk", "tr"} <= set(dst_session["country_agents"]))
check("六国都有独立指数状态", set(dst_session["party_indexes"]) == {"cn", "us", "eu", "in", "uk", "tr"})
check("英国和土耳其事实卡进入 Prompt", "英国DST门槛" in server.system_prompt_now(dst_scene, speaker="uk") and "7.5%" in server.system_prompt_now(dst_scene, speaker="tr"))

print(f"\n结果：{PASS} 通过 / {FAIL} 失败\n")
sys.exit(0 if FAIL == 0 else 1)
