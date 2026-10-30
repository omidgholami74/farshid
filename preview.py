#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""پیش‌نمایش تقریبی + بررسی سرریز متن، هم‌پوشانی و بیرون‌زدگی شکل‌ها.

usage: preview.py <file.pptx> <prefix> [dpi]
"""

import math
import sys

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn
from pptx.util import Emu

DPI = 110
REG = "fonts/Vazirmatn-Regular.ttf"
BLD = "fonts/Vazirmatn-Bold.ttf"

PPTX = sys.argv[1] if len(sys.argv) > 1 else "prometheus-architecture-fa.pptx"
PREFIX = sys.argv[2] if len(sys.argv) > 2 else "slide"
if len(sys.argv) > 3:
    DPI = int(sys.argv[3])

_cache = {}


def font(size_px, bold):
    k = (round(size_px), bold)
    if k not in _cache:
        _cache[k] = ImageFont.truetype(BLD if bold else REG, max(6, round(size_px)))
    return _cache[k]


def shape_text(sh):
    out = []
    for p in sh.text_frame.paragraphs:
        txt = "".join(r.text for r in p.runs)
        if not txt.strip():
            continue
        r0 = p.runs[0]
        size = r0.font.size.pt if r0.font.size else 10
        bold = bool(r0.font.bold)
        col = (34, 48, 63)
        try:
            if r0.font.color and r0.font.color.rgb:
                c = r0.font.color.rgb
                col = (c[0], c[1], c[2])
        except Exception:
            pass
        align = str(p.alignment).split(".")[-1].split(" ")[0] if p.alignment else "CENTER"
        out.append((txt, size, bold, col, align, p.space_before.pt if p.space_before else 0))
    return out


def is_connector(sh):
    return sh.__class__.__name__ == "Connector" or sh.shape_type == 20


def draw_slide(slide, path):
    W, H = 13.333 * DPI, 7.5 * DPI
    prs_w = Emu(prs.slide_width).inches * DPI
    prs_h = Emu(prs.slide_height).inches * DPI
    img = Image.new("RGB", (int(prs_w), int(prs_h)), "white")
    d = ImageDraw.Draw(img)
    problems = []
    rects = []

    for sh in slide.shapes:
        x, y = Emu(sh.left).inches * DPI, Emu(sh.top).inches * DPI
        w, h = Emu(sh.width).inches * DPI, Emu(sh.height).inches * DPI

        if x < -1 or y < -1 or x + w > prs_w + 1 or y + h > prs_h + 1:
            problems.append(
                f"OUT OF SLIDE: {sh.name} ({x/DPI:.2f},{y/DPI:.2f},{w/DPI:.2f},{h/DPI:.2f})")

        if is_connector(sh):
            xfrm = sh._element.spPr.xfrm
            flipH = xfrm.get("flipH") in ("1", "true")
            flipV = xfrm.get("flipV") in ("1", "true")
            x1 = x + (w if flipH else 0)
            x2 = x + (0 if flipH else w)
            y1 = y + (h if flipV else 0)
            y2 = y + (0 if flipV else h)
            d.line([x1, y1, x2, y2], fill=(46, 74, 122), width=max(1, int(DPI / 60)))
            ln = sh._element.spPr.find(qn("a:ln"))
            if ln is not None and ln.find(qn("a:tailEnd")) is not None:
                ang = math.atan2(y2 - y1, x2 - x1)
                L, aw = DPI / 11, DPI / 24
                d.polygon([(x2, y2),
                           (x2 - L * math.cos(ang) + aw * math.sin(ang),
                            y2 - L * math.sin(ang) - aw * math.cos(ang)),
                           (x2 - L * math.cos(ang) - aw * math.sin(ang),
                            y2 - L * math.sin(ang) + aw * math.cos(ang))],
                          fill=(46, 74, 122))
            continue

        try:
            fill = tuple(sh.fill.fore_color.rgb)
        except Exception:
            fill = None
        try:
            line = tuple(sh.line.color.rgb) if sh.line.width and sh.line.width.pt > 0 else None
        except Exception:
            line = None
        if fill:
            rects.append((sh.name, x, y, w, h))
        if fill or line:
            rad = 0.085 * DPI
            d.rounded_rectangle([x, y, x + w, y + h], radius=rad, fill=fill,
                                outline=line or None, width=max(1, int(DPI / 70)))

        if not sh.has_text_frame:
            continue
        lines = shape_text(sh)
        if not lines:
            continue

        rendered, total_h, max_over = [], 0, 0
        avail = w - 2 * 0.07 * DPI
        for (txt, size, bold, col, align, sb) in lines:
            f = font(size * DPI / 72, bold)
            tw = f.getlength(txt)
            max_over = max(max_over, tw - avail)
            lh = size * DPI / 72 * 1.32
            total_h += lh + sb * DPI / 72
            rendered.append((txt, f, tw, lh, col, align, sb))

        bp = sh.text_frame._txBody.find(qn("a:bodyPr"))
        vert = bp.get("vert") if bp is not None else None

        if vert in ("vert270", "vert"):
            avail_v = h - 2 * 0.05 * DPI
            over = max(t.getlength(txt) for (txt, t, _, _, _, _, _) in rendered) - avail_v
            if over > 2:
                problems.append(f"TEXT OVERFLOW ({over/DPI:.2f}in): {sh.name}")
            if total_h > w - 2 * 0.05 * DPI:
                problems.append(f"TEXT TALL in vertical block: {sh.name}")
            tmp = Image.new("RGBA", (max(1, int(h)), max(1, int(w))), (0, 0, 0, 0))
            td = ImageDraw.Draw(tmp)
            cy = w / 2 - total_h / 2 + 2
            for (txt, f, tw, lh, col, align, sb) in rendered:
                cy += sb * DPI / 72
                td.text(((h - tw) / 2, cy), txt, font=f, fill=col)
                cy += lh
            rot = tmp.rotate(90 if vert == "vert270" else -90, expand=True)
            img.paste(rot, (int(x), int(y)), rot)
            continue

        if max_over > 2:
            problems.append(f"TEXT OVERFLOW ({max_over/DPI:.2f}in): {sh.name} -> {lines[0][0][:40]}")
        if total_h > h - 2 * 0.03 * DPI + 1:
            problems.append(
                f"TEXT TALL ({total_h/DPI:.2f}in > {h/DPI:.2f}in): {sh.name} -> {lines[0][0][:40]}")

        cy = y + h / 2 - total_h / 2 + 2
        for (txt, f, tw, lh, col, align, sb) in rendered:
            cy += sb * DPI / 72
            if align == "RIGHT":
                tx = x + w - 0.07 * DPI - tw
            elif align == "LEFT":
                tx = x + 0.07 * DPI
            else:
                tx = x + w / 2 - tw / 2
            d.text((tx, cy), txt, font=f, fill=col)
            cy += lh

    for i in range(len(rects)):
        n1, x1, y1, w1, h1 = rects[i]
        for j in range(i + 1, len(rects)):
            n2, x2, y2, w2, h2 = rects[j]
            ox = min(x1 + w1, x2 + w2) - max(x1, x2)
            oy = min(y1 + h1, y2 + h2) - max(y1, y2)
            if ox > 2 and oy > 2:
                problems.append(f"OVERLAP {ox/DPI:.2f}x{oy/DPI:.2f}in: {n1} / {n2}")

    img.save(path)
    return problems


prs = Presentation(PPTX)
all_problems = []
for i, slide in enumerate(prs.slides, 1):
    out = f"artifacts/{PREFIX}{i}.png"
    all_problems += [f"{PREFIX}{i}: {p}" for p in draw_slide(slide, out)]
    print("wrote", out)

print("\n".join(all_problems) if all_problems else "no layout problems detected")
