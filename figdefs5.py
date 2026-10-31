# -*- coding: utf-8 -*-
"""Figures 3.7 (activity frequency) and 3.8 (multi-faceted input embedding)."""
from figchart import bars
from figkit import (BLUE, GREEN, INK, LINE, MUTED, ORANGE, PINK, PURPLE, SAND,
                    bottom, cx, cy, figure, right)

RED = "#C00000"
TEAL = "#D6E9E4"

NAMES = ["A%d" % i for i in range(1, 21)]
COUNTS = [1200, 600, 500, 300, 300, 300, 200] + [100] * 13


@figure("fig_3_7_activity_distribution", 10.0, 5.2)
def f37(fig):
    fig.title("شکل ۳.۷: توزیع فراوانی فعالیت‌ها و کلاس‌های کم‌فراوان", fs=15)
    cats = list(reversed(NAMES))
    vals = list(reversed(COUNTS))
    bars(fig, 0.5, 0.6, 9.1, 3.75, cats, vals, color="#5B9BD5",
         xtitle="فعالیت", ytitle="فراوانی", fs=9, gap=40, ymax=1300,
         data_labels=True)
    fig.text(0.3, 4.5, 9.4, 0.32,
             "خط مبنای صدک ۳۰ فراوانی برابر ۱۰۰ است؛ کلاس‌های A8 تا A20 کم‌فراوان‌اند "
             "و در زیان آنتروپی متقاطع وزن بیشتری می‌گیرند",
             fs=10, color=MUTED, align="ctr")


@figure("fig_3_8_embedding_layer", 10.0, 6.2)
def f38(fig):
    fig.title("شکل ۳.۸: ساختار لایه تعبیه ورودی چندوجهی و اجزای آن", fs=15)

    items = [
        ("**تعبیه فعالیت**\n(Activity Embedding)", BLUE),
        ("**تعبیه فعالیت پیشین**\n(Prev Activity Embedding)", GREEN),
        ("**تعبیه موقعیت مطلق**\n(Position Embedding)", SAND),
        ("**رمزگذاری بازه زمانی**\n(Time Delta Encoding)", PINK),
        ("**رمزگذاری زمان تجمعی**\n(Cumulative Time Encoding)", PURPLE),
        ("**رمزگذاری نقش رویداد**\n(Role: First/Last)", ORANGE),
        ("**رمزگذاری فراوانی**\n(Activity Frequency)", TEAL),
        ("**رمزگذاری موقعیت نسبی**\n(Relative Position)", PINK),
    ]
    boxes = []
    for i, (t, fc) in enumerate(items):
        y = 0.68 + i * 0.63
        boxes.append((0.35, y, 4.0, 0.55))
        fig.box(0.35, y, 4.0, 0.55, t, fc=fc, fs=10.5)

    sig = (4.95, 2.85, 0.72, 0.72)
    fig.box(*sig, "**Σ**", fc=PINK, ec=RED, fs=18, shape="round", radius=0.36,
            lw=1.6)
    for bx in boxes:
        fig.arrow([(right(bx), cy(bx)), (sig[0] - 0.02, cy(sig))], lw=1.2)

    ln = (6.15, 2.82, 1.85, 0.78)
    fig.box(*ln, "**LayerNorm**\n**+ Dropout**", fc=GREEN, fs=11.5)
    fig.arrow([(right(sig), cy(sig)), (ln[0], cy(ln))])

    out = (8.35, 2.82, 1.4, 0.78)
    fig.box(*out, "**به**\n**رمزگذار**", fc=SAND, fs=12)
    fig.arrow([(right(ln), cy(ln)), (out[0], cy(out))])
