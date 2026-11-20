# -*- coding: utf-8 -*-
"""Declarative figure engine -> native editable PowerPoint shapes.

Coordinates are inches, origin at the TOP-LEFT corner (like PowerPoint).
Every figure is drawn with the B Nazanin font and right-to-left paragraphs.
Optional `png=` in build() also paints an approximate preview with PIL so the
layout can be inspected without PowerPoint (Vazirmatn is used for the preview).
"""
import os

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

FONT = "B Nazanin"
LATIN_FONT = "Arial"
PV_FONT = "fonts/Vazirmatn-Regular.ttf"
PV_FONT_B = "fonts/Vazirmatn-Bold.ttf"

INK = "#1F3864"
LINE = "#2F5597"
MUTED = "#404040"
SEP = "#8C8C8C"

BLUE = "#DEEAF6"
GREEN = "#E2EFDA"
SAND = "#FFF2CC"
ORANGE = "#FBE5D6"
PINK = "#F8DCDC"
PURPLE = "#E4DFEC"
GREY = "#F2F2F2"
WHITE = "#FFFFFF"

REG = {}


def figure(name, W, H):
    def deco(fn):
        REG[name] = (W, H, fn)
        return fn
    return deco


def _rgb(hexstr):
    return RGBColor.from_string(hexstr.lstrip("#").upper())


def _typeface(run, font):
    """Persian/Arabic runs use `font`; Latin, digits and math symbols use Arial
    (B Nazanin has no Greek/math glyphs, so λ, ⊙ and −∞ keep rendering)."""
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:latin", "a:ea", "a:cs"):
        for old in rPr.findall(qn(tag)):
            rPr.remove(old)
    rPr.append(rPr.makeelement(qn("a:latin"), {"typeface": LATIN_FONT}))
    rPr.append(rPr.makeelement(qn("a:ea"), {"typeface": font}))
    rPr.append(rPr.makeelement(qn("a:cs"), {"typeface": font}))


def _style(run, fs, bold, color, font, italic=False):
    run.font.size = Pt(fs)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = _rgb(color)
    _typeface(run, font)


ALIGN = {"ctr": PP_ALIGN.CENTER, "center": PP_ALIGN.CENTER,
         "r": PP_ALIGN.RIGHT, "right": PP_ALIGN.RIGHT,
         "l": PP_ALIGN.LEFT, "left": PP_ALIGN.LEFT,
         "just": PP_ALIGN.JUSTIFY}


