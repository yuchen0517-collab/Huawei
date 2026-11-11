"""议题可谈判性检查（规则层）。

实现 U1-U4 四条硬规则，未命中任何规则时返回 pending，交由下一步模型判定。
本版不调用模型、不联网，仅使用标准库正则。
"""
from __future__ import annotations

import re
from typing import Any

U1_YES_NO_PATTERNS = (
    re.compile(r"是否"),
    re.compile(r"谁对谁错|谁是谁非|谁对|谁错"),
    re.compile(r"谁违反|违反了什么|谁违规|谁在违规"),
    re.compile(r"责任在谁|责任归谁|谁的责任|谁负责|谁(该|应当|应该)(为.{0,20})?(负|承担).{0,6}责任"),
)

U1_ADJUSTABLE_PATTERN = re.compile(
    r"\d|%|％|比例|百分比|税率|关税|金额|美元|欧元|亿元|万元|配额|额度|上限|下限|选项|方案|哪种|几种"
    r"|机制|程序|流程|频次|级别|范围|渠道|清单|时限|周期|场次|议程|热线|联络"
)

U2_PATTERNS = (
    re.compile(r"会不会|能否(获胜|胜出|赢|当选)"),
    re.compile(r"结果(会|将)?(如何|怎样|怎么样)|最终结果|结局如何"),
    re.compile(r"谁将(获胜|胜出|赢)|谁(会)?(获胜|胜出|当选|赢)"),
    re.compile(r"明年(会|将)?(怎样|如何|怎么样)|明年.{0,6}(走势|结果)"),
)

U3_PATTERNS = (
    re.compile(r"隐私|私生活|绯闻|出轨|婚外情"),
    re.compile(r"名誉|诽谤|抹黑|人身攻击|造谣"),
    re.compile(r"人品|私德|道德品质"),
    re.compile(r"(收入|病历|家庭|子女).{0,6}(情况|细节)"),
)

U3_INSTITUTIONAL_PATTERN = re.compile(r"数据|信息|保护|合规|制度|立法|跨境|流动")

_COMMON_SURNAMES = (
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜谢邹苏潘葛范彭鲁韦马苗方俞任袁柳唐薛雷贺"
    "倪汤罗毕郝安常于傅齐康伍余顾孟黄萧尹姚邵汪毛戴宋庞熊董梁杜阮蓝闵席季强贾路江童颜郭梅盛林钟徐邱骆高夏蔡田"
    "樊胡凌霍虞万卢莫房裘解应丁邓单杭洪包左石崔吉龚程邢裴陆荣翁荀羊惠甄曲封储靳段富巫乌焦巴弓牧山谷车侯全班"
    "秋仲伊宫宁仇甘厉祖武符刘景詹龙叶黎白怀蒲鄂索咸赖卓蔺屠蒙池乔闻党翟谭姬申冉雍桑桂牛寿通边燕浦尚温庄晏柴"
    "瞿阎慕连茹艾容向古易慎戈廖庾居衡步都耿满弘匡寇广禄东欧沃利蔚越隆师巩聂融冷辛那简饶曾沙鞠丰巢关查红游权"
)

U3_PERSON_PATTERNS = (
    re.compile(r"某(?:国)?(?:领导|总统|主席|总理|部长|首相|外长|议员|官员|企业家|明星|校长|院长|法官|检察官)"),
    re.compile(r"(?:总统|总理|部长|主席|首相|外长|议员|官员)(?:[\u4e00-\u9fa5]{2,4}|他|她)"),
    re.compile(
        rf"[{_COMMON_SURNAMES}][\u4e00-\u9fa5]{{1,3}}"
        r"(?=的|，|。|、|；|：|？|！|,|\s|$|总统|总理|部长|主席|首相|外长|议员|官员)"
    ),
)

U4_PATTERNS = (
    re.compile(r"[三四五六七八九十]\s*(国|方|边)"),
    re.compile(r"(?<!\d)(\d{1,2})\s*(国|方|边)"),
    re.compile(r"多方|多国|各方|多边|三方以上|三国以上"),
)

VERDICTS = {
    "U1": "unsupported",
    "U2": "unsupported",
    "U3": "unsupported",
    "U4": "needs_narrowing",
}

U1_SUGGESTIONS = [
    "把是非判断改为「各方分别承担多少比例的份额」",
    "把「谁对谁错」改为「设定三档处理方案并逐项比较」",
]

U2_SUGGESTIONS = [
    "改为「假设推演」模式，把它当成教学情境来谈",
    "把「结果会怎样」改为「在两种情景下各自的应对方案」",
]

