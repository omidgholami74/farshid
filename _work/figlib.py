# -*- coding: utf-8 -*-
"""Small declarative figure engine: one spec -> PNG (for Word) + SVG + PPTX (editable).

Coordinates are in inches with the origin at the TOP-LEFT, like PowerPoint.
"""
import os

import arabic_reshaper
import matplotlib
from bidi.algorithm import get_display

matplotlib.use("Agg")
import matplotlib.pyplot as plt                      # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle  # noqa: E402
from matplotlib.font_manager import FontProperties    # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.join(HERE, "fonts", "Vazirmatn-Regular.ttf")
BOLD = os.path.join(HERE, "fonts", "Vazirmatn-Bold.ttf")

FONT_REG = FontProperties(fname=REG)
FONT_BOLD = FontProperties(fname=BOLD)

INK = "#1F3864"
LINE = "#2F5597"


def fa(text):
    """matplotlib >= 3.10 shapes Arabic/Persian itself, so keep logical order."""
    if text is None:
        return ""
    return str(text)


def _fp(bold, size):
    f = FontProperties(fname=BOLD if bold else REG)
    f.set_size(size)
    return f


def box(ax, x, y, w, h, text="", fc="#DEEAF6", ec=LINE, fs=10.5, bold=False,
        radius=0.06, dashed=False, lw=1.3, color=INK, shape="round"):
    """Draw a node; (x, y) is the top-left corner in inches."""
    y = -y  # data coords have y growing upwards
    if shape == "rect":
        patch = Rectangle((x, y - h), w, h, facecolor=fc, edgecolor=ec, lw=lw,
                          linestyle=(0, (4, 2)) if dashed else "-", zorder=2)
    elif shape == "diamond":
        patch = Polygon([(x + w / 2, y), (x + w, y - h / 2), (x + w / 2, y - h),
                         (x, y - h / 2)], closed=True, facecolor=fc, edgecolor=ec,
                        lw=lw, zorder=2)
    else:
        patch = FancyBboxPatch((x, y - h), w, h,
                               boxstyle="round,pad=0,rounding_size=%s" % radius,
                               facecolor=fc, edgecolor=ec, lw=lw,
                               linestyle=(0, (4, 2)) if dashed else "-",
                               mutation_aspect=1, zorder=2)
    ax.add_patch(patch)
    if text:
        lines = str(text).split("\n")
        step = fs / 72.0 * 1.42
        total = step * (len(lines) - 1)
        for i, ln in enumerate(lines):
            ax.text(x + w / 2, y - h / 2 + total / 2 - i * step, fa(ln),
                    ha="center", va="center", fontproperties=_fp(bold, fs),
                    color=color, zorder=3)
    return patch


def arrow(ax, pts, label=None, lw=1.5, dashed=False, color=LINE, rad=0.0,
          head=11, label_fs=9, label_dx=0.0, label_dy=0.08, label_bold=False):
    """Polyline arrow through pts [(x, y), ...] (inches, top-left origin)."""
    xy = [(x, -y) for x, y in pts]
    if len(xy) == 2:
        style = dict(arrowstyle="-|>", connectionstyle="arc3,rad=%s" % rad)
        ax.add_patch(FancyArrowPatch(xy[0], xy[1], lw=lw, color=color,
                                     linestyle=(0, (4, 2)) if dashed else "-",
                                     mutation_scale=head, zorder=1, **style))
    else:
        for a, b in zip(xy[:-1], xy[1:-1]):
            ax.plot([a[0], b[0]], [a[1], b[1]], color=color, lw=lw,
                    linestyle=(0, (4, 2)) if dashed else "-", zorder=1,
                    solid_capstyle="round", solid_joinstyle="round")
        ax.add_patch(FancyArrowPatch(xy[-2], xy[-1], lw=lw, color=color,
                                     linestyle=(0, (4, 2)) if dashed else "-",
                                     mutation_scale=head, arrowstyle="-|>", zorder=1))
    if label:
        mx = sum(p[0] for p in pts) / len(pts) + label_dx
        my = sum(p[1] for p in pts) / len(pts) + label_dy
        ax.text(mx, -my, fa(label), ha="center", va="center",
                fontproperties=_fp(label_bold, label_fs), color=color, zorder=4,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))


