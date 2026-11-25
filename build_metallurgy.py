#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دیاگرام معماری پرومتئوس در محیط متالورژی (فولادسازی) — پاورپوینت قابل ویرایش.

خروجی: prometheus-metallurgy-fa.pptx  (+ پیش‌نمایش PNG برای بازبینی چیدمان)
همهٔ کادرها، متن‌ها و فلش‌ها شکل بومی پاورپوینت‌اند، نه تصویر.
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

OUT = "prometheus-metallurgy-fa.pptx"
PNG = "prometheus-metallurgy-fa.png"
FONT = "Tahoma"
PV_FONT = "_work/fonts/Vazirmatn-Regular.ttf"
PV_FONT_B = "_work/fonts/Vazirmatn-Bold.ttf"

# ---------- palette ----------
NAVY = RGBColor(0x1F, 0x38, 0x64)
NAVY_SOFT = RGBColor(0x2E, 0x4A, 0x7A)
INK = RGBColor(0x1F, 0x2A, 0x37)
MUTED = RGBColor(0x44, 0x4C, 0x58)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREY_TXT = RGBColor(0x5F, 0x68, 0x76)

BLUE = (RGBColor(0xEA, 0xF2, 0xF9), RGBColor(0x5B, 0x8D, 0xB8))
GREEN = (RGBColor(0xE6, 0xF4, 0xEC), RGBColor(0x4E, 0x9C, 0x6B))
PURPLE = (RGBColor(0xEF, 0xEC, 0xF9), RGBColor(0x7C, 0x6B, 0xB0))
ORANGE = (RGBColor(0xFD, 0xEE, 0xDF), RGBColor(0xD9, 0x8B, 0x4A))
SAND = (RGBColor(0xFF, 0xF6, 0xDF), RGBColor(0xD6, 0xA8, 0x3C))
GREY = (RGBColor(0xF4, 0xF6, 0xF9), RGBColor(0xB0, 0xB8, 0xC4))
NAVYF = (RGBColor(0xE7, 0xEC, 0xF5), RGBColor(0x1F, 0x38, 0x64))
TEAL = (RGBColor(0xE4, 0xF2, 0xF3), RGBColor(0x3F, 0x8E, 0x94))

# ---------- geometry ----------
SW, SH = 13.333, 8.75
CL, CR = 0.35, 11.70
W = CR - CL
LAB_X, LAB_W = 11.85, 1.06

R1_Y, R1_H = 1.02, 0.88
COL_Y = 2.04
R2_Y, R2_H = 2.20, 0.72
BOX_Y, BOX_H = 3.18, 1.58
SRV_Y, SRV_H = 4.92, 0.62
AG1_Y, AG_H = 5.72, 0.68
AG2_Y = 6.48
ACT_Y, ACT_H = 7.42, 0.60

GAP = 0.16
W6 = (W - 5 * GAP) / 6
X6 = [CR - W6 - i * (W6 + GAP) for i in range(6)]
C6 = [x + W6 / 2 for x in X6]

GAP3 = 0.22
W3 = (W - 2 * GAP3) / 3
X3 = [CR - W3 - i * (W3 + GAP3) for i in range(3)]
C3 = [x + W3 / 2 for x in X3]

GAP4 = 0.18
W4 = (W - 3 * GAP4) / 4
X4 = [CR - W4 - i * (W4 + GAP4) for i in range(4)]
C4 = [x + W4 / 2 for x in X4]

GAP5 = 0.14
W5 = (W - 4 * GAP5) / 5
X5 = [CR - W5 - i * (W5 + GAP5) for i in range(5)]

# inner boxes of the prediction container
IN = 0.30
W3I = (W - IN - 2 * 0.20) / 3
X3I = [CR - 0.15 - W3I - i * (W3I + 0.20) for i in range(3)]
C3I = [x + W3I / 2 for x in X3I]

