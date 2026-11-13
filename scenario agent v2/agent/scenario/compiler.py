"""场景编译 Agent：把议题编译成结构化 Scenario。

设计约束（手册 2.3 接口纪律）：
· 任何模型输出先过 JSON Schema，再过业务校验（models.validate_scenario）
· 校验失败不得返回半成品；重试仍失败则抛 ScenarioCompileError
· 不读数据库、不写状态、不碰路由，纯函数式：议题进，场景出

对外只有一个入口：compile_scenario()。
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from agent.scenario import negotiability as negotiability_module
from agent.scenario.models import Assumption, Problem, Scenario, validate_scenario

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]
PROMPT_PATH = BASE_DIR / "prompts" / "scenario_compile.md"
SCHEMA_PATH = BASE_DIR / "docs" / "contracts" / "scenario.schema.json"

DEFAULT_MODEL = "deepseek-chat"
DEFAULT_BASE_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_TIMEOUT = 90.0

__all__ = [
    "CompileResult",
    "ScenarioCompileError",
    "compile_scenario",
    "compile_from_narrowing",
    "parse_scenario_json",
    "strip_code_fence",
]


class ScenarioCompileError(RuntimeError):
    """编译失败。不返回半成品，调用方拿到异常后可决定重试或降级。

    stage 取值：prompt / llm / parse / schema / validate
    """

    def __init__(
        self,
        message: str,
        *,
        stage: str = "unknown",
        last_issues: list[Problem] | None = None,
        raw_output: str | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.last_issues = list(last_issues or [])
        self.raw_output = raw_output

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "message": str(self),
            "issues": [problem.to_dict() for problem in self.last_issues],
        }


@dataclass
class CompileResult:
    """编译结果。scenario 为 None 表示议题未通过可谈判性检查，未调用模型。"""

    scenario: Scenario | None
    negotiability: dict[str, Any]
    attempts: int = 0
    problems: list[Problem] = field(default_factory=list)
    raw_output: str | None = None

    @property
    def ok(self) -> bool:
        return self.scenario is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "attempts": self.attempts,
            "negotiability": self.negotiability,
            "problems": [problem.to_dict() for problem in self.problems],
            "scenario": self.scenario.to_dict() if self.scenario is not None else None,
        }


_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def strip_code_fence(text: str) -> str:
    match = _FENCE_PATTERN.search(text)
    if match is not None:
        return match.group(1)
    return text


def _extract_object(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ScenarioCompileError("输出里找不到 JSON 对象", stage="parse", raw_output=text)
    return text[start:end + 1]


def _repair_trailing_commas(text: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", text)


def parse_scenario_json(text: str) -> dict[str, Any]:
    """宽松解析模型输出：剥围栏 → 截取对象 → 逐级修复 → dict。"""
    if not isinstance(text, str) or not text.strip():
        raise ScenarioCompileError("模型返回空内容", stage="parse", raw_output=text)

    candidate = _extract_object(strip_code_fence(text))

    for transform in (
        lambda raw: raw,
        _repair_trailing_commas,
        lambda raw: _repair_trailing_commas(raw.replace("'", '"')),
    ):
        try:
            data = json.loads(transform(candidate))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
        raise ScenarioCompileError("模型输出的 JSON 顶层不是对象", stage="parse", raw_output=text)

    raise ScenarioCompileError("模型输出不是合法 JSON", stage="parse", raw_output=text)


_VALIDATOR = None


def _schema_validator():
    global _VALIDATOR
    if _VALIDATOR is None:
        if not SCHEMA_PATH.is_file():
            return None
        try:
            import jsonschema
        except ImportError:
            return None
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8-sig"))
        _VALIDATOR = jsonschema.Draft202012Validator(schema)
    return _VALIDATOR


def schema_messages(data: Mapping[str, Any]) -> list[str]:
    validator = _schema_validator()
    if validator is None:
        return []
    messages = []
    for error in sorted(validator.iter_errors(data), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.path) or "<根>"
        messages.append(f"{location}: {error.message}")
    return messages


def default_llm(messages: list[dict[str, str]], *, timeout: float = DEFAULT_TIMEOUT) -> str:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise ScenarioCompileError(
            "未设置 DEEPSEEK_API_KEY；测试请注入 llm= 参数，或改用离线验证脚本",
            stage="llm",
        )
    base_url = os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
    model = os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "stream": False,
    }
    request = urllib.request.Request(
        base_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ScenarioCompileError(f"模型接口返回 HTTP {exc.code}", stage="llm") from exc
    except urllib.error.URLError as exc:
        raise ScenarioCompileError(f"模型接口连接失败：{exc.reason}", stage="llm") from exc
    except TimeoutError as exc:
        raise ScenarioCompileError(f"模型接口超时（{timeout}s）", stage="llm") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ScenarioCompileError("模型接口返回内容不是合法 JSON", stage="llm") from exc
    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ScenarioCompileError("模型接口返回结构不符预期", stage="llm") from exc


def _load_prompt() -> str:
    if not PROMPT_PATH.is_file():
        raise ScenarioCompileError(f"缺少提示词文件：{PROMPT_PATH}", stage="prompt")
    return PROMPT_PATH.read_text(encoding="utf-8-sig")


def _build_messages(topic: str, mode: str, facts: Any) -> list[dict[str, str]]:
    payload: dict[str, Any] = {"topic": topic, "mode": mode}
    if facts:
        payload["facts"] = facts
    return [
        {"role": "system", "content": _load_prompt()},
        {
            "role": "user",
            "content": "请按系统提示中的格式与约束，编译下面这个议题：\n"
            + json.dumps(payload, ensure_ascii=False, indent=2),
        },
    ]


def _repair_message(schema_problems: list[str], business_problems: list[Problem]) -> str:
    lines = ["上面这份 JSON 没通过校验，请只修改下列位置，其余内容与字段顺序保持不变，重新输出完整 JSON："]
    if schema_problems:
        lines.append("\n【结构问题】")
        lines.extend(f"- {item}" for item in schema_problems)
    if business_problems:
        lines.append("\n【业务规则问题】")
        lines.extend(f"- [{problem.code}] {problem.path}：{problem.message}" for problem in business_problems)
    lines.append("\n只输出 JSON，不要解释，不要代码围栏。")
    return "\n".join(lines)



def compile_from_narrowing(
    topic: str,
    suggestion: str,
    mode: str = "auto",
    facts: Any = None,
    max_retry: int = 2,
    llm: Callable[[list[dict[str, str]]], str] | None = None,
) -> CompileResult:
    """多边议题按「收窄方向」编译成双边场景。

    两步走，对应手册 4.1「需要补充或收窄」这一档：
      1. 原议题是 needs_narrowing 时，用 suggestion 作为新议题重新编译
      2. 生成成功后补一条 assumption，写明「本场景为多边议题的双边简化」

    原议题本来就通过时，退化为普通 compile_scenario。
    """
    check = negotiability_module.check(topic, facts)
    if check.get("verdict") != "needs_narrowing":
        return compile_scenario(topic, mode=mode, facts=facts, max_retry=max_retry, llm=llm)

    narrowed = (suggestion or "").strip()
    if not narrowed:
        raise ScenarioCompileError("收窄方向不能为空", stage="parse")

    result = compile_scenario(narrowed, mode=mode, facts=facts, max_retry=max_retry, llm=llm)
    if result.scenario is None:
        return result

    scenario = result.scenario
    scenario.assumptions.append(
        Assumption(
            assumption_id=f"A_narrow_{len(scenario.assumptions) + 1}",
            text=f"本场景为「{topic}」的双边简化，仅保留最具交换结构的两个主体。",
            reason="原议题涉及三方及以上，本轮范围冻结为双边谈判，多边重构不在范围内。",
            affects=[issue.issue_id for issue in scenario.issues],
        )
    )
    problems = validate_scenario(scenario)
    if problems:
        raise ScenarioCompileError(
            "收窄后补写假设导致校验失败",
            stage="validate",
            last_issues=problems,
            raw_output=result.raw_output,
        )

    result.negotiability = {
        **result.negotiability,
        "narrowed_from": topic,
        "narrowing": narrowed,
    }
    return result

def compile_scenario(
    topic: str,
    mode: str = "auto",
    facts: Any = None,
    max_retry: int = 2,
    llm: Callable[[list[dict[str, str]]], str] | None = None,
) -> CompileResult:
    """把议题编译成 Scenario。

    mode="auto" 时先跑可谈判性规则层：
      · unsupported / needs_narrowing → 直接返回，且**不调用模型**
      · pending（规则层未命中）→ 继续编译
    """
    started = time.perf_counter()
    if not isinstance(topic, str) or not topic.strip():
        raise ScenarioCompileError("议题不能为空", stage="parse")
    topic = topic.strip()

    logger.info("compile_scenario start topic=%r mode=%s", topic, mode)

    check = negotiability_module.check(topic, facts)
    if check.get("verdict") in ("unsupported", "needs_narrowing"):
        logger.info(
            "compile_scenario blocked verdict=%s elapsed_ms=%d",
            check.get("verdict"),
            int((time.perf_counter() - started) * 1000),
        )
        return CompileResult(scenario=None, negotiability=check, attempts=0)

    caller = llm or default_llm
    messages = _build_messages(topic, mode, facts)
    schema_problems: list[str] = []
    business_problems: list[Problem] = []
    raw_output: str | None = None

    for attempt in range(max_retry + 1):
        attempt_started = time.perf_counter()
        try:
            raw_output = caller(messages)
        except ScenarioCompileError:
            raise
        except Exception as exc:
            raise ScenarioCompileError(
                f"模型调用失败：{type(exc).__name__}: {exc}",
                stage="llm",
            ) from exc
        call_ms = int((time.perf_counter() - attempt_started) * 1000)

        try:
            data = parse_scenario_json(raw_output)
        except ScenarioCompileError as exc:
            logger.warning(
                "compile_scenario attempt=%d stage=%s elapsed_ms=%d",
                attempt + 1,
                exc.stage,
                call_ms,
            )
            raise

        schema_problems = schema_messages(data)
        if schema_problems:
            logger.info(
                "compile_scenario attempt=%d elapsed_ms=%d schema_problems=%d",
                attempt + 1,
                call_ms,
                len(schema_problems),
            )
            business_problems = []
            messages = messages + [
                {"role": "assistant", "content": raw_output},
                {"role": "user", "content": _repair_message(schema_problems, business_problems)},
            ]
            continue

        business_problems = validate_scenario(data)
        if business_problems:
            logger.info(
                "compile_scenario attempt=%d elapsed_ms=%d codes=%s",
                attempt + 1,
                call_ms,
                sorted({problem.code for problem in business_problems}),
            )
            messages = messages + [
                {"role": "assistant", "content": raw_output},
                {"role": "user", "content": _repair_message(schema_problems, business_problems)},
            ]
            continue

        scenario = Scenario.from_dict(data)
        if scenario.negotiability is not None:
            scenario.negotiability.verdict = "direct"
        logger.info(
            "compile_scenario ok attempts=%d elapsed_ms=%d",
            attempt + 1,
            int((time.perf_counter() - started) * 1000),
        )
        return CompileResult(
            scenario=scenario,
            negotiability={**check, "verdict": "direct"},
            attempts=attempt + 1,
            raw_output=raw_output,
        )

    logger.warning(
        "compile_scenario failed attempts=%d codes=%s elapsed_ms=%d",
        max_retry + 1,
        sorted({problem.code for problem in business_problems}),
        int((time.perf_counter() - started) * 1000),
    )
    raise ScenarioCompileError(
        f"连续 {max_retry + 1} 次编译失败",
        stage="validate" if not schema_problems else "schema",
        last_issues=business_problems,
        raw_output=raw_output,
    )