def text(ax, x, y, t, fs=10, bold=False, color=INK, ha="center", va="center", rot=0):
    ax.text(x, -y, fa(t), ha=ha, va=va, fontproperties=_fp(bold, fs), color=color, zorder=5,
            rotation=rot)


def line(ax, pts, lw=1.0, dashed=False, color="#808080"):
    """Plain polyline without an arrow head (used for stage separators)."""
    xy = [(x, -y) for x, y in pts]
    ax.plot([p[0] for p in xy], [p[1] for p in xy], lw=lw, color=color,
            linestyle=(0, (6, 3)) if dashed else "-", zorder=0, solid_capstyle="butt")


def render(spec, png_path, svg_path=None, dpi=300):
    w, h = spec.get("size", (11.0, 6.5))
    fig = plt.figure(figsize=(w, h), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w)
    ax.set_ylim(-h, 0)
    ax.axis("off")
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")

    for b in spec.get("boxes", []):
        box(ax, b["x"], b["y"], b["w"], b["h"], b.get("t", ""), b.get("fc", "#DEEAF6"),
            b.get("ec", LINE), b.get("fs", 10.5), b.get("bold", False),
            b.get("r", 0.06), b.get("dash", False), b.get("lw", 1.3),
            b.get("color", INK), b.get("shape", "round"))
    for a in spec.get("arrows", []):
        arrow(ax, a["p"], a.get("label"), a.get("lw", 1.5), a.get("dash", False),
              a.get("color", LINE), a.get("rad", 0.0), a.get("head", 11),
              a.get("lfs", 9), a.get("dx", 0.0), a.get("dy", 0.08), a.get("lbold", False))
    for ln in spec.get("lines", []):
        line(ax, ln["p"], ln.get("lw", 1.0), ln.get("dash", False),
             ln.get("color", "#808080"))
    for t in spec.get("texts", []):
        text(ax, t["x"], t["y"], t["t"], t.get("fs", 10), t.get("bold", False),
             t.get("color", INK), t.get("ha", "center"), t.get("va", "center"),
             t.get("rot", 0))

    os.makedirs(os.path.dirname(png_path) or ".", exist_ok=True)
    fig.savefig(png_path, dpi=dpi, facecolor="white", bbox_inches=None, pad_inches=0)
    if svg_path:
        fig.savefig(svg_path, facecolor="white", bbox_inches=None, pad_inches=0)
    plt.close(fig)
    return png_path