class Fig:
    def __init__(self, slide, W, H, scale=1.0, font=FONT, png=None, dpi=140):
        self.slide = slide
        self.W, self.H = W, H
        self.k = scale
        self.font = font
        self.dpi = dpi
        self.img = None
        self.d = None
        if png:
            self.img = Image.new("RGB", (int(W * dpi), int(H * dpi)), "white")
            self.d = ImageDraw.Draw(self.img)
            self._fonts = {}

    # -- preview helpers -------------------------------------------------
    def _pf(self, fs, bold):
        key = (round(fs, 1), bold)
        if key not in self._fonts:
            path = PV_FONT_B if bold else PV_FONT
            self._fonts[key] = ImageFont.truetype(
                path, max(6, int(round(fs * self.dpi / 72.0))))
        return self._fonts[key]

    def _pt(self, fs, bold, text, cx_, cy_, color, maxw=None):
        """Draw one preview line centred on (cx_, cy_) in inches."""
        f = self._pf(fs, bold)
        if maxw:
            words = str(text).split(" ")
            lines, cur = [], ""
            for wd in words:
                trial = (cur + " " + wd).strip()
                if self.d.textlength(trial, font=f) <= maxw * self.dpi or not cur:
                    cur = trial
                else:
                    lines.append(cur)
                    cur = wd
            if cur:
                lines.append(cur)
        else:
            lines = [text]
        step = fs * 1.32 / 72.0
        total = step * (len(lines) - 1)
        for i, ln in enumerate(lines):
            y = cy_ + total / 2 - i * step
            self.d.text((cx_ * self.dpi, y * self.dpi), ln, font=f,
                        fill=color, anchor="mm")

    # -- primitives ------------------------------------------------------
    def _emu(self, v):
        return Emu(int(round(v * self.k * 914400)))

    def box(self, x, y, w, h, text="", fc=BLUE, ec=LINE, fs=12, bold=False,
            color=INK, radius=0.06, dash=False, lw=1.25, shape="round",
            align="ctr", anchor="mid", margins=(0.06, 0.03), spacing=1.0,
            name=None):
        kind = {"rect": MSO_SHAPE.RECTANGLE, "diamond": MSO_SHAPE.DIAMOND,
                "round": MSO_SHAPE.ROUNDED_RECTANGLE}.get(
                    shape, MSO_SHAPE.ROUNDED_RECTANGLE)
        sh = self.slide.shapes.add_shape(kind, self._emu(x), self._emu(y),
                                        self._emu(w), self._emu(h))
        sh.name = name or (str(text).split("\n")[0][:28] or "box")
        sh.shadow.inherit = False
        if fc is None:
            sh.fill.background()
        else:
            sh.fill.solid()
            sh.fill.fore_color.rgb = _rgb(fc)
        if ec is None:
            sh.line.fill.background()
        else:
            sh.line.color.rgb = _rgb(ec)
            sh.line.width = Pt(lw)
            if dash:
                sh.line.dash_style = MSO_LINE_DASH_STYLE.DASH
        if kind == MSO_SHAPE.ROUNDED_RECTANGLE:
            try:
                sh.adjustments[0] = min(0.5, radius / max(h, 0.01))
            except (IndexError, ValueError):
                pass
        tf = sh.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = self._emu(margins[0])
        tf.margin_top = tf.margin_bottom = self._emu(margins[1])
        tf.vertical_anchor = {"mid": MSO_ANCHOR.MIDDLE, "top": MSO_ANCHOR.TOP,
                              "bot": MSO_ANCHOR.BOTTOM}[anchor]
        self._fill(tf, text, fs, bold, color, align, spacing)

        if self.d is not None:
            d = self.d
            x0, y0, x1, y1 = (x * self.dpi, y * self.dpi,
                              (x + w) * self.dpi, (y + h) * self.dpi)
            rad = (radius if shape == "round" else 0) * self.dpi
            if fc:
                d.rounded_rectangle([x0, y0, x1, y1], radius=rad, fill=fc,
                                    outline=ec,
                                    width=max(1, int(lw * self.dpi / 72.0)))
            elif ec:
                d.rounded_rectangle([x0, y0, x1, y1], radius=rad, outline=ec,
                                    width=max(1, int(lw * self.dpi / 72.0)))
            if text:
                lines = str(text).split("\n")
                step = fs * 1.32 / 72.0
                total = step * (len(lines) - 1)
                for i, ln in enumerate(lines):
                    cy_ = (y + h / 2) - total / 2 + i * step
                    self._pt(fs, bold, ln.replace("**", ""), x + w / 2, cy_,
                             color, maxw=w - 2 * margins[0])
        return sh

    def _fill(self, tf, text, fs, bold, color, align="ctr", spacing=1.0):
        lines = str(text).split("\n") if text else []
        if not lines:
            return
        for i, ln in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = ALIGN[align]
            p._p.get_or_add_pPr().set("rtl", "1")
            if spacing != 1.0:
                p.line_spacing = spacing
            for j, seg in enumerate(str(ln).split("**")):
                if not seg:
                    continue
                run = p.add_run()
                run.text = seg
                _style(run, fs * self.k, bold or (j % 2 == 1), color, self.font)

    def text(self, x, y, w, h, s, fs=12, bold=False, color=INK, align="r",
             anchor="mid", spacing=1.0, name=None):
        tb = self.slide.shapes.add_textbox(self._emu(x), self._emu(y),
                                           self._emu(w), self._emu(h))
        tb.name = name or ("txt " + str(s).split("\n")[0][:24])
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = Emu(0)
        tf.margin_top = tf.margin_bottom = Emu(0)
        tf.vertical_anchor = {"mid": MSO_ANCHOR.MIDDLE, "top": MSO_ANCHOR.TOP,
                              "bot": MSO_ANCHOR.BOTTOM}[anchor]
        self._fill(tf, s, fs, bold, color, align, spacing)

        if self.d is not None:
            lines = str(s).split("\n")
            step = fs * 1.32 / 72.0
            total = step * (len(lines) - 1)
            for i, ln in enumerate(lines):
                cy_ = (y + h / 2) - total / 2 + i * step
                if align in ("r", "right"):
                    px = (x + w) * self.dpi
                    f = self._pf(fs, bold or "**" in ln)
                    self.d.text((px, cy_ * self.dpi), ln.replace("**", ""),
                                font=f, fill=color, anchor="rm")
                elif align in ("l", "left"):
                    f = self._pf(fs, bold or "**" in ln)
                    self.d.text((x * self.dpi, cy_ * self.dpi),
                                ln.replace("**", ""), font=f, fill=color,
                                anchor="lm")
                else:
                    self._pt(fs, bold or "**" in ln, ln.replace("**", ""),
                             x + w / 2, cy_, color, maxw=w)
        return tb

    def label(self, x, y, s, fs=12, bold=False, color=INK, rot=0, w=2.0,
              h=0.4, align="ctr"):
        tb = self.text(x - w / 2, y - h / 2, w, h, s, fs=fs, bold=bold,
                       color=color, align=align)
        if rot:
            tb.rotation = rot
        return tb

    def line(self, pts, lw=1.0, dash=False, color=SEP, name=None):
        for (x1, y1), (x2, y2) in zip(pts[:-1], pts[1:]):
            c = self.slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,
                                                self._emu(x1), self._emu(y1),
                                                self._emu(x2), self._emu(y2))
            c.name = name or "line"
            c.line.color.rgb = _rgb(color)
            c.line.width = Pt(lw)
            if dash:
                c.line.dash_style = MSO_LINE_DASH_STYLE.DASH
        if self.d is not None:
            self.d.line([(p[0] * self.dpi, p[1] * self.dpi) for p in pts],
                        fill=color, width=max(1, int(lw * self.dpi / 72.0)))

    def arrow(self, pts, lw=1.5, color=LINE, dash=False, head=True, name=None):
        segs = list(zip(pts[:-1], pts[1:]))
        for idx, ((x1, y1), (x2, y2)) in enumerate(segs):
            c = self.slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,
                                                self._emu(x1), self._emu(y1),
                                                self._emu(x2), self._emu(y2))
            c.name = name or "arrow"
            c.line.color.rgb = _rgb(color)
            c.line.width = Pt(lw)
            if dash:
                c.line.dash_style = MSO_LINE_DASH_STYLE.DASH
            if head and idx == len(segs) - 1:
                ln = c.line._get_or_add_ln()
                ln.append(ln.makeelement(qn("a:tailEnd"),
                                         {"type": "triangle", "w": "med",
                                          "len": "med"}))
        if self.d is not None:
            d = self.d
            wpx = max(1, int(lw * self.dpi / 72.0))
            d.line([(p[0] * self.dpi, p[1] * self.dpi) for p in pts],
                   fill=color, width=wpx)
            if head and len(pts) >= 2:
                (x1, y1), (x2, y2) = pts[-2], pts[-1]
                vx, vy = x2 - x1, y2 - y1
                n = max((vx * vx + vy * vy) ** 0.5, 1e-6)
                ux, uy = vx / n, vy / n
                L, Wd = 0.14 * self.dpi, 0.05 * self.dpi
                tip = (x2 * self.dpi, y2 * self.dpi)
                p1 = (tip[0] - L * ux - Wd * uy, tip[1] - L * uy + Wd * ux)
                p2 = (tip[0] - L * ux + Wd * uy, tip[1] - L * uy - Wd * ux)
                d.polygon([tip, p1, p2], fill=color)

    # -- helpers ---------------------------------------------------------
    def title(self, s, fs=16, color=INK, y=0.12, h=0.42):
        return self.text(0.25, y, self.W - 0.5, h, s, fs=fs, bold=True,
                         color=color, align="ctr")

    def chart_gap(self, x, y, w, h, label="نمودار"):
        """Placeholder so the preview shows where a native chart sits."""
        if self.d is not None:
            self.d.rectangle([x * self.dpi, y * self.dpi,
                              (x + w) * self.dpi, (y + h) * self.dpi],
                             outline="#BFBFBF", width=2)
            self.d.text(((x + w / 2) * self.dpi, (y + h / 2) * self.dpi),
                        label, font=self._pf(12, False), fill="#BFBFBF",
                        anchor="mm")

    def stack(self, x, y, w, h, n, gap=0.08):
        return [(x, y + i * (h + gap), w, h) for i in range(n)]

    def row(self, x, y, w, h, n, gap=0.15, total=None):
        if total is None:
            total = n * w + (n - 1) * gap
        step = (total - w) / max(n - 1, 1) if n > 1 else 0
        return [(x + i * step, y, w, h) for i in range(n)]


def bottom(b):
    return b[1] + b[3]


def right(b):
    return b[0] + b[2]


def cx(b):
    return b[0] + b[2] / 2.0


def cy(b):
    return b[1] + b[3] / 2.0


def new_deck(W, H, scale=1.0, png=False):
    prs = Presentation()
    prs.slide_width = Emu(int(round(W * scale * 914400)))
    prs.slide_height = Emu(int(round(H * scale * 914400)))
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fig = Fig(slide, W, H, scale=scale, png=png)
    return prs, fig


def build(name, outdir, pngdir=None, font=FONT):
    W, H, fn = REG[name]
    prs, fig = new_deck(W, H, 1.0, png=bool(pngdir))
    fig.font = font
    fn(fig)
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, name + ".pptx")
    prs.save(path)
    if pngdir and fig.img is not None:
        os.makedirs(pngdir, exist_ok=True)
        fig.img.save(os.path.join(pngdir, name + ".png"))
    return path
