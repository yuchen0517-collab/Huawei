"""在头脑风暴纪要末尾追加第十二章（决议与契约 v2），并就地修订三处误导性表述。

修订原则：不重写 11 月 10 日的讨论原貌，只做两件事——
1. 把已经拍板的决议、卡表、参数、对前文的修订集中写进新增的第十二章；
2. 对"照着做会做错"的地方（5.3 的最后报价归类、5.5 的示例边界、1.2 的修法）
   就地加注，避免团队按旧表述实现。

格式一律克隆文档内已有段落/表格，保证字体、字号、缩进与全文一致。
"""

from __future__ import annotations

import copy
import shutil
from datetime import date
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.shared import Pt
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

SRC = Path(r"D:\RainbowKATE\大学研究生时\华为杯\外交谈判智能体升级改造头脑风暴纪要.docx")
BACKUP = SRC.with_name(f"{SRC.stem}_2026-11-10.docx")


# ----------------------------------------------------------------------
# 基础工具
# ----------------------------------------------------------------------
def set_run_text(run_el, text: str) -> None:
    for child in list(run_el):
        if child.tag in (qn("w:t"), qn("w:br"), qn("w:tab")):
            run_el.remove(child)
    # 原文用黄色荧光笔标重点（含 7.2 标题这类误标），新内容一律不带，
    # 否则整列/整段高亮会盖住表格与列表的层次。
    rpr = run_el.find(qn("w:rPr"))
    if rpr is not None:
        for tag in ("w:highlight", "w:shd"):
            for node in rpr.findall(qn(tag)):
                rpr.remove(node)
    node = OxmlElement("w:t")
    node.text = text
    node.set(qn("xml:space"), "preserve")
    run_el.append(node)


def strip_mark_highlight(paragraph_el) -> None:
    """项目符号/编号的格式取自段落标记的 rPr；不清掉它，圆点会带荧光笔底色。"""
    ppr = paragraph_el.find(qn("w:pPr"))
    if ppr is None:
        return
    rpr = ppr.find(qn("w:rPr"))
    if rpr is None:
        return
    for tag in ("w:highlight", "w:shd"):
        for node in rpr.findall(qn(tag)):
            rpr.remove(node)


def collapse(paragraph_el, keep: int):
    runs = paragraph_el.findall(qn("w:r"))
    for extra in runs[keep:]:
        paragraph_el.remove(extra)
    return runs[:keep]


def clone_labeled(template_p, label: str, body: str):
    """克隆「粗体标签＋正文」段落。"""
    el = copy.deepcopy(template_p._p)
    runs = collapse(el, 2)
    set_run_text(runs[0], label)
    set_run_text(runs[1], body)
    strip_mark_highlight(el)
    return el


def clone_plain(template_p, text: str):
    el = copy.deepcopy(template_p._p)
    runs = collapse(el, 1)
    set_run_text(runs[0], text)
    strip_mark_highlight(el)
    return el


def clone_heading(template_p, number: str | None, title: str, two_runs: bool, owner):
    el = copy.deepcopy(template_p._p)
    if two_runs:
        runs = collapse(el, 2)
        set_run_text(runs[0], number or "")
        set_run_text(runs[1], title)
    else:
        runs = collapse(el, 1)
        set_run_text(runs[0], title)
    # 标题不与后续表格分页，避免「12.3」孤零零留在页脚。
    Paragraph(el, owner).paragraph_format.keep_with_next = True
    return el


def clone_list_item(template_p, text: str):
    el = copy.deepcopy(template_p._p)
    runs = collapse(el, 1)
    set_run_text(runs[0], text)
    strip_mark_highlight(el)
    return el


def _ensure_keep_next(p_el) -> None:
    ppr = p_el.find(qn("w:pPr"))
    if ppr is None:
        ppr = OxmlElement("w:pPr")
        p_el.insert(0, ppr)
    if ppr.find(qn("w:keepNext")) is not None:
        return
    node = OxmlElement("w:keepNext")
    pstyle = ppr.find(qn("w:pStyle"))
    if pstyle is not None:
        pstyle.addnext(node)
    else:
        ppr.insert(0, node)