def add_arrowhead(connector, dashed=False):
    """python-pptx has no arrowhead API; write the tailEnd element directly."""
    from pptx.oxml.ns import qn as pqn
    ln = connector.line._get_or_add_ln()
    for tag in ("a:tailEnd", "a:headEnd"):
        for old in ln.findall(pqn(tag)):
            ln.remove(old)
    tail = ln.makeelement(pqn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
    ln.append(tail)
    if dashed:
        from pptx.enum.dml import MSO_LINE_DASH_STYLE
        connector.line.dash_style = MSO_LINE_DASH_STYLE.DASH


def to_pptx(spec, pptx_path, slide_w=13.333, slide_h=None, title=None):
    """Mirror of the same spec as native, editable PowerPoint shapes."""
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.util import Emu, Pt

    w, h = spec.get("size", (11.0, 6.5))
    prs = Presentation()
    prs.slide_width = Emu(int(slide_w * 914400))
    prs.slide_height = Emu(int(slide_w * h / w * 914400))
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    sx = slide_w / w
    sy = (slide_w * h / w) / h
    E = lambda v, s: Emu(int(v * s * 914400))  # noqa: E731

    def rgb(hexstr):
        return RGBColor.from_string(hexstr.lstrip("#").upper())

    for b in spec.get("boxes", []):
        shape_type = {"rect": MSO_SHAPE.RECTANGLE, "diamond": MSO_SHAPE.DIAMOND}.get(
            b.get("shape", "round"), MSO_SHAPE.ROUNDED_RECTANGLE)
        sh = slide.shapes.add_shape(shape_type, E(b["x"], sx), E(b["y"], sy),
                                    E(b["w"], sx), E(b["h"], sy))
        sh.fill.solid()
        sh.fill.fore_color.rgb = rgb(b.get("fc", "#DEEAF6"))
        sh.line.color.rgb = rgb(b.get("ec", LINE))
        sh.line.width = Pt(b.get("lw", 1.3))
        if b.get("dash"):
            from pptx.enum.dml import MSO_LINE_DASH_STYLE
            sh.line.dash_style = MSO_LINE_DASH_STYLE.DASH
        if shape_type == MSO_SHAPE.ROUNDED_RECTANGLE:
            try:
                sh.adjustments[0] = min(0.5, b.get("r", 0.06) / max(b["h"], 0.01))
            except (IndexError, ValueError):
                pass
        tf = sh.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = Emu(20000)
        tf.margin_top = tf.margin_bottom = Emu(10000)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        for i, ln in enumerate(str(b.get("t", "")).split("\n")):
            para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            para.alignment = PP_ALIGN.CENTER
            para._p.get_or_add_pPr().set("rtl", "1")
            run = para.add_run()
            run.text = ln
            run.font.size = Pt(b.get("fs", 10.5))
            run.font.bold = bool(b.get("bold"))
            run.font.name = "Vazirmatn"
            run.font.color.rgb = rgb(b.get("color", INK))

    for a in spec.get("arrows", []):
        pts = a["p"]
        for (x1, y1), (x2, y2) in zip(pts[:-2], pts[1:-1]):
            c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, E(x1, sx), E(y1, sy),
                                           E(x2, sx), E(y2, sy))
            c.line.color.rgb = rgb(a.get("color", LINE))
            c.line.width = Pt(a.get("lw", 1.5))
        x1, y1 = pts[-2]
        x2, y2 = pts[-1]
        c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, E(x1, sx), E(y1, sy),
                                       E(x2, sx), E(y2, sy))
        c.line.color.rgb = rgb(a.get("color", LINE))
        c.line.width = Pt(a.get("lw", 1.5))
        c.line.fill.solid()
        add_arrowhead(c, dashed=a.get("dash", False))

    for ln in spec.get("lines", []):
        pts = ln["p"]
        for (x1, y1), (x2, y2) in zip(pts[:-1], pts[1:]):
            c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, E(x1, sx), E(y1, sy),
                                           E(x2, sx), E(y2, sy))
            c.line.color.rgb = rgb(ln.get("color", "#808080"))
            c.line.width = Pt(ln.get("lw", 1.0))
            if ln.get("dash"):
                from pptx.enum.dml import MSO_LINE_DASH_STYLE
                c.line.dash_style = MSO_LINE_DASH_STYLE.DASH

    for t in spec.get("texts", []):
        rot = t.get("rot", 0)
        bw, bh = (1.75, 0.42) if rot else (1.0, 0.4)
        tb = slide.shapes.add_textbox(E(t["x"] - bw / 2.0, sx), E(t["y"] - bh / 2.0, sy),
                                      E(bw, sx), E(bh, sy))
        if rot:
            tb.rotation = 270
        for i, ln in enumerate(str(t["t"]).split("\n")):
            p = tb.text_frame.paragraphs[0] if i == 0 else tb.text_frame.add_paragraph()
            p.alignment = PP_ALIGN.CENTER
            r = p.add_run()
            r.text = ln
            r.font.size = Pt(t.get("fs", 10))
            r.font.bold = bool(t.get("bold"))
            r.font.name = "Vazirmatn"
            r.font.color.rgb = rgb(t.get("color", INK))

    prs.save(pptx_path)
    return pptx_path
