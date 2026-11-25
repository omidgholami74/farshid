#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دیاگرام پرومتئوس در حالت روش‌شناسی (methodology) — پاورپوینت قابل ویرایش.

سه ستون روش‌شناسی (فرآیندکاوی، یادگیری ماشین، سنجش با پرومتئوس) به‌همراه
دوازده عامل تحلیلی. خروجی: prometheus-methodology-fa.pptx + پیش‌نمایش PNG.
"""

import math
import os

from lxml import etree
from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

OUT = "prometheus-methodology-fa.pptx"
PNG = "prometheus-methodology-fa.png"
FONT = "Tahoma"
PV_FONT = "_work/fonts/Vazirmatn-Regular.ttf"
PV_FONT_B = "_work/fonts/Vazirmatn-Bold.ttf"

NAVY = RGBColor(0x1F, 0x38, 0x64)
NAVY_SOFT = RGBColor(0x2E, 0x4A, 0x7A)
INK = RGBColor(0x1F, 0x2A, 0x37)
MUTED = RGBColor(0x44, 0x4C, 0x58)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREY_TXT = RGBColor(0x5F, 0x68, 0x76)
BROWN = RGBColor(0x8C, 0x5A, 0x18)

BLUE = (RGBColor(0xEA, 0xF2, 0xF9), RGBColor(0x5B, 0x8D, 0xB8))
GREEN = (RGBColor(0xE6, 0xF4, 0xEC), RGBColor(0x4E, 0x9C, 0x6B))
PURPLE = (RGBColor(0xEF, 0xEC, 0xF9), RGBColor(0x7C, 0x6B, 0xB0))
ORANGE = (RGBColor(0xFD, 0xEE, 0xDF), RGBColor(0xD9, 0x8B, 0x4A))
SAND = (RGBColor(0xFF, 0xF6, 0xDF), RGBColor(0xD6, 0xA8, 0x3C))
GREY = (RGBColor(0xF4, 0xF6, 0xF9), RGBColor(0xB0, 0xB8, 0xC4))
NAVYF = (RGBColor(0xE7, 0xEC, 0xF5), RGBColor(0x1F, 0x38, 0x64))
TEAL = (RGBColor(0xE4, 0xF2, 0xF3), RGBColor(0x3F, 0x8E, 0x94))

SW, SH = 13.333, 8.45
CL, CR = 0.35, 11.70
W = CR - CL
LAB_X, LAB_W = 11.85, 1.06

B1_Y, B1_H = 0.96, 0.95
B2_Y, B2_H = 2.10, 1.52
B3_Y, B3_H = 3.78, 0.95
AG_Y, AG_H = 4.90, 2.84
AG1_Y, AG2_Y, AG3_Y = 5.20, 6.06, 6.92
AG_BOX_H = 0.78

GAP = 0.18
W4 = (W - 3 * GAP) / 4
X4 = [CR - W4 - i * (W4 + GAP) for i in range(4)]
C4 = [x + W4 / 2 for x in X4]

W3I = (W - 0.30 - 2 * 0.20) / 3
X3I = [CR - 0.15 - W3I - i * (W3I + 0.20) for i in range(3)]
C3I = [x + W3I / 2 for x in X3I]

W4I = (W - 0.30 - 3 * 0.16) / 4
X4I = [CR - 0.15 - W4I - i * (W4I + 0.16) for i in range(4)]
C4I = [x + W4I / 2 for x in X4I]

DPI = 150
IMG = Image.new("RGB", (int(SW * DPI), int(SH * DPI)), "white")
DRAW = ImageDraw.Draw(IMG)
_FONTS = {}


def pf(size, bold):
    key = (round(size, 1), bold)
    if key not in _FONTS:
        _FONTS[key] = ImageFont.truetype(PV_FONT_B if bold else PV_FONT,
                                         max(7, int(round(size * DPI / 72.0))))
    return _FONTS[key]


def _hex(c):
    return "#" + str(c).upper()


try:
    import arabic_reshaper
    from bidi.algorithm import get_display

    def shape(s):
        return get_display(arabic_reshaper.reshape(str(s)))
except ImportError:  # pragma: no cover
    def shape(s):
        return str(s)


def style_run(run, size, bold=False, color=INK):
    f = run.font
    f.size = Pt(size)
    f.bold = bold
    f.color.rgb = color
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:latin", "a:ea", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = etree.SubElement(rPr, qn(tag))
        el.set("typeface", FONT)


def add_par(tf, value, size, bold=False, color=INK, first=False, before=1.5,
            align="ctr", spacing=1.0):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p._p.get_or_add_pPr().set("rtl", "1")
    p.alignment = {"ctr": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[align]
    p.space_before = Pt(before if not first else 0)
    p.space_after = Pt(0)
    p.line_spacing = spacing
    run = p.add_run()
    run.text = str(value)
    style_run(run, size, bold, color)


def draw_rows(rows, cx, cy, usable_w):
    laid = []
    total = 0.0
    for value, size, bold, color in rows:
        f = pf(size, bold)
        words = shape(value).split(" ")
        lines, cur = [], ""
        for wd in words:
            trial = (cur + " " + wd).strip()
            if not cur or DRAW.textlength(trial, font=f) <= usable_w * DPI:
                cur = trial
            else:
                lines.append(cur)
                cur = wd
        if cur:
            lines.append(cur)
        step = size * 1.28 / 72.0
        total += step * len(lines)
        laid.append((lines, step, size, bold, color))
    y = cy - total / 2
    for lines, step, size, bold, color in laid:
        f = pf(size, bold)
        for ln in lines:
            DRAW.text((cx * DPI, (y + step / 2) * DPI), ln, font=f,
                      fill=_hex(color), anchor="mm")
            y += step


def box(slide, x, y, w, h, title="", lines=(), colors=BLUE, name="box",
        tsize=9, bsize=7.2, title_color=INK, body_color=MUTED,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, fill_override=None,
        line_override=None, dashed=False, align="ctr"):
    fill, line = colors
    if fill_override is not None:
        fill = fill_override
    if line_override is not None:
        line = line_override

    sh = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.name = name
    sh.shadow.inherit = False
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line
        sh.line.width = Pt(1.1 if shape != MSO_SHAPE.RECTANGLE else 1.0)
        if dashed:
            sh.line.dash_style = 4
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        sh.adjustments[0] = min(0.35, 0.08 / max(min(w, h), 0.01))

    tf = sh.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = Inches(0.045)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    if title:
        add_par(tf, title, tsize, True, title_color, True, align=align)
    for i, ln in enumerate(lines):
        add_par(tf, ln, bsize, False, body_color, i == 0 and not title, align=align)

    x0, y0, x1, y1 = x * DPI, y * DPI, (x + w) * DPI, (y + h) * DPI
    rad = 8 if shape == MSO_SHAPE.ROUNDED_RECTANGLE else 0
    DRAW.rounded_rectangle([x0, y0, x1, y1], radius=rad, fill=_hex(fill),
                           outline=None if line is None else _hex(line), width=2)
    rows = []
    if title:
        rows.append((title, tsize, True, title_color))
    rows += [(ln, bsize, False, body_color) for ln in lines]
    draw_rows(rows, x + w / 2, y + h / 2, w - 0.10)
    return sh


def text(slide, x, y, w, h, value, size=9, bold=False, color=MUTED,
         align="ctr", name="text"):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = Inches(0.02)
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    add_par(tf, value, size, bold, color, True, align=align)
    draw_rows([(value, size, bold, color)], x + w / 2, y + h / 2,
              w - 0.04)
    return tb


def arrow(slide, pts, color=NAVY_SOFT, width=1.5, dashed=False, name="arrow",
          head=True):
    pts = list(pts)
    for i, (p1, p2) in enumerate(zip(pts[:-1], pts[1:])):
        cn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,
                                        Inches(p1[0]), Inches(p1[1]),
                                        Inches(p2[0]), Inches(p2[1]))
        cn.name = name
        cn.line.color.rgb = color
        cn.line.width = Pt(width)
        if dashed:
            cn.line.dash_style = 4
        if head and i == len(pts) - 2:
            ln = cn.line._get_or_add_ln()
            tail = etree.SubElement(ln, qn("a:tailEnd"))
            tail.set("type", "triangle")
            tail.set("w", "sm")
            tail.set("len", "med")
        DRAW.line([(p1[0] * DPI, p1[1] * DPI), (p2[0] * DPI, p2[1] * DPI)],
                  fill=_hex(color), width=max(2, int(width * DPI / 72.0)))
    if head and len(pts) >= 2:
        (xa, ya), (xb, yb) = pts[-2], pts[-1]
        vx, vy = xb - xa, yb - ya
        n = math.hypot(vx, vy) or 1.0
        ux, uy = vx / n, vy / n
        L, Wd = 0.13 * DPI, 0.045 * DPI
        tip = (xb * DPI, yb * DPI)
        DRAW.polygon([tip,
                      (tip[0] - L * ux - Wd * uy, tip[1] - L * uy + Wd * ux),
                      (tip[0] - L * ux + Wd * uy, tip[1] - L * uy - Wd * ux)],
                     fill=_hex(color))


def vtag(word, cx, cy, size, fill, edge, ink, h=1.16):
    f = pf(size, True)
    tw = DRAW.textlength(shape(word), font=f)
    th = size * 1.35 / 72.0 * DPI
    tmp = Image.new("RGBA", (int(tw) + 8, int(th) + 8), (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    td.text((tmp.width / 2, tmp.height / 2), shape(word), font=f,
            fill=ink, anchor="mm")
    tmp = tmp.rotate(90, expand=True)
    DRAW.rounded_rectangle([(cx - 0.13) * DPI, (cy - h / 2) * DPI,
                            (cx + 0.13) * DPI, (cy + h / 2) * DPI],
                           radius=8, fill=fill, outline=edge, width=2)
    IMG.paste(tmp, (int(cx * DPI - tmp.width / 2), int(cy * DPI - tmp.height / 2)), tmp)


def band_label(slide, y, h, number, title, subs=()):
    sh = box(slide, LAB_X, y, LAB_W, h, "", (), (NAVY, NAVY), "phase_label",
             fill_override=NAVY, line_override=None)
    tf = sh.text_frame
    tf.word_wrap = True
    add_par(tf, number, 10, True, WHITE, True)
    add_par(tf, title, 8.2, True, WHITE, False)
    for s in subs:
        add_par(tf, s, 7, False, RGBColor(0xD5, 0xDE, 0xEC), False)
    rows = [(number, 10, True, WHITE), (title, 8.2, True, WHITE)]
    rows += [(s, 7, False, RGBColor(0xD5, 0xDE, 0xEC)) for s in subs]
    DRAW.rounded_rectangle([LAB_X * DPI, y * DPI, (LAB_X + LAB_W) * DPI,
                            (y + h) * DPI], radius=8, fill=_hex(NAVY))
    draw_rows(rows, LAB_X + LAB_W / 2, y + h / 2, LAB_W - 0.08)
    return sh


def container(slide, x, y, w, h, name, fill="#FBFCFD"):
    sh = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y),
                                Inches(w), Inches(h))
    sh.name = name
    sh.shadow.inherit = False
    sh.fill.solid()
    sh.fill.fore_color.rgb = RGBColor.from_string(fill.lstrip("#"))
    sh.line.color.rgb = RGBColor(0x9A, 0xA7, 0xBC)
    sh.line.width = Pt(1.2)
    sh.line.dash_style = 4
    sh.adjustments[0] = 0.04
    DRAW.rounded_rectangle([x * DPI, y * DPI, (x + w) * DPI, (y + h) * DPI],
                           radius=8, fill=fill, outline="#9AA7BC", width=2)
    return sh


def build():
    prs = Presentation()
    prs.slide_width = Inches(SW)
    prs.slide_height = Inches(SH)
    s = prs.slides.add_slide(prs.slide_layouts[6])

    text(s, CL, 0.12, W, 0.44,
         "پرومتئوس به‌مثابهٔ روش سنجش: پایش و ارزیابی خط لولهٔ پیش‌بینی فرآیند",
         18.5, True, NAVY, name="main_title")
    text(s, CL, 0.56, W, 0.28,
         "سه ستون روش‌شناسی — فرآیندکاوی، یادگیری ماشین، سنجش با پرومتئوس — و دوازده عامل تحلیلی",
         9.3, False, GREY_TXT, name="subtitle")

    # ================= 1) process mining =================
    band_label(s, B1_Y, B1_H, "۱", "روش فرآیندکاوی", ["ستون یکم"])
    p1 = [
        ("رویدادنگار فرآیند (XES)", ["BPI Challenge 2012", "پرونده، فعالیت و زمان"]),
        ("ساخت پیشوند", ["کمترین طول پیشوند: ۲", "هر پیشوند یک نمونهٔ آموزش"]),
        ("شاخص‌های موردی و زمانی", ["انتظار، مدت کل", "زمان باقی‌مانده"]),
        ("گراف پیشوند", ["گره: فعالیت", "یال: ترتیب و تکرار"]),
    ]
    for i, (t, ls) in enumerate(p1):
        box(s, X4[i], B1_Y, W4, B1_H, t, ls, BLUE, "stage1_%d" % (i + 1),
            tsize=9.2, bsize=7.2)
    for i in range(3):
        arrow(s, [(X4[i], B1_Y + B1_H / 2), (X4[i + 1] + W4, B1_Y + B1_H / 2)],
              NAVY_SOFT, 1.5, name="stage1_flow")

    # ================= 2) machine learning =================
    band_label(s, B2_Y, B2_H, "۲", "روش یادگیری ماشین",
               ["مدل سه‌جریانه", "چهار سر خروجی"])
    container(s, CL, B2_Y, W, B2_H, "model_container")

    st_y, st_h = 2.34, 0.52
    arrow(s, [(C4[3], B1_Y + B1_H), (C4[3], 2.02), (C3I[0], 2.02),
              (C3I[0], st_y)], NAVY_SOFT, 1.2, name="to_model", head=False)
    for c in C3I:
        arrow(s, [(c, 2.02), (c, st_y)], NAVY_SOFT, 1.3, name="stream_in")

    streams = [
        ("جریان ۱ — Transformer", ["وابستگی‌های دوربرد توالی"], BLUE),
        ("جریان ۲ — TCN", ["الگوهای محلی چندمقیاسی"], TEAL),
        ("جریان ۳ — GNN", ["گراف فعالیت‌ها و روابط"], PURPLE),
    ]
    for i, (t, ls, col) in enumerate(streams):
        box(s, X3I[i], st_y, W3I, st_h, t, ls, col, "stream_%d" % (i + 1),
            tsize=8.8, bsize=7.0)

    heads = [
        ("سر فعالیت بعدی", ["احتمال فعالیت"], BLUE),
        ("سر زمان باقی‌مانده", ["دقیقه"], GREEN),
        ("سر پتانسیل بهبود", ["دقیقهٔ قابل بازیافت"], SAND),
        ("سر گلوگاه", ["فعالیت بحرانی"], ORANGE),
    ]
    hd_y, hd_h = 3.06, 0.42
    arrow(s, [(C3I[0], st_y + st_h), (C3I[0], 2.96)], NAVY_SOFT, 1.0,
          name="fuse_stub", head=False)
    arrow(s, [(C3I[0], 2.96), (C3I[2], 2.96)], NAVY_SOFT, 1.1,
          name="head_bus", head=False)
    for i, (t, ls, col) in enumerate(heads):
        box(s, X4I[i], hd_y, W4I, hd_h, t, ls, col, "head_%d" % (i + 1),
            tsize=8.4, bsize=6.8)
        arrow(s, [(C4I[i], 2.96), (C4I[i], hd_y)], NAVY_SOFT, 1.1, name="head_in")

    # ================= 3) measurement with Prometheus =================
    band_label(s, B3_Y, B3_H, "۳", "روش سنجش با پرومتئوس", ["متریک", "آستانه"])
    p3 = [
        ("تعریف متریک و قواعد ثبت", ["Top-k، MAE، نرخ گلوگاه", "قاعدهٔ ثبت در PromQL"]),
        ("واکشی و سری‌زمانی", ["برچسب نسخهٔ مدل، داده و اجرا", "نمونه‌برداری هر ۱۵ ثانیه"]),
        ("آستانه و هشدار روش‌شناختی", ["افت دقت، Drift", "خطای زمان و بهبود"]),
        ("داشبورد و خروجی تکرارپذیر", ["Grafana برای پایش زنده", "CSV/JSON برای فصل ۴"]),
    ]
    for i, (t, ls) in enumerate(p3):
        box(s, X4[i], B3_Y, W4, B3_H, t, ls, GREEN, "stage3_%d" % (i + 1),
            tsize=9.2, bsize=7.2)
    for c in C4:
        arrow(s, [(c, B2_Y + B2_H), (c, B3_Y)], NAVY_SOFT, 1.2, name="model_to_metric")
    for i in range(3):
        arrow(s, [(X4[i], B3_Y + B3_H / 2), (X4[i + 1] + W4, B3_Y + B3_H / 2)],
              NAVY_SOFT, 1.4, name="stage3_flow")

    # ================= 4) agents =================
    band_label(s, AG_Y, AG_H, "۴", "عامل‌های تحلیلی",
               ["دوازده عامل", "سنجش، تحلیل", "و تصمیم"])
    container(s, CL, AG_Y, W, AG_H, "agents_container", fill="#F7F9FC")
    text(s, 7.10, AG_Y + 0.03, 4.45, 0.22,
         "سامانهٔ چندعاملی تحلیلی — دوازده عامل تخصصی", 8.6, True, NAVY,
         align="r", name="agents_title")
    for x in (C4[3], C4[2]):
        arrow(s, [(x, B3_Y + B3_H), (x, AG_Y)], NAVY_SOFT, 1.4, name="metric_to_agents")

    agents = [
        [("عامل کیفیت داده", ["کامل‌بودن و ناسازگاری رویدادها"], BLUE),
         ("عامل اعتبار تقسیم", ["نشت‌نداشتن پرونده بین آموزش و آزمون"], BLUE),
         ("عامل پایش آموزش", ["زیان، نرخ یادگیری و همگرایی"], BLUE),
         ("عامل دقت طبقه‌بندی", ["Top-k و ماتریس درهم‌ریختگی"], BLUE)],
        [("عامل خطای زمان", ["MAE زمان باقی‌مانده و بهبود"], TEAL),
         ("عامل کالیبراسیون", ["تطابق احتمال با فراوانی واقعی"], TEAL),
         ("عامل Drift", ["تغییر توزیع داده و مفهوم"], TEAL),
         ("عامل گلوگاه", ["رتبه‌بندی فعالیت بر پایهٔ انتظار"], TEAL)],
        [("عامل تعریف متریک", ["پیشنهاد متریک و قاعدهٔ ثبت"], SAND),
         ("عامل آستانه و هشدار", ["فعال‌سازی قاعده و مسیریابی هشدار"], SAND),
         ("عامل گزارش روش‌شناختی", ["جدول و نمودار قابل ارجاع"], SAND),
         ("عامل هماهنگ‌کننده", ["ترتیب اجرا، ثبت آزمایش و بازخورد"], ORANGE)],
    ]
    for r, (row, y) in enumerate(zip(agents, (AG1_Y, AG2_Y, AG3_Y))):
        for i, (t, ls, col) in enumerate(row):
            box(s, X4[i], y, W4, AG_BOX_H, t, ls, col,
                "agent_%d" % (r * 4 + i + 1), tsize=8.8, bsize=7.0)

    # ================= feedback loop =================
    FX = 0.15
    arrow(s, [(CL, 6.30), (FX, 6.30), (FX, B1_Y + 0.47), (CL, B1_Y + 0.47)],
          BROWN, 1.25, dashed=True, name="method_feedback")
    tag = box(s, FX - 0.13, 2.95, 0.26, 1.62, "", (), (SAND, SAND),
              "feedback_label", fill_override=RGBColor(0xFB, 0xEF, 0xD5),
              line_override=RGBColor(0xC9, 0x94, 0x2E))
    tf = tag.text_frame
    tf.margin_left = tf.margin_right = 0
    tf._txBody.find(qn("a:bodyPr")).set("vert", "vert270")
    add_par(tf, "اصلاح مدل و متریک", 6.5, True, BROWN, True)
    vtag("اصلاح مدل و متریک", FX, 3.76, 6.5, (251, 239, 213), (201, 148, 46),
         (140, 90, 24), h=1.62)

    # ================= cycle caption =================
    text(s, CL, 7.82, W, 0.24,
         "چرخهٔ روش‌شناختی: طراحی آزمایش  →  اجرای خط لوله  →  سنجش با پرومتئوس  →  "
         "تحلیل عامل‌ها و اصلاح مدل یا متریک",
         8.4, True, NAVY_SOFT, name="cycle_caption")
    text(s, CL, 8.10, W, 0.22,
         "همهٔ اجزا شکل بومی پاورپوینت‌اند: کادرها، متن‌ها، فلش‌ها و رنگ‌ها مستقیماً قابل ویرایش‌اند.",
         7.6, False, GREY_TXT, name="note")

    prs.save(OUT)
    IMG.save(PNG)
    return prs


def check(prs):
    sw, sh = prs.slide_width / 914400.0, prs.slide_height / 914400.0
    bad = []
    for shape in prs.slides[0].shapes:
        x, y = shape.left / 914400.0, shape.top / 914400.0
        w, h = shape.width / 914400.0, shape.height / 914400.0
        if x < -0.01 or y < -0.01 or x + w > sw + 0.01 or y + h > sh + 0.01:
            bad.append((shape.name, round(x, 2), round(y, 2),
                        round(x + w, 2), round(y + h, 2)))
    print("shapes:", len(prs.slides[0].shapes), "| slide:", sw, "x", sh)
    print("out of bounds:", bad if bad else "none")
    return bad


if __name__ == "__main__":
    pres = build()
    assert not check(pres), "شکلی بیرون از اسلاید است"
    print("saved", OUT, os.path.getsize(OUT), "bytes;", PNG,
          os.path.getsize(PNG), "bytes")
