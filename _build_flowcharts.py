"""生成谈判部分流程图（PPTX，便于修改；再转 PNG）。

三张图对应契约 v2：
1. 单局主循环：回合内的行动、校验、结算与终局判定
2. 待表态窗口：响应闭包状态机
3. 终局判定：五态级联（按 engine/terminal.py 的优先级）

坐标一律用英寸；画布 13.333 x 7.5（16:9）。
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

OUT = Path(__file__).resolve().parent / "figs"
OUT.mkdir(exist_ok=True)
PPTX = OUT / "谈判流程图.pptx"

TEAL = RGBColor(0x11, 0x42, 0x4C)
TEAL2 = RGBColor(0x2E, 0x6E, 0x78)
LIGHT = RGBColor(0xEA, 0xF3, 0xF3)
ORANGE = RGBColor(0xC0, 0x56, 0x2A)
ORANGE_BG = RGBColor(0xFB, 0xED, 0xE4)
RED = RGBColor(0xA3, 0x3A, 0x2E)
RED_BG = RGBColor(0xFB, 0xEC, 0xEA)
GRAY = RGBColor(0x5B, 0x6B, 0x6E)
DARK = RGBColor(0x24, 0x33, 0x3B)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LINE = RGBColor(0xB9, 0xCF, 0xCF)

FONT = "微软雅黑"


def _font(run, size=None, bold=None, color=None):
    run.font.name = FONT
    rpr = run._r.get_or_add_rPr()
    ea = rpr.find(qn("a:ea"))
    if ea is None:
        ea = rpr.makeelement(qn("a:ea"), {})
        rpr.append(ea)
    ea.set("typeface", FONT)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color


def textbox(slide, x, y, w, h, lines, *, size=10, color=DARK, bold=False,
            align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.02)
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    for index, item in enumerate(lines):
        para = tf.paragraphs[0] if index == 0 else tf.add_paragraph()
        para.alignment = align
        run = para.add_run()
        run.text = item
        _font(run, size, bold, color)
    return box


def box(slide, x, y, w, h, title, body=(), *, kind="proc",
        title_size=11.5, body_size=9, thick=False):
    shape_type = {
        "decision": MSO_SHAPE.DIAMOND,
        "start": MSO_SHAPE.ROUNDED_RECTANGLE,
        "term": MSO_SHAPE.ROUNDED_RECTANGLE,
    }.get(kind, MSO_SHAPE.ROUNDED_RECTANGLE)
    shape = slide.shapes.add_shape(shape_type, Inches(x), Inches(y), Inches(w), Inches(h))
    if shape_type == MSO_SHAPE.ROUNDED_RECTANGLE:
        shape.adjustments[0] = 0.12
    shape.shadow.inherit = False

    style = {
        "proc": (WHITE, TEAL, TEAL, GRAY),
        "start": (LIGHT, TEAL2, TEAL, GRAY),
        "decision": (ORANGE_BG, ORANGE, ORANGE, DARK),
        "term": (TEAL, TEAL, WHITE, RGBColor(0xD8, 0xE8, 0xE8)),
        "muted": (RGBColor(0xF4, 0xF7, 0xF7), LINE, GRAY, GRAY),
        "error": (RED_BG, RED, RED, RED),
    }[kind]
    fill, border, title_color, body_color = style
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = border
    shape.line.width = Pt(1.6 if thick else 1.1)

    tf = shape.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.07)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE

    para = tf.paragraphs[0]
    para.alignment = PP_ALIGN.CENTER
    run = para.add_run()
    run.text = title
    _font(run, title_size if kind != "decision" else 10.5, True, title_color)

    for line in body:
        para = tf.add_paragraph()
        para.alignment = PP_ALIGN.CENTER
        run = para.add_run()
        run.text = line
        _font(run, body_size, False, body_color)
    return shape


def polyline(slide, points, color=TEAL2, *, dashed=False, arrow=True, width=1.1):
    for index in range(len(points) - 1):
        (x1, y1), (x2, y2) = points[index], points[index + 1]
        conn = slide.shapes.add_connector(
            MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2)
        )
        conn.line.color.rgb = color
        conn.line.width = Pt(width)
        if dashed:
            conn.line.dash_style = MSO_LINE_DASH_STYLE.DASH
        if arrow and index == len(points) - 2:
            ln = conn.line._get_or_add_ln()
            tail = ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
            ln.append(tail)


def title_block(slide, title, fig_no):
    textbox(slide, 0.55, 0.26, 10.4, 0.5, [title], size=21, color=TEAL, bold=True)
    textbox(slide, 11.2, 0.34, 1.6, 0.34, [fig_no], size=14, color=TEAL2, bold=True,
            align=PP_ALIGN.RIGHT)
    line = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT, Inches(0.55), Inches(0.86), Inches(12.78), Inches(0.86)
    )
    line.line.color.rgb = ORANGE
    line.line.width = Pt(1.4)


# ----------------------------------------------------------------------
# 图 1：单局主循环
# ----------------------------------------------------------------------
def slide_main_loop(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    title_block(slide, "图 1　单局主循环：一次行动如何被校验、结算与判定", "12-1")

    x0, w = 4.96, 3.40
    center = x0 + w / 2

    box(slide, x0, 0.98, w, 0.46, "开局 · 场景确认",
        ["条款表 V0 ／ 每回合 4 个行动点 ／ 牌组常驻，不抽牌"], kind="start")
    box(slide, x0, 1.60, w, 0.48, "行动入口",
        ["选一张牌或基础动作，填写载荷"], kind="proc")

    check = box(slide, x0, 2.24, w, 0.92, "契约层校验（negotiation_rules）", (), kind="proc")
    tf = check.text_frame
    for line in ("卡牌归属 · 冷却 · 限次",
                 "载荷白名单：探询目标 / 程序项 / 承诺文本",
                 "推进不变量：不许空转回合",
                 "响应闭包：过渡额度 1 次"):
        para = tf.add_paragraph()
        para.alignment = PP_ALIGN.LEFT
        run = para.add_run()
        run.text = "· " + line
        _font(run, 8.5, False, GRAY)

    box(slide, x0 + 0.30, 3.32, w - 0.60, 0.86, "产生新版本？", kind="decision")

    box(slide, 0.80, 3.31, 3.55, 0.88,
        "信息 / 程序 / 承诺",
        ["产出：信息集 · 程序状态 · 承诺账本", "不产生版本，不修改条款"], kind="muted")
    box(slide, 8.88, 3.31, 3.50, 0.88,
        "报价板",
        ["改条款 / 附条件 / 宣布最后报价", "产出：新版本 V+1"], kind="proc", thick=True)

    box(slide, x0, 4.32, w, 0.50, "引擎结算",
        ["红线 · 条款合法 · 扣行动点 → 写公开事件"], kind="proc")
    box(slide, x0, 4.96, w, 0.54, "开待表态窗口",
        ["仅当产生新版本；否则本轮跳过"], kind="proc")
    box(slide, x0 + 0.30, 5.66, w - 0.60, 0.86, "是否终局？", kind="decision")

    box(slide, 0.80, 5.70, 3.55, 0.80,
        "终局五态",
        ["完整协议 · 部分协议 · 主动退出", "僵局 · 回合耗尽（见图 3）"], kind="term")

    polyline(slide, [(center, 1.44), (center, 1.60)])
    polyline(slide, [(center, 2.08), (center, 2.24)])
    polyline(slide, [(center, 3.16), (center, 3.32)])
    polyline(slide, [(center, 4.18), (center, 4.32)])

    # 菱形左右分支
    polyline(slide, [(4.96, 3.75), (4.35, 3.75)])
    polyline(slide, [(8.36, 3.75), (8.88, 3.75)])
    textbox(slide, 4.44, 3.48, 0.50, 0.24, ["否"], size=9, color=GRAY, bold=True)
    textbox(slide, 8.40, 3.48, 0.50, 0.24, ["是"], size=9, color=TEAL, bold=True)

    polyline(slide, [(2.575, 4.19), (2.575, 4.57), (4.96, 4.57)])
    polyline(slide, [(10.63, 4.19), (10.63, 4.57), (8.36, 4.57)])
    polyline(slide, [(center, 4.82), (center, 4.96)])
    polyline(slide, [(center, 5.50), (center, 5.66)])

    # 校验拒绝：回到行动入口
    polyline(slide, [(4.96, 2.70), (4.38, 2.70), (4.38, 1.84), (4.96, 1.84)],
             color=RED, dashed=True)
    textbox(slide, 2.90, 1.74, 1.42, 0.24, ["拒绝 + 原因码"], size=8.5, color=RED)

    # 未终局：回到行动入口
    polyline(slide, [(8.36, 6.09), (12.62, 6.09), (12.62, 1.84), (8.36, 1.84)],
             color=TEAL2, dashed=True)
    textbox(slide, 10.30, 6.15, 2.30, 0.24, ["否 → 下一行动／下一轮"], size=8.5, color=TEAL2)

    polyline(slide, [(4.96, 6.09), (4.35, 6.09)], color=TEAL)
    textbox(slide, 4.42, 5.79, 0.42, 0.24, ["是"], size=9, color=TEAL, bold=True)

    textbox(slide, 0.55, 7.04, 12.2, 0.30,
            ["校验：negotiation_rules.py ｜ 结算与终局：engine/core.py · engine/terminal.py ｜ "
             "参数：行动点 4／5，僵局 3 轮，过渡 1 次"],
            size=8, color=GRAY)
    return slide


# ----------------------------------------------------------------------
# 图 2：待表态窗口状态机
# ----------------------------------------------------------------------
def slide_pending(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    title_block(slide, "图 2　待表态窗口：响应闭包状态机", "12-2")

    box(slide, 0.75, 2.90, 2.55, 0.95, "无挂起窗口", ["任何一方都可以发起行动"], kind="start")
    box(slide, 4.55, 2.90, 3.55, 0.95, "待表态（V_n）", ["响应方 = 报价方以外的另一方"],
        kind="proc", thick=True)
    box(slide, 9.55, 2.90, 3.00, 0.95, "窗口关闭",
        ["可开启下一个窗口", "（反报价即开 V(n+1)）"], kind="muted")

    box(slide, 4.85, 1.48, 2.95, 0.75, "过渡牌 × 1",
        ["信息 / 程序 / 承诺，不表态"], kind="muted")

    polyline(slide, [(3.30, 3.375), (4.55, 3.375)])
    textbox(slide, 3.28, 3.06, 1.24, 0.28, ["提交新版本"], size=8, color=GRAY,
            align=PP_ALIGN.CENTER)

    polyline(slide, [(6.30, 2.90), (6.30, 2.23)], color=TEAL2, dashed=True, width=1.0)
    polyline(slide, [(7.80, 2.23), (7.80, 2.90)], color=TEAL2, dashed=True, width=1.0)

    polyline(slide, [(8.10, 3.375), (9.55, 3.375)])
    textbox(slide, 8.12, 3.05, 1.41, 0.50,
            ["接受 / 拒绝 /", "反报价 / 最后报价"], size=7.5, color=TEAL2,
            align=PP_ALIGN.CENTER)

    box(slide, 0.75, 5.05, 3.50, 0.62, "对方未表态先改版",
        ["SELF_REVISION_LOCKED"], kind="error")
    box(slide, 4.55, 5.05, 3.55, 0.62, "第 2 次过渡",
        ["PENDING_RESPONSE_EXCEEDED"], kind="error")
    box(slide, 9.55, 5.05, 3.00, 0.62, "连续重复维持原报价",
        ["REPEAT_HOLD_FORBIDDEN"], kind="error")

    polyline(slide, [(4.80, 3.85), (4.80, 4.45), (2.50, 4.45), (2.50, 5.05)],
             color=RED, dashed=True, width=1.0)
    polyline(slide, [(6.30, 3.85), (6.30, 5.05)], color=RED, dashed=True, width=1.0)
    polyline(slide, [(11.05, 3.85), (11.05, 5.05)], color=RED, dashed=True, width=1.0)

    textbox(slide, 0.75, 6.10, 5.60, 0.60,
            ["实线 = 合法的状态转移；红色虚线 = 拒绝路径。",
             "拒绝不改变状态，只返回原因码，玩家需重新选牌。"],
            size=8.5, color=GRAY)
    textbox(slide, 6.70, 6.10, 6.05, 0.60,
            ["计时：每轮没有新版本 rounds_without_offer +1；连续 3 轮判僵局（DEADLOCK）。",
             "过渡额度按「每个版本 1 次」重置，换手才重新计数。"],
            size=8.5, color=GRAY)
    return slide


# ----------------------------------------------------------------------
# 图 3：终局判定五态
# ----------------------------------------------------------------------
def slide_terminal(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    title_block(slide, "图 3　终局判定：五态级联（按优先级自上而下）", "12-3")

    rows = [
        ("已有协议且条款齐备？", "完整协议 FULL_AGREEMENT",
         ["必选议题全部覆盖，且各方接受同一版本"]),
        ("已有协议对象？", "部分协议 PARTIAL_AGREEMENT",
         ["仍有未决议题；场景禁止部分协议则判僵局"]),
        ("出现 walk_away？", "主动退出 WITHDRAWAL",
         ["一方正式宣布退出，执行 BATNA"]),
        ("连续 3 轮无新版本？", "僵局 DEADLOCK",
         ["没有新报价，也没有实质推进"]),
        ("超过最大轮次？", "回合耗尽 ROUNDS_EXHAUSTED",
         ["期限到达但未形成有效协议"]),
    ]

    top, step, height = 0.96, 1.02, 0.82
    center_x = 2.95
    for index, (question, outcome, notes) in enumerate(rows):
        y = top + index * step
        box(slide, 1.15, y, 3.60, height, question, kind="decision")
        box(slide, 5.95, y - 0.02, 3.35, height + 0.04, outcome, notes, kind="term",
            title_size=10.5, body_size=8)
        polyline(slide, [(4.75, y + height / 2), (5.95, y + height / 2)])
        textbox(slide, 5.02, y + height / 2 - 0.14, 0.55, 0.24, ["是"], size=8.5,
                color=TEAL, bold=True)
        if index < len(rows) - 1:
            polyline(slide, [(center_x, y + height), (center_x, y + step)])
            textbox(slide, center_x + 0.08, y + height + 0.02, 0.55, 0.24, ["否"],
                    size=8.5, color=ORANGE, bold=True)

    final_y = top + len(rows) * step
    polyline(slide, [(center_x, top + (len(rows) - 1) * step + height), (center_x, final_y)])
    box(slide, 1.15, final_y, 3.60, 0.62, "继续谈判", ["回到图 1 的行动入口"], kind="muted")

    textbox(slide, 9.60, 1.00, 3.15, 3.20,
            ["判定顺序固定，先命中先终局：",
             "",
             "1. 协议对象优先于退出与超时",
             "2. 退出优先于僵局计数",
             "3. 僵局优先于回合耗尽",
             "",
             "所以「谈成了」不会被后续计时覆盖，",
             "「超时」也不会被包装成成功。"],
            size=8.5, color=GRAY)

    textbox(slide, 0.55, 7.04, 12.2, 0.30,
            ["判定实现：engine/terminal.py ｜ 不新增第六态；"
             "「达成协议」不等于好结果，协议质量与学习表现另算"],
            size=8, color=GRAY)
    return slide


def main() -> None:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slide_main_loop(prs)
    slide_pending(prs)
    slide_terminal(prs)
    prs.save(PPTX)
    print(f"saved {PPTX}")


if __name__ == "__main__":
    main()
