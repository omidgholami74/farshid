# -*- coding: utf-8 -*-
"""Figure 3.13 — prefix graph and its edge types."""
from figkit import (BLUE, GREEN, INK, LINE, MUTED, PINK, PURPLE, SAND, bottom,
                    cx, cy, figure)

RED = "#C00000"
GREEN_EDGE = "#00B050"
ORANGE_EDGE = "#ED7D31"


@figure("fig_3_13_prefix_graph", 10.0, 6.7)
def f313(fig):
    fig.title("شکل ۳.۱۳: ساختار گراف پیشوند با انواع یال‌ها", fs=15)
    fig.label(5.0, 0.62, "**گراف پیشوند: انواع یال‌ها**", fs=12, color=LINE, w=4.0)

    cls = (4.6, 0.95, 0.8, 0.7)
    fig.box(*cls, "**CLS**", fc=PINK, ec=RED, fs=11, radius=0.34, lw=1.8,
            shape="round")

    letters = ["A", "B", "C", "A", "D", "A"]
    colors = [BLUE, GREEN, SAND, BLUE, PURPLE, BLUE]
    nodes = []
    for i, (ch, fc) in enumerate(zip(letters, colors)):
        x = 0.85 + i * 1.63
        b = (x, 2.5, 0.75, 0.75)
        nodes.append(b)
        fig.box(*b, "**%s**" % ch, fc=fc, fs=13, radius=0.36, lw=1.6)

    for b in nodes:
        fig.line([(cx(cls), bottom(cls)), (cx(b), b[1])], lw=1.2, dash=True,
                 color="#E8A0A0")

    for a, b in zip(nodes[:-1], nodes[1:]):
        fig.line([(a[0] + a[2], cy(a) - 0.05), (b[0], cy(b) - 0.05)], lw=1.3)

    # repeat-activity edges between the three "A" nodes
    for i, j in ((0, 3), (3, 5)):
        a, b = nodes[i], nodes[j]
        y = 3.5
        fig.line([(cx(a), bottom(a)), (cx(a), y), (cx(b), y), (cx(b), bottom(b))],
                 lw=1.6, color=GREEN_EDGE)
    # temporal-neighbourhood edge
    a, b = nodes[1], nodes[2]
    y = 3.75
    fig.line([(cx(a), bottom(a)), (cx(a), y), (cx(b), y), (cx(b), bottom(b))],
             lw=1.6, color=ORANGE_EDGE)

    legend = [("یال CLS (سراسری)", RED, True),
              ("یال پیروی مستقیم", LINE, False),
              ("یال تکرار فعالیت", GREEN_EDGE, False),
              ("یال مجاورت زمانی", ORANGE_EDGE, False)]
    for i, (t, c, dashed) in enumerate(legend):
        y = 4.35 + i * 0.45
        fig.line([(0.55, y), (1.45, y)], lw=2.0 if not dashed else 1.3,
                 dash=dashed, color=c)
        fig.text(1.6, y - 0.16, 4.2, 0.32, t, fs=11, align="l", color=INK)

    fig.box(2.5, 6.0, 5.0, 0.5,
            "**ویژگی گره:** فعالیت + بازه زمانی نرمال + موقعیت نرمال", fc=SAND,
            fs=11)
