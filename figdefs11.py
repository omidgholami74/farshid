# -*- coding: utf-8 -*-
"""Figure 3.14 — one gated graph convolution layer."""
from figkit import (BLUE, GREEN, INK, LINE, MUTED, PINK, PURPLE, SAND, bottom,
                    cx, figure)


@figure("fig_3_14_graph_conv", 10.0, 6.45)
def f314(fig):
    fig.title("شکل ۳.۱۴: ساختار یک لایه پیچش گرافی با مکانیزم دروازه‌ای", fs=15)

    src = (3.2, 0.65, 3.6, 0.6)
    fig.box(*src, "**ورودی لایه (نمایش گره‌ها)**", fc=SAND, fs=11.5)

    agg = (1.8, 1.5, 6.4, 0.85)
    fig.box(*agg, "**تجمیع پیام از گره‌های همسایه**\n(Mean Aggregation)", fc=BLUE,
            fs=11.5)

    gate = (1.8, 2.65, 6.4, 0.85)
    fig.box(*gate, "**لایه خطی + مکانیزم دروازه‌ای** (Sigmoid Gate)", fc=SAND,
            fs=11.5)

    nm = (1.8, 3.8, 6.4, 0.7)
    fig.box(*nm, "**LayerNorm + GELU + Dropout**", fc=GREEN, fs=11.5)

    res = (2.7, 4.8, 4.6, 0.6)
    fig.box(*res, "اتصال باقی‌مانده", fc=PINK, fs=11.5)

    out = (2.6, 5.7, 4.8, 0.6)
    fig.box(*out, "**خروجی لایه (نمایش به‌روز گره‌ها)**", fc=GREEN, fs=11.5)

    for a, b in ((src, agg), (agg, gate), (gate, nm), (nm, res), (res, out)):
        fig.arrow([(cx(a), bottom(a)), (cx(b), b[1])])

    fig.box(8.15, 2.55, 1.65, 1.05,
            "**مکانیزم دروازه‌ای:**\ng = σ(W_g · x)\nh = g ⊙ (W_l · agg)",
            fc=None, ec=LINE, fs=9, align="r", radius=0.02, color=MUTED)
