# -*- coding: utf-8 -*-
"""Figure 3.12 — cross-attention fusion of the Transformer and TCN streams."""
from figkit import (BLUE, GREEN, INK, LINE, MUTED, PINK, PURPLE, SAND, bottom,
                    cx, cy, figure, right)


@figure("fig_3_12_cross_attention", 10.0, 6.4)
def f312(fig):
    fig.title("شکل ۳.۱۲: ماژول ادغام توجه متقابل میان جریان ترانسفورمر و TCN", fs=15)

    q = (7.0, 1.2, 2.85, 0.85)
    kv = (7.0, 2.4, 2.85, 0.85)
    fig.box(*q, "**خروجی ترانسفورمر**\n(Query)", fc=BLUE, fs=11.5)
    fig.box(*kv, "**خروجی TCN**\n(Key, Value)", fc=SAND, fs=11.5)

    at = (3.55, 1.8, 2.95, 0.95)
    fig.box(*at, "**Multi-Head**\n**Cross-Attention**", fc=PINK, fs=12)
    fig.arrow([(q[0], cy(q)), (right(at) + 0.02, at[1] + 0.22)])
    fig.arrow([(kv[0], cy(kv)), (right(at) + 0.02, bottom(at) - 0.22)])

    an = (2.7, 3.15, 4.6, 0.68)
    fig.box(*an, "Add & Norm", fc=GREEN, fs=12)
    fig.arrow([(cx(at), bottom(at)), (cx(an), an[1])])

    ff = (2.7, 4.2, 4.6, 0.68)
    fig.box(*ff, "Feed-Forward + Add & Norm", fc=SAND, fs=12)
    fig.arrow([(cx(an), bottom(an)), (cx(ff), ff[1])])

    out = (3.2, 5.25, 3.6, 0.62)
    fig.box(*out, "**نمایش ترکیبی ۱۲**", fc=GREEN, fs=12)
    fig.arrow([(cx(ff), bottom(ff)), (cx(out), out[1])])

    fig.box(7.05, 3.5, 2.8, 0.6, "ادغام اطلاعات سراسری و محلی", fc=BLUE, fs=10.5)