def clone_table(template_t, rows):
    tbl = copy.deepcopy(template_t._tbl)
    trs = tbl.findall(qn("w:tr"))
    while len(trs) < len(rows):
        added = copy.deepcopy(trs[-1])
        trs[-1].addnext(added)
        trs = tbl.findall(qn("w:tr"))
    while len(trs) > len(rows):
        tbl.remove(trs[-1])
        trs = tbl.findall(qn("w:tr"))

    for tr, values in zip(trs, rows):
        cells = tr.findall(qn("w:tc"))
        for tc, value in zip(cells, values):
            paragraphs = tc.findall(qn("w:p"))
            for extra in paragraphs[1:]:
                tc.remove(extra)
            para = paragraphs[0]
            runs = para.findall(qn("w:r"))
            set_run_text(runs[0], value)
            for extra in runs[1:]:
                para.remove(extra)
    # 短表整块不跨页：除最后一行外，行内段落都"与下段同页"。
    for tr in trs[:-1]:
        for tc in tr.findall(qn("w:tc")):
            for para in tc.findall(qn("w:p")):
                _ensure_keep_next(para)
    return tbl


def _tidy_note(paragraph_el, owner) -> None:
    """插入的批注段落：段前留白、不跨页。"""
    para = Paragraph(paragraph_el, owner)
    para.paragraph_format.keep_together = True
    para.paragraph_format.space_before = Pt(10)


def find_paragraph(doc, prefix: str):
    for p in doc.paragraphs:
        if p.text.startswith(prefix):
            return p
    raise LookupError(prefix)


def find_table(doc, header: str):
    for t in doc.tables:
        if t.rows and t.rows[0].cells[0].text.strip() == header:
            return t
    raise LookupError(header)


# ----------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------
def restart_numbering(doc, start_text: str, end_text: str) -> None:
    """让指定区间内的列表重新从 1 编号（原文 11.2 被前面的编号列表带成了 12-16）。"""
    numbering = doc.part.numbering_part.element

    def numid_of(para):
        ppr = para._p.find(qn("w:pPr"))
        numpr = ppr.find(qn("w:numPr")) if ppr is not None else None
        numid = numpr.find(qn("w:numId")) if numpr is not None else None
        return None if numid is None else numid.get(qn("w:val"))

    # 先圈出区间，再取区间内真正使用的 numId 作为模板。
    section = []
    inside = False
    for para in doc.paragraphs:
        if para.text.startswith(start_text):
            inside = True
        elif para.text.startswith(end_text):
            inside = False
        if inside:
            section.append(para)

    target = None
    for para in section:
        value = numid_of(para)
        if value not in (None, "0"):
            target = int(value)
            break
    if target is None:
        return

    abstract_id = None
    for num in numbering.findall(qn("w:num")):
        if int(num.get(qn("w:numId"))) == target:
            abstract_id = num.find(qn("w:abstractNumId")).get(qn("w:val"))
    if abstract_id is None:
        return

    ids = [int(num.get(qn("w:numId"))) for num in numbering.findall(qn("w:num"))]
    new_id = max(ids) + 1
    num_el = OxmlElement("w:num")
    num_el.set(qn("w:numId"), str(new_id))
    an = OxmlElement("w:abstractNumId")
    an.set(qn("w:val"), str(abstract_id))
    num_el.append(an)
    override = OxmlElement("w:lvlOverride")
    override.set(qn("w:ilvl"), "0")
    start = OxmlElement("w:startOverride")
    start.set(qn("w:val"), "1")
    override.append(start)
    num_el.append(override)
    numbering.append(num_el)

    for para in section:
        ppr = para._p.find(qn("w:pPr"))
        numpr = ppr.find(qn("w:numPr")) if ppr is not None else None
        numid = numpr.find(qn("w:numId")) if numpr is not None else None
        if numid is not None:
            numid.set(qn("w:val"), str(new_id))


