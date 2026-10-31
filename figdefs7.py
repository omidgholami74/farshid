# -*- coding: utf-8 -*-
"""Figure 3.10 — causal (masked) vs. full attention matrix."""
from figkit import INK, LINE, MUTED, WHITE, figure

NAVY = "#1F3864"
RED = "#C00000"


def grid(fig, x0, y0, causal):
    cw, ch, g = 0.62, 0.4, 0.03
    for r in range(6):
        for c in range(6):
            x = x0 + c * (cw + g)
            y = y0 + r * (ch + g)
            masked = causal and c > r
            if masked:
                fig.box(x, y, cw, ch, "−∞", fc=WHITE, ec="#BFBFBF", fs=11,
                        color=RED, shape="rect", lw=0.75)
            else:
                fig.box(x, y, cw, ch, "1", fc=NAVY, ec=NAVY, fs=11,
                        color=WHITE, shape="rect", lw=0.75)
    for c in range(6):
        fig.text(x0 + c * (cw + g), y0 + 6 * (ch + g) + 0.02, cw, 0.26,
                 str(c), fs=10, align="ctr", color=INK)
    for r in range(6):
        fig.text(x0 - 0.5, y0 + r * (ch + g), 0.45, ch, str(r), fs=10,
                 align="r", color=INK)
    fig.text(x0, y0 + 6 * (ch + g) + 0.3, 6 * (cw + g) - g, 0.3,
             "Key (موقعیت)", fs=10, align="ctr", color=INK)
    fig.label(x0 - 0.5, y0 + 3 * (ch + g) - 0.1, "Query (موقعیت)", fs=10,
              rot=270, w=1.2, h=0.3)


@figure("fig_3_10_causal_attention", 10.0, 4.95)
def f310(fig):
    fig.title("شکل ۳.۱۰: مقایسه ماتریس توجه کامل و ماتریس توجه علّی", fs=15)
    fig.text(0.3, 0.62, 4.4, 0.32, "**ماتریس توجه کامل (بدون ماسک)**", fs=12,
             align="ctr")
    fig.text(5.35, 0.62, 4.4, 0.32, "**ماتریس توجه علّی (با ماسک)**", fs=12,
             align="ctr")
    grid(fig, 1.15, 1.15, causal=False)
    grid(fig, 5.6, 1.15, causal=True)