U3_SUGGESTIONS = [
    "移除对具体个人的评价，改为讨论制度或政策安排",
    "把隐私或名誉议题替换为「相关行业的合规标准如何设定」",
]

U4_GENERIC_SUGGESTIONS = [
    "收窄为双边谈判：只保留最主要的两个当事方",
    "按议题拆分：每轮只谈一个具体分配项",
    "先谈程序性安排（议程、时限、表决方式），再谈实质分配",
]

U4_CHIP_SUGGESTIONS = [
    "聚焦中美之间的芯片许可审批时限",
    "聚焦关键矿产配额与芯片许可的交换",
    "先把第三方转口限制从议题中剥离",
]

U4_TAX_SUGGESTIONS = [
    "先收窄为中美欧三方数字服务税税率差",
    "把全球最低税率与单边数字税拆成两轮谈",
    "先谈数字税抵扣规则，再谈税率",
]

U4_WATER_SUGGESTIONS = [
    "先收窄为上下游两国年度取水量",
    "把生态补偿金额与水量分配拆开谈",
    "先谈监测与数据共享机制",
]

PENDING_SUGGESTIONS = [
    "直接进入下一步模型判定：按当前议题生成 2-3 个具体选项后再复核",
]


def _first_keyword(text: str, patterns: tuple[re.Pattern[str], ...]) -> str | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match is not None:
            return match.group(0)
    return None


def _match_u1(text: str) -> tuple[str, str, list[str]] | None:
    keyword = _first_keyword(text, U1_YES_NO_PATTERNS)
    if keyword is None:
        return None
    if U1_ADJUSTABLE_PATTERN.search(text):
        return None
    reason = f"命中 U1：单一二元是非题（关键词「{keyword}」），且不含可调数值、金额、比例或可选项"
    return keyword, reason, list(U1_SUGGESTIONS)


def _match_u2(text: str) -> tuple[str, str, list[str]] | None:
    keyword = _first_keyword(text, U2_PATTERNS)
    if keyword is None:
        return None
    reason = f"命中 U2：要求预测尚未发生的现实事件（关键词「{keyword}」）"
    return keyword, reason, list(U2_SUGGESTIONS)


def _match_u3(text: str) -> tuple[str, str, list[str]] | None:
    keyword = _first_keyword(text, U3_PATTERNS)
    if keyword is None:
        return None
    if _first_keyword(text, U3_PERSON_PATTERNS) is None:
        return None
    if U3_INSTITUTIONAL_PATTERN.search(text):
        return None
    reason = f"命中 U3：涉及具体个人的隐私或名誉评价（关键词「{keyword}」）"
    return keyword, reason, list(U3_SUGGESTIONS)


def _u4_suggestions(text: str) -> list[str]:
    if re.search(r"芯片|半导体|先进计算", text):
        return list(U4_CHIP_SUGGESTIONS)
    if re.search(r"数字税|数字服务税", text):
        return list(U4_TAX_SUGGESTIONS)
    if re.search(r"河流|水量|水权|跨境水", text):
        return list(U4_WATER_SUGGESTIONS)
    return list(U4_GENERIC_SUGGESTIONS)


def _match_u4(text: str) -> tuple[str, str, list[str]] | None:
    for pattern in U4_PATTERNS:
        for match in pattern.finditer(text):
            numeric = match.group(1)
            if numeric is not None and numeric.isdigit() and int(numeric) < 3:
                continue
            keyword = match.group(0)
            reason = f"命中 U4：涉及 3 方及以上同时谈判（关键词「{keyword}」）"
            return keyword, reason, _u4_suggestions(text)
    return None


_MATCHERS = (
    ("U1", _match_u1),
    ("U2", _match_u2),
    ("U3", _match_u3),
    ("U4", _match_u4),
)


def check(topic: str, facts: Any = None) -> dict[str, Any]:
    text = topic if isinstance(topic, str) else ""
    text = text.strip()
    for rule_id, matcher in _MATCHERS:
        matched = matcher(text)
        if matched is None:
            continue
        _keyword, reason, suggestions = matched
        return {
            "verdict": VERDICTS[rule_id],
            "reasons": [reason],
            "suggestions": suggestions,
            "matched_rules": [rule_id],
        }
    return {
        "verdict": "pending",
        "reasons": ["规则层 U1-U4 均未命中，交由下一步模型判定"],
        "suggestions": list(PENDING_SUGGESTIONS),
        "matched_rules": [],
    }