def main() -> None:
    if not BACKUP.exists():
        shutil.copy2(SRC, BACKUP)
        print(f"备份：{BACKUP.name}")

    doc = Document(SRC)

    h1_tpl = find_paragraph(doc, "十一、")
    h2_tpl = find_paragraph(doc, "11.1")
    label_tpl = find_paragraph(doc, "一句话结论")
    plain_tpl = find_paragraph(doc, "Agent 的行动应具体说明")
    list_tpl = next(p for p in doc.paragraphs if p.style.name == "List Paragraph")

    tbl_decisions = find_table(doc, "待确认问题")          # 3 列 9 行
    tbl_cards = find_table(doc, "组件")                     # 3 列 7 行
    tbl_revisions = find_table(doc, "子议题示例")            # 3 列 4 行
    tbl_params = find_table(doc, "终局状态")                 # 2 列 6 行

    body = doc.element.body
    sect_pr = body.find(qn("w:sectPr"))

    def append(element):
        sect_pr.addprevious(element)

    # ---------------- 就地修订 1：5.5 示例的适用范围 ----------------
    p_55 = find_paragraph(doc, "用户操作")
    note_55 = clone_labeled(
        label_tpl,
        "适用范围\u3000",
        "上例属于报价塑造类。信息试探、进程控制、立场表态三类卡牌打完即结束回合，"
        "不产生报价；只有报价塑造、条款控制、终局三类必须提交条款变更（见 §12.2、§12.3）。",
    )
    _tidy_note(note_55, doc._body)
    p_55._p.addnext(note_55)

    # ---------------- 就地修订 2：5.3 卡表里的「最后报价」------------
    tbl_53 = find_table(doc, "卡牌类型")
    for row in tbl_53.rows:
        if row.cells[0].text.strip() == "进程控制":
            cell = row.cells[1]
            runs = cell.paragraphs[0].runs
            runs[0].text = "暂时休会、请求调解"
            for extra in runs[1:]:
                extra._element.getparent().remove(extra._element)
    note_53 = clone_labeled(
        label_tpl,
        "修订\u3000",
        "最后报价已从进程控制移出，改属报价类，必须走报价板（见 §12.3）。",
    )
    _tidy_note(note_53, doc._body)
    tbl_53._tbl.addnext(note_53)

    # ---------------- 就地修订 3：1.2 的修法建议 ----------------
    p_12 = find_paragraph(doc, "一个需要立即修正的规则")
    tail_run = copy.deepcopy(p_12.runs[-1]._element)
    set_run_text(tail_run, "（11 月 16 日已改为响应闭包：见 §12.4。）")
    p_12._p.append(tail_run)

    # ---------------- 就地修订 4：11.1 待确认表 ----------------
    tbl_confirm = find_table(doc, "待确认问题")
    for row in tbl_confirm.rows:
        if row.cells[0].text.strip() == "卡牌与报价板谁是主交互？":
            cell = row.cells[1]
            runs = cell.paragraphs[0].runs
            runs[0].text = "已定：报价板为中心，卡牌作策略层与限制层（§12.2）"
            for extra in runs[1:]:
                extra._element.getparent().remove(extra._element)

    # ---------------- 第十二章 ----------------
    append(clone_heading(h1_tpl, None, "十二、决议与契约 v2（2026-11-16 追加）", False, doc._body))

    append(
        clone_plain(
            plain_tpl,
            "性质\u3000前十一章保留 11 月 10 日讨论原貌，本章记录其后已经拍板的决议、"
            "对前文的三处修订，以及已落地的实现。文中「已定」指团队已经确认，"
            "不再作为待确认事项。目录页码需在 Word/WPS 中右键目录并选择「更新域」后刷新。",
        )
    )

    # 12.1
    append(clone_heading(h2_tpl, "12.1 ", "八项已拍板决议", True, doc._body))
    append(
        clone_table(
            tbl_decisions,
            [
                ["议题", "决议", "影响"],
                ["卡牌与报价的关系", "卡牌是行动，报价是行动在条款表上留下的新版本；不设「出牌」与「报价」两种并列回合", "行动入口只有一个，版本只由条款变更推进"],
                ["什么牌必须走报价板", "产出要写进协议对象的牌才走报价板", "卡牌分成两类，见 §12.2"],
                ["过渡额度", "对方报价后允许 1 次不表态的过渡行动", "第 2 次必须接受、拒绝或反报价"],
                ["探询的应答", "可被拒绝或虚报，并计入信任度", "探询不再是免费信息"],
                ["卡牌资源", "常驻持有、不抽牌，用后进冷却", "消除运气因素，训练可复现"],
                ["维持原报价", "算一次行动，但不得连续重复", "堵住零成本拖延"],
                ["行动点", "每回合 4；子议题 4 项及以上时 5", "容纳三步闭环并留余量"],
                ["僵局阈值", "连续 3 轮没有新版本判僵局", "放开过渡牌后不再误杀正常试探"],
            ],
        )
    )

    # 12.2
    append(clone_heading(h2_tpl, "12.2 ", "判定法则：什么时候必须走报价板", True, doc._body))
    append(
        clone_labeled(
            label_tpl,
            "判定法则\u3000",
            "一张牌必须走报价板，当且仅当它的产出要写进协议对象（条款表、附加条件或终局标志）。",
        )
    )
    append(
        clone_plain(
            plain_tpl,
            "理由\u3000凡进入协议对象的东西，都必须版本化、可比较、可被「接受」指认；"
            "凡不进入协议对象的东西，就不该产生版本。因此「有时候不需要提交报价」"
            "不是省略了一个动作，而是这张牌本来就没有条款可交——探询产出信息，"
            "休会改变程序，承诺进入承诺账本，三者都不改变协议。",
        )
    )

    append(
        clone_labeled(
            label_tpl,
            "一句话结论\u3000",
            "这一版把「怎么谈」与「谈成什么」分开：卡牌约束你能做什么，条款版本记录你谈成了什么；"
            "报价不再是另一种输入，而是行动留下的痕迹。",
        )
    )

    # 12.3
    append(clone_heading(h2_tpl, "12.3 ", "卡牌分类：两张清单", True, doc._body))
    append(
        clone_table(
            tbl_cards,
            [
                ["族", "包含卡牌", "是否走报价板"],
                ["报价塑造", "锚定报价、条件让步、议题捆绑、分拆议题", "是"],
                ["条款控制", "附加生效条件、设置履约节点、加入退出条款", "是（写成结构化条款）"],
                ["终局", "最后报价", "是"],
                ["信息试探", "探询优先级、要求依据、核查履约能力", "否，产出信息"],
                ["进程控制", "暂时休会、请求调解", "否，改变程序"],
                ["立场表态", "公开承诺", "否，进入承诺账本"],
                ["基础行动", "报价、反报价、条件交换、接受、拒绝、维持原报价、宣布退出", "报价类走板，其余不产生版本"],
            ],
        )
    )
    append(
        clone_plain(
            plain_tpl,
            "补充\u3000条款控制类不再写入自由文本条件。场景需要声明 clause_roles，"
            "把「生效条件」「履约核查节点」「退出条款」做成带预置选项的条款；"
            "只有枚举化的条款才能判断双方是否接受了同一内容。",
        )
    )

    # 12.4
    append(clone_heading(h2_tpl, "12.4 ", "响应闭包：取代「必须反报价」", True, doc._body))
    for text in (
        "任一方提交新版本，就为对方开一个待表态窗口，窗口只保留最新版本。",
        "响应方有 1 次过渡机会（信息、程序、立场三类牌）；第 2 次必须落在接受、拒绝、反报价或最后报价上。",
        "对方尚未表态前，报价方不得自行改版，否则待表态窗口永远关不上。",
        "接受与拒绝都能解除窗口；拒绝后不得连续重复维持原报价，否则视为空转。",
    ):
        append(clone_list_item(list_tpl, text))

    # 12.5
    append(clone_heading(h2_tpl, "12.5 ", "参数与冷却定稿", True, doc._body))
    append(
        clone_table(
            tbl_params,
            [
                ["参数", "定稿值"],
                ["每回合行动点", "4；子议题 4 项及以上时 5"],
                ["僵局阈值", "连续 3 轮没有新版本（原为 2 轮，口径改为双方该轮均未产生新版本）"],
                ["过渡额度", "每个版本 1 次"],
                ["报价塑造、条款控制、立场表态", "冷却 1 回合（用后下一回合不可再用，第 3 回合恢复）"],
                ["信息试探", "冷却 2 回合；核查履约能力 3 回合"],
                ["程序类与最后报价", "每局 1 次"],
            ],
        )
    )

    # 12.6
    append(clone_heading(h2_tpl, "12.6 ", "对前文的修订", True, doc._body))
    append(
        clone_table(
            tbl_revisions,
            [
                ["章节", "原文表述", "修订"],
                ["§1.2", "建议把「任何提议均需主动提出反方案」改为「不得无依据接受或拒绝……」", "已按 §12.4 的响应闭包落地：1 次过渡后必须表态"],
                ["§5.3", "进程控制一栏含「最后报价」", "最后报价属报价类，必须走报价板；进程控制只留休会与调解"],
                ["§5.5", "示例读起来像每张牌都要提交反报价", "只有报价塑造、条款控制、终局三类需提交；其余打完即结束回合"],
                ["§11.1", "「卡牌与报价板谁是主交互」列为待确认", "已定：报价板为中心，卡牌作策略层与限制层"],
            ],
        )
    )

    # 12.7
    append(clone_heading(h2_tpl, "12.7 ", "已落地与未尽事项", True, doc._body))
    for text in (
        "已产出：card_registry.json（14 张牌与 6 个基础行动的族、冷却、载荷）、"
        "negotiation_rules.py（报价板法则、响应闭包、推进不变量的校验）、"
        "action_schema_v2.json、test_negotiation_rules.py（19 条用例跑在真实引擎上）。",
        "两个现存漏洞：一是空 patch 的报价会被接受，能无限重置僵局计时；"
        "二是 conditions 不随版本累积、接受时不校验，导致「谈成了但协议内容不一致」。"
        "前者已由契约层关闭，后者随条件枚举化消失。",
        "未尽事项：信息集与承诺账本还没有存储，探询仍不产出实际信息；"
        "虚报被证实后的信任度扣减也未接入。这是下一轮要补的闭环。",
    ):
        append(clone_list_item(list_tpl, text))

    restart_numbering(doc, "11.2 建议下一步", "11.3 本文资料依据")

    doc.save(SRC)

    # ---------------- 校验 ----------------
    check = Document(SRC)
    headings = [p.text for p in check.paragraphs if p.style.name == "Heading 1"]
    print("章：", headings)
    print("表数：", len(check.tables))
    for label in ("12.1 ", "12.2 ", "12.3 ", "12.4 ", "12.5 ", "12.6 ", "12.7 "):
        hit = [p.text for p in check.paragraphs if p.text.startswith(label)]
        print(label, "->", hit[0] if hit else "缺失")
    print("5.3 进程控制：", [
        row.cells[1].text for row in find_table(check, "卡牌类型").rows
        if row.cells[0].text.strip() == "进程控制"
    ])
    print("11.1 主交互：", [
        row.cells[1].text for row in find_table(check, "待确认问题").rows
        if row.cells[0].text.strip().startswith("卡牌与报价板")
    ])


if __name__ == "__main__":
    main()
