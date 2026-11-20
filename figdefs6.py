# -*- coding: utf-8 -*-
"""Figure 3.9 — one Transformer encoder layer and its parts."""
from figkit import (BLUE, GREEN, INK, LINE, MUTED, PINK, PURPLE, SAND, bottom,
                    figure)

RED = "#C00000"


@figure("fig_3_9_transformer_layer", 10.0, 7.5)
def f39(fig):
    fig.title("شکل ۳.۹: ساختار یک لایه رمزگذار ترانسفورمر و اجزای آن", fs=15)

    x, w = 1.6, 6.4
    b1 = (x + 0.8, 0.65, w - 1.6, 0.58)
    fig.box(*b1, "**ورودی لایه** (d_model)", fc=SAND, fs=12)

    b2 = (x, 1.55, w, 0.85)
    fig.box(*b2, "**خودتوجهی چندسری**\n(Multi-Head Self-Attention)", fc=BLUE, fs=12)

    b3 = (x, 2.72, w, 0.62)
    fig.box(*b3, "اتصال باقی‌مانده + LayerNorm", fc=GREEN, fs=11.5)

    b4 = (x, 3.6, w, 0.85)
    fig.box(*b4, "**شبکه پیش‌خور**\nLinear → GELU → Linear", fc=SAND, fs=12)

    b5 = (x, 4.75, w, 0.62)
    fig.box(*b5, "اتصال باقی‌مانده + LayerNorm", fc=GREEN, fs=11.5)

    b6 = (x + 0.55, 5.62, w - 1.1, 0.6)
    fig.box(*b6, "**خروجی لایه**", fc=PINK, fs=12)

    for a, b in ((b1, b2), (b2, b3), (b3, b4), (b4, b5), (b5, b6)):
        cx_ = a[0] + a[2] / 2
        fig.arrow([(cx_, bottom(a)), (cx_, b[1])])

    fig.box(8.35, 1.5, 1.5, 0.95,
            "• محاسبه ماتریس توجه\n• ۸ سر توجه\n• ماسک علّی", fc=None, ec=LINE,
            fs=9.5, align="r", radius=0.02, color=MUTED)
    fig.box(8.35, 3.5, 1.5, 0.95,
            "• گسترش به ۱٫۰۲۴\n• فعال‌سازی GELU\n• فشرده‌سازی به ۲۵۶",
            fc=None, ec=RED, fs=9.5, align="r", radius=0.02, color=MUTED)

    fig.box(2.6, 6.7, 4.4, 0.52, "**۶ لایه به‌صورت پشته‌ای**", fc=BLUE, fs=12)
