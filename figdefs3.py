# -*- coding: utf-8 -*-
"""Figure 3.4 — prefix/target sample construction."""
from figkit import BLUE, GREEN, INK, LINE, MUTED, ORANGE, PINK, PURPLE, SAND, figure

RED = "#C00000"
LETTER_FC = [BLUE, GREEN, SAND, PINK, PURPLE, ORANGE]


@figure("fig_3_4_prefix_target", 10.0, 6.15)
def f34(fig):
    fig.title("شکل ۳.۴: فرآیند ساخت نمونه‌های پیشوند-به-هدف با برچسب‌های چندوظیفه‌ای", fs=15)

    w, h, g, x0 = 0.72, 0.6, 0.06, 3.0

    fig.text(0.15, 0.72, 2.6, 0.42, "**توالی کامل (Case):**", fs=11, align="r")
    for i, ch in enumerate("ABCDEF"):
        fig.box(x0 + i * (w + g), 0.7, w, h, ch, fc=LETTER_FC[i], fs=13, bold=True)

    fig.text(0.15, 1.45, 2.3, 0.62,
             "**ساخت نمونه‌های\nچندوظیفه‌ای:**", fs=11, align="r")

    rows = 4
    for r in range(rows):
        y = 2.05 + r * 0.66
        fig.text(0.15, y + 0.05, 2.6, 0.4, "**پیشوند %d:**" % (r + 1), fs=11, align="r")
        for i in range(r + 2):
            fig.box(x0 + i * (w + g), y, w, h, "ABCDEF"[i], fc=BLUE, fs=11,
                    color=INK)
        tgt = r + 2
        fig.box(x0 + tgt * (w + g), y, w, h, "ABCDEF"[tgt], fc=PINK, ec=RED,
                fs=11, bold=True)
        # small arrow from prefix to the target box
        fig.arrow([(x0 + tgt * (w + g) - 0.04, y + h / 2),
                   (x0 + tgt * (w + g) + 0.02, y + h / 2)], lw=1.2, color=RED)

    fig.text(0.15, 4.95, 2.3, 0.4, "**برچسب‌ها:**", fs=11, align="r")
    labs = [("فعالیت هدف", PINK), ("زمان باقی‌مانده", GREEN),
            ("پتانسیل بهبود", SAND), ("بردار گلوگاه", PINK)]
    xb = 2.6
    for t, fc in labs:
        fig.box(xb, 4.9, 1.7, 0.5, t, fc=fc, fs=10.5)
        xb += 1.7 + 0.12