W4I = (W - IN - 3 * 0.16) / 4
X4I = [CR - 0.15 - W4I - i * (W4I + 0.16) for i in range(4)]
C4I = [x + W4I / 2 for x in X4I]

# ---------- preview canvas ----------
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


try:  # optional: proper Persian shaping in the preview only
    import arabic_reshaper
    from bidi.algorithm import get_display

    def shape(s):
        return get_display(arabic_reshaper.reshape(str(s)))
except ImportError:  # pragma: no cover
    def shape(s):
        return str(s)


# ---------- pptx helpers ----------
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

    # preview
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


def draw_rows(rows, cx, cy, usable_w):
    """Center a stack of (text, size, bold, color) rows at (cx, cy)."""
    laid = []
    total = 0.0
    for text, size, bold, color in rows:
        f = pf(size, bold)
        words = shape(text).split(" ")
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
    draw_rows([(value, size, bold, color)], x + w / 2, y + h / 2, w)
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
        # preview
        DRAW.line([(p1[0] * DPI, p1[1] * DPI), (p2[0] * DPI, p2[1] * DPI)],
                  fill=_hex(color), width=max(2, int(width * DPI / 72.0)),
                  joint="curve")
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


def vtag(word, cx, cy, size, fill, edge, ink):
    """Preview only: a rotated label pill like the feedback tag."""
    f = pf(size, True)
    tw = DRAW.textlength(shape(word), font=f)
    th = size * 1.35 / 72.0 * DPI
    tmp = Image.new("RGBA", (int(tw) + 8, int(th) + 8), (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    td.text((tmp.width / 2, tmp.height / 2), shape(word), font=f,
            fill=ink, anchor="mm")
    tmp = tmp.rotate(90, expand=True)
    DRAW.rounded_rectangle([(cx - 0.13) * DPI, (cy - 0.58) * DPI,
                            (cx + 0.13) * DPI, (cy + 0.58) * DPI],
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


# ---------- the slide ----------
def build():
    prs = Presentation()
    prs.slide_width = Inches(SW)
    prs.slide_height = Inches(SH)
    s = prs.slides.add_slide(prs.slide_layouts[6])

    # ----- title -----
    text(s, CL, 0.12, W, 0.46,
         "پرومتئوس در محیط متالورژی: پایش و پیش‌بینی فرآیند فولادسازی",
         19, True, NAVY, name="main_title")
    text(s, CL, 0.58, W, 0.30,
         "از کوره قوس الکتریکی تا نورد گرم — ستون پایش پرومتئوس با هشت عامل تخصصی",
         9.5, False, GREY_TXT, name="subtitle")

    # ================= 1) sources =================
    band_label(s, R1_Y, R1_H, "۱", "فرآیند فولادسازی")
    sources = [
        ("کوره قوس الکتریکی", ["EAF • ذوب قراضه و آهن اسفنجی"]),
        ("کوره پاتیل", ["LF/VD • تصفیه و آلیاژسازی"]),
        ("ریخته‌گری پیوسته", ["CCM • تاندیش، قالب، سرعت"]),
        ("خط نورد گرم", ["کاهش ضخامت و دمای نورد"]),
        ("آزمایشگاه متالورژی", ["ترکیب شیمیایی و خواص"]),
        ("MES / ERP", ["سفارش، دستور ذوب، برنامه‌ریزی"]),
    ]
    for i, (t, ls) in enumerate(sources):
        box(s, X6[i], R1_Y, W6, R1_H, t, ls, BLUE, "source_%d" % (i + 1),
            tsize=8.8, bsize=7.2)

    # collector line from the six sources
    arrow(s, [(CL + 0.05, COL_Y), (CR - 0.02, COL_Y)], NAVY_SOFT, 1.1,
          name="collect_bus", head=False)
    for c in C6:
        arrow(s, [(c, R1_Y + R1_H), (c, COL_Y)], NAVY_SOFT, 1.1,
              name="source_stub", head=False)
    for c in C3:
        arrow(s, [(c, COL_Y), (c, R2_Y)], NAVY_SOFT, 1.3, name="bus_to_data")

    # ================= 2) data and metrics =================
    band_label(s, R2_Y, R2_H, "۲", "داده و متریک")
    data = [
        ("رویدادنگار فرآیند (XES)",
         ["هر ذوب یا سفارش یک پرونده", "فعالیت، ایستگاه و زمان هر رویداد"]),
        ("متریک‌های فرآیندی و کیفی",
         ["تاپ‌تو‌پات، سوپرهیت، سرعت ریخته‌گری", "انرژی مخصوص، انحراف ترکیب"]),
        ("ویژگی‌ها و گراف پیشوند",
         ["توالی، زمان تجمعی، نقش و فراوانی", "گراف فعالیت‌ها و ایستگاه‌ها"]),
    ]
    for i, (t, ls) in enumerate(data):
        box(s, X3[i], R2_Y, W3, R2_H, t, ls, GREEN, "data_%d" % (i + 1),
            tsize=9, bsize=7.2)
    for i in (0, 1):
        arrow(s, [(X3[i], R2_Y + R2_H / 2), (X3[i + 1] + W3, R2_Y + R2_H / 2)],
              NAVY_SOFT, 1.4, name="data_flow")

    # ================= 3) prediction service =================
    band_label(s, BOX_Y, BOX_H, "۳", "سرویس پیش‌بینی", ["سه جریان موازی", "چهار سر خروجی"])
    cont = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(CL), Inches(BOX_Y),
                              Inches(W), Inches(BOX_H))
    cont.name = "prediction_service"
    cont.shadow.inherit = False
    cont.fill.solid()
    cont.fill.fore_color.rgb = RGBColor(0xFA, 0xFB, 0xFD)
    cont.line.color.rgb = RGBColor(0x9A, 0xA7, 0xBC)
    cont.line.width = Pt(1.2)
    cont.line.dash_style = 4
    cont.adjustments[0] = 0.05
    DRAW.rounded_rectangle([CL * DPI, BOX_Y * DPI, CR * DPI, (BOX_Y + BOX_H) * DPI],
                           radius=8, fill="#FAFBFD", outline="#9AA7BC", width=2)
    text(s, CL, BOX_Y + 0.05, W, 0.24,
         "مدل سه‌جریانهٔ پرومتئوس — پیش‌بینی فعالیت بعدی، زمان باقی‌مانده، پتانسیل بهبود و گلوگاه",
         8.8, True, NAVY, name="model_title")

    streams = [
        ("جریان ۱ — Transformer", ["وابستگی‌های دوربرد توالی ذوب"], BLUE),
        ("جریان ۲ — TCN", ["الگوهای محلی و چندمقیاسی زمان"], TEAL),
        ("جریان ۳ — GNN", ["گراف ایستگاه‌ها و فعالیت‌ها"], PURPLE),
    ]
    st_y, st_h = BOX_Y + 0.36, 0.50
    for i, (t, ls, col) in enumerate(streams):
        box(s, X3I[i], st_y, W3I, st_h, t, ls, col, "stream_%d" % (i + 1),
            tsize=8.6, bsize=7.0)
    arrow(s, [(C3[2], R2_Y + R2_H), (C3[2], st_y - 0.10)], NAVY_SOFT, 1.3,
          name="to_streams", head=False)
    arrow(s, [(C3I[0], st_y - 0.10), (min(C3[2], C3I[2]), st_y - 0.10)],
          NAVY_SOFT, 1.1, name="stream_bus", head=False)
    for c in C3I:
        arrow(s, [(c, st_y - 0.10), (c, st_y)], NAVY_SOFT, 1.2, name="stream_in")

    heads = [
        ("سر فعالیت بعدی", ["احتمال فعالیت بعدی"], BLUE),
        ("سر زمان باقی‌مانده", ["دقیقه تا پایان ذوب"], GREEN),
        ("سر پتانسیل بهبود", ["دقیقهٔ قابل بازیافت"], SAND),
        ("سر گلوگاه", ["ایستگاه بحرانی"], ORANGE),
    ]
    hd_y, hd_h = BOX_Y + 1.02, 0.40
    arrow(s, [(C3I[0], st_y + st_h), (C3I[0], hd_y - 0.08)], NAVY_SOFT, 1.0,
          name="fuse_stub", head=False)
    arrow(s, [(C3I[0], hd_y - 0.08), (C3I[2], hd_y - 0.08)], NAVY_SOFT, 1.1,
          name="head_bus", head=False)
    for i, (t, ls, col) in enumerate(heads):
        box(s, X4I[i], hd_y, W4I, hd_h, t, ls, col, "head_%d" % (i + 1),
            tsize=8.2, bsize=6.8)
        arrow(s, [(C4I[i], hd_y - 0.08), (C4I[i], hd_y)], NAVY_SOFT, 1.1,
              name="head_in")

    # prediction service exports metrics to Prometheus
    arrow(s, [(10.55, BOX_Y + BOX_H), (10.55, SRV_Y)], NAVY, 1.6,
          name="remote_write")
    text(s, 7.30, BOX_Y + BOX_H + 0.012, 3.10, 0.13,
         "متریک پیش‌بینی → Prometheus", 6.3, False, GREY_TXT, align="r",
         name="remote_write_label")

    # ================= 4) Prometheus + agents =================
    band_label(s, SRV_Y, AG2_Y + AG_H - SRV_Y, "۴", "پایش و عامل‌ها",
               ["سرور پرومتئوس", "هشت عامل تخصصی"])
    srv = box(s, CL, SRV_Y, W, SRV_H, "", (), GREY, "prometheus_server",
              fill_override=NAVY, line_override=None)
    tf = srv.text_frame
    add_par(tf, "سرور پرومتئوس در اتاق کنترل متالورژی", 9.6, True, WHITE, True)
    add_par(tf, "واکشی متریک هر ۱۵ ثانیه  •  پایگاه سری‌زمانی ۹۰ روزه  •  قواعد PromQL: "
                "تاپ‌تو‌پات، سوپرهیت، سرعت ریخته‌گری، انحراف ترکیب",
            7.4, False, RGBColor(0xD8, 0xE0, 0xEE), False)
    DRAW.rounded_rectangle([CL * DPI, SRV_Y * DPI, CR * DPI, (SRV_Y + SRV_H) * DPI],
                           radius=8, fill=_hex(NAVY))
    draw_rows([("سرور پرومتئوس در اتاق کنترل متالورژی", 9.6, True, WHITE),
               ("واکشی متریک هر ۱۵ ثانیه  •  پایگاه سری‌زمانی ۹۰ روزه  •  قواعد PromQL: "
                "تاپ‌تو‌پات، سوپرهیت، سرعت ریخته‌گری، انحراف ترکیب",
                7.4, False, RGBColor(0xD8, 0xE0, 0xEE))],
              (CL + CR) / 2, SRV_Y + SRV_H / 2, W - 0.2)

    agents_a = [
        ("عامل ادراک داده", ["پاک‌سازی، نرمال‌سازی و کیفیت‌سنجی متریک‌ها"], BLUE),
        ("عامل پایش فرآیند", ["مقایسه با محدودهٔ مجاز هر ایستگاه"], BLUE),
        ("عامل پیش‌بینی", ["فراخوانی مدل و رتبه‌بندی فعالیت بعدی"], GREEN),
        ("عامل گلوگاه", ["ریشه‌یابی تأخیر و ایستگاه بحرانی"], ORANGE),
    ]
    agents_b = [
        ("عامل کیفیت متالورژی", ["سوپرهیت، ترکیب شیمیایی و انحراف گرید"], PURPLE),
        ("عامل انرژی", ["مصرف ویژهٔ کوره و برنامهٔ دمش"], SAND),
        ("عامل نگهداشت پیش‌بینانه", ["سلامت تجهیز، عمر نسوز و ارتعاش"], TEAL),
        ("عامل هماهنگ‌کننده و اقدام", ["اولویت هشدار، پیشنهاد اقدام، ثبت بازخورد"], ORANGE),
    ]
    for i, (t, ls, col) in enumerate(agents_a):
        box(s, X4[i], AG1_Y, W4, AG_H, t, ls, col, "agent_%d" % (i + 1),
            tsize=8.6, bsize=7.0)
    for i, (t, ls, col) in enumerate(agents_b):
        box(s, X4[i], AG2_Y, W4, AG_H, t, ls, col, "agent_%d" % (i + 5),
            tsize=8.6, bsize=7.0)
    for c in C4:
        arrow(s, [(c, SRV_Y + SRV_H), (c, AG1_Y)], NAVY_SOFT, 1.2, name="metrics_to_agent")

    # ================= 5) actions + feedback =================
    band_label(s, ACT_Y, ACT_H, "۵", "اقدام و بازخورد")
    actions = [
        ("اپراتور و سرشیفت", ["تأیید یا رد پیشنهاد"]),
        ("ست‌پوینت در MES", ["اصلاح برنامهٔ ذوب و ریخته‌گری"]),
        ("برنامهٔ نگهداشت", ["تعویض نسوز و قطعات"]),
        ("گزارش کیفیت", ["بازخورد به واحد متالورژی"]),
        ("ثبت بازخورد", ["رویداد جدید در رویدادنگار"]),
    ]
    for i, (t, ls) in enumerate(actions):
        box(s, X5[i], ACT_Y, W5, ACT_H, t, ls, GREY, "action_%d" % (i + 1),
            tsize=8.4, bsize=6.9)

    # agents -> one distribution bus -> the five action boxes
    act_bus = ACT_Y - 0.12
    for c in C4:
        arrow(s, [(c, AG2_Y + AG_H), (c, act_bus)], NAVY_SOFT, 1.2,
              name="agent_stub", head=False)
    arrow(s, [(C4[3], act_bus), (C4[0], act_bus)], NAVY_SOFT, 1.1,
          name="action_bus", head=False)
    for i in range(5):
        cx_act = X5[i] + W5 / 2
        arrow(s, [(cx_act, act_bus), (cx_act, ACT_Y)], NAVY_SOFT, 1.2,
              name="to_action")

    # dashed feedback loop: actions back to planning data (left edge)
    FX = 0.16
    arrow(s, [(X5[-1], ACT_Y + ACT_H / 2), (FX, ACT_Y + ACT_H / 2),
              (FX, R1_Y + R1_H / 2), (X6[-1], R1_Y + R1_H / 2)],
          RGBColor(0x8C, 0x6D, 0x3F), 1.2, dashed=True, name="feedback_loop")
    tag = box(s, FX - 0.13, 4.02, 0.26, 1.16, "", (), (SAND, SAND),
              "feedback_label", fill_override=RGBColor(0xFB, 0xEF, 0xD5),
              line_override=RGBColor(0xC9, 0x94, 0x2E))
    tf = tag.text_frame
    tf.margin_left = tf.margin_right = 0
    tf._txBody.find(qn("a:bodyPr")).set("vert", "vert270")
    add_par(tf, "بازخورد", 7.0, True, RGBColor(0x8C, 0x5A, 0x18), True)
    vtag("بازخورد", FX, 4.60, 7.0, (251, 239, 213), (201, 148, 46), (140, 90, 24))

    # ----- footer -----
    text(s, CL, 8.16, W, 0.26,
         "همهٔ اجزا شکل بومی پاورپوینت‌اند: کادرها، متن‌ها، فلش‌ها و رنگ‌ها مستقیماً قابل ویرایش‌اند.",
         7.8, False, GREY_TXT, name="note")

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
    print("saved", OUT, os.path.getsize(OUT), "bytes;", PNG, os.path.getsize(PNG), "bytes")
