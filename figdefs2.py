# -*- coding: utf-8 -*-
"""Figure 3.3 — the four output heads and their loss functions."""
from figkit import BLUE, GREEN, GREEN as G, INK, LINE, MUTED, PINK, SAND, bottom, cx, figure

RED = "#C00000"


@figure("fig_3_3_four_heads", 10.0, 5.8)
def f33(fig):
    fig.title("شکل ۳.۳: ساختار چهار سر خروجی مدل چندوظیفه‌ای و برچسب‌های هر وظیفه", fs=15)

    top = (3.1, 0.62, 3.8, 0.62)
    fig.box(*top, "**نمایش تجمیع‌شده** (d_model)", fc=SAND, fs=12)

    shared = (2.6, 1.5, 4.8, 0.72)
    fig.box(*shared, "**سر مشترک چندلایه**", fc=SAND, fs=12)
    fig.arrow([(5.0, bottom(top)), (5.0, shared[1])])

    heads = [
        ("**سر ۱:**\nفعالیت بعدی", BLUE),
        ("**سر ۲:**\nزمان باقی‌مانده", GREEN),
        ("**سر ۳:**\nپتانسیل بهبود", SAND),
        ("**سر ۴:**\nگلوگاه", PINK),
    ]
    losses = [
        "CrossEntropy\n+ Label Smoothing\n+ Class Weights",
        "Huber Loss\n(رگرسیون)",
        "Huber Loss\n+ tanh",
        "BCE Loss\n(دودویی)",
    ]
    xs = [7.525, 5.075, 2.625, 0.175]
    for (t, fc), x, ls in zip(heads, xs, losses):
        fig.box(x, 2.55, 2.3, 0.95, t, fc=fc, fs=11.5)
        fig.arrow([(5.0, bottom(shared)), (x + 1.15, 2.53)], lw=1.3)
        fig.box(x, 3.78, 2.3, 0.78, ls, fc=None, ec=LINE, fs=9.5, shape="rect",
                color=MUTED, radius=0.0)

    fig.box(1.55, 4.85, 6.9, 0.44,
            "ضرایب: λ_activity=1.0، λ_remaining=0.3، λ_improvement=0.3، λ_bottleneck=0.1",
            fc=None, ec=RED, fs=10.5, color=RED, radius=0.02)

    fig.text(0.4, 5.4, 9.2, 0.32,
             "**خروجی نهایی: تابع زیان چندوظیفه‌ای = مجموع وزنی چهار مؤلفه**",
             fs=12, color=INK, align="ctr")
