# -*- coding: utf-8 -*-
"""Figure 3.11 — TCN block with dilations 1, 2, 4."""
from figkit import (BLUE, GREEN, INK, LINE, MUTED, PINK, PURPLE, SAND, bottom,
                    cx, figure)

RED = "#C00000"


@figure("fig_3_11_tcn_block", 10.0, 6.35)
def f311(fig):
    fig.title("شکل ۳.۱۱: ساختار بلوک‌های پیچشی زمانی با dilations مختلف", fs=15)

    x, w = 2.6, 4.8
    src = (x + 0.8, 0.65, w - 1.6, 0.55)
    fig.box(*src, "**ورودی جریان TCN**", fc=SAND, fs=12)

    convs = [("**Conv1D (kernel=3, dilation=1)**", SAND),
             ("**Conv1D (kernel=3, dilation=2)**", PINK),
             ("**Conv1D (kernel=3, dilation=4)**", PURPLE)]
    y = 1.5
    prev = src
    for t, fc in convs:
        c = (x, y, w, 0.85)
        fig.box(*c, t, fc=fc, fs=12)
        fig.arrow([(cx(prev), bottom(prev)), (cx(c), c[1])])
        s = (x, y + 0.9, w, 0.35)
        fig.box(*s, "LayerNorm + GELU + Residual + Mask", fc=GREEN, fs=9.5)
        prev = s
        y += 1.35

    out = (x + 0.35, y - 0.13, w - 0.7, 0.6)
    fig.box(*out, "**خروجی جریان TCN**", fc=PINK, fs=12)
    fig.arrow([(cx(prev), bottom(prev)), (cx(out), out[1])])

    fig.box(7.85, 2.55, 1.95, 1.2,
            "• میدان پذیرش: ۱+۲+۴ = ۷ رویداد\n• پردازش موازی\n• الگوهای محلی",
            fc=None, ec=LINE, fs=10, align="r", radius=0.02, color=MUTED)
