# -*- coding: utf-8 -*-
"""Figure 3.15 — the tri-fusion module."""
from figkit import (BLUE, GREEN, INK, LINE, MUTED, PINK, PURPLE, SAND, bottom,
                    cx, cy, figure, right)


@figure("fig_3_15_tri_fusion", 10.0, 6.5)
def f315(fig):
    fig.title("شکل ۳.۱۵: ماژول ادغام سه‌گانه و نحوه ترکیب سه جریان", fs=15)

    h12 = (6.7, 1.1, 3.0, 0.85)
    gnn = (0.35, 1.1, 2.8, 0.85)
    fig.box(*h12, "**خروجی ترکیبی**\n(Transformer + TCN (h_12", fc=BLUE, fs=11)
    fig.box(*gnn, "**خروجی GNN**\n(h_gnn)", fc=PURPLE, fs=11)

    cat = (3.25, 2.35, 4.0, 0.95)
    fig.box(*cat, "**الحاق + حاصل‌ضرب عنصری**\n[h_12 ; h_gnn ; h_12 ⊙ h_gnn]",
            fc=SAND, fs=11)
    fig.arrow([(h12[0], cy(h12)), (right(cat) - 0.35, cat[1])])
    fig.arrow([(right(gnn), cy(gnn)), (cat[0] + 0.35, cat[1])])

    l1 = (3.4, 3.6, 3.7, 0.85)
    fig.box(*l1, "**Linear (3·d → 2·d)**\n**+ GELU**", fc=SAND, fs=11.5)
    fig.arrow([(cx(cat), bottom(cat)), (cx(l1), l1[1])])

    l2 = (3.4, 4.7, 3.7, 0.85)
    fig.box(*l2, "**Linear (2·d → d)**\n**+ LayerNorm**", fc=GREEN, fs=11.5)
    fig.arrow([(cx(l1), bottom(l1)), (cx(l2), l2[1])])

    out = (3.5, 5.75, 3.5, 0.6)
    fig.box(*out, "**نمایش ادغام‌شده نهایی**", fc=PINK, fs=12)
    fig.arrow([(cx(l2), bottom(l2)), (cx(out), out[1])])
