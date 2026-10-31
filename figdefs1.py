# -*- coding: utf-8 -*-
"""Figures 3.1 and 3.2 — overall architecture and preprocessing flow."""
from figkit import (BLUE, GREEN, GREY, INK, LINE, MUTED, ORANGE, PINK, PURPLE,
                    SAND, SEP, WHITE, bottom, cx, cy, figure, right)


@figure("fig_3_1_architecture", 10.0, 10.8)
def f31(fig):
    fig.title("شکل ۳.۱: نمای کلی معماری مدل سه‌جریانه پیشنهادی و جریان داده", fs=15)

    a = (1.85, 0.68, 6.3, 0.78)
    fig.box(*a, "**ورودی: پیشوند رویدادها**\n"
                "(فعالیت، فعالیت پیشین، زمان، نقش، فراوانی، موقعیت نسبی)",
            fc=SAND, fs=11)
    b = (0.85, 1.66, 8.3, 0.92)
    fig.box(*b, "**لایه تعبیه ورودی چندوجهی**\n"
                "(Activity + PrevActivity + Position + TimeDelta + CumTime + Role + Freq + RelPos)",
            fc=GREEN, fs=11)
    fig.arrow([(cx(a), bottom(a)), (cx(b), b[1])])

    fig.label(5.0, 2.78, "سه جریان موازی پردازش", fs=12, bold=True, color=LINE, w=4.0)

    fig.label(5.0, 2.78, "سه جریان موازی پردازش", fs=12, bold=True, color=LINE, w=4.0)

    y0, hc, wc = 3.02, 3.6, 2.9
    cols = [(0.35, BLUE), (3.55, SAND), (6.75, PURPLE)]
    for (x, fc) in cols:
        fig.box(x, y0, wc, hc, "", fc=fc, name="stream")
    fig.box(0.35, y0, wc, 0.4, "**جریان ۱: ترانسفورمر**", fc=BLUE, ec=None, fs=11)
    fig.box(3.55, y0, wc, 0.4, "**جریان ۲: TCN**", fc=SAND, ec=None, fs=11)
    fig.box(6.75, y0, wc, 0.4, "**جریان ۳: GNN**", fc=PURPLE, ec=None, fs=11)

    for i in range(6):
        fig.box(0.55, 3.52 + i * 0.5, 2.5, 0.42,
                "لایه %d: خودتوجهی علی + FFN" % (i + 1), fs=9.5, radius=0.03)

    for i, d in enumerate((4, 2, 1)):
        fig.box(3.75, 4.05 + i * 0.62, 2.5, 0.5, "Conv1D (d=%d)" % d, fc=SAND, fs=10.5)

    fig.box(6.95, 3.55, 2.5, 1.0, "گراف پیشوند\n(CLS + رویدادها + یال‌ها)", fc=PURPLE, fs=10)
    fig.box(6.95, 4.72, 2.5, 1.0, "دو لایه پیچش گرافی\nبا مکانیزم دروازه‌ای", fc=PURPLE, fs=10)

    for x in (1.8, 5.0, 8.2):
        fig.arrow([(cx(b), bottom(b)), (x, y0)])

    fu = (2.25, 6.9, 5.5, 0.88)
    fig.box(*fu, "**ماژول ادغام سه‌گانه**\n"
                 "(توجه متقابل Transformer + TCN، ادغام با GNN)", fc=PINK, fs=11)
    fig.arrow([(1.8, y0 + hc), (3.1, fu[1])])
    fig.arrow([(5.0, y0 + hc), (5.0, fu[1])])
    fig.arrow([(8.2, y0 + hc), (6.9, fu[1])])

    sh = (2.15, 8.05, 5.7, 0.66)
    fig.box(*sh, "**سر مشترک**\nLayerNorm → Linear → GELU → Dropout → Linear → GELU",
            fc=SAND, fs=11)
    fig.arrow([(5.0, bottom(fu)), (5.0, sh[1])])

    heads = [
        ("**سر ۱:**\nفعالیت بعدی\n(Softmax)", BLUE),
        ("**سر ۲:**\nزمان باقی‌مانده\n(رگرسیون)", GREEN),
        ("**سر ۳:**\nپتانسیل بهبود\n(tanh)", SAND),
        ("**سر ۴:**\nگلوگاه\n(Sigmoid)", PINK),
    ]
    xs = [7.49, 5.12, 2.75, 0.38]
    for (t, fc), x in zip(heads, xs):
        fig.box(x, 8.9, 2.25, 0.82, t, fc=fc, fs=9.5)
        fig.arrow([(5.0, bottom(sh)), (x + 1.125, 8.88)], lw=1.3)

    fig.text(0.6, 9.86, 8.8, 0.3,
             "گره‌بندی وزنی: وزن سر فعالیت همان ماتریس تعبیه فعالیت است",
             fs=10, color=MUTED, align="ctr")

    fig.box(1.3, 10.16, 7.4, 0.58,
            "**خروجی: توزیع احتمال فعالیت + زمان باقی‌مانده + بهبود تأخیر + بردار گلوگاه**",
            fc=PINK, fs=11)

    fig.box(3.15, 2.57, 3.7, 0.34, "", fc=WHITE, ec=None, name="mask")
    fig.label(5.0, 2.74, "سه جریان موازی پردازش", fs=12, bold=True, color=LINE,
              w=4.0)


@figure("fig_3_2_preprocessing", 10.0, 6.7)
def f32(fig):
    fig.title("شکل ۳.۲: جریان پیش‌پردازش رویدادنگار و استخراج پیشوندها", fs=15)

    y, h, w = 0.85, 0.9, 2.2
    xs = [7.65, 5.15, 2.65, 0.15]
    row = [
        ("**رویدادنگار خام**\n(BPI Challenge 2012)", SAND),
        ("استخراج Caseها\nو رویدادها", BLUE),
        ("مرتب‌سازی\nبر اساس زمان", BLUE),
        ("توالی مرتب", GREEN),
    ]
    for (t, fc), x in zip(row, xs):
        fig.box(x, y, w, h, t, fc=fc, fs=11)

    for i in range(3):
        fig.arrow([(xs[i], y + h / 2), (xs[i + 1] + w, y + h / 2)], lw=1.3)

    stats = (0.15, 2.15, 4.6, 0.95)
    fig.box(*stats, "**محاسبه آمار Case**\n(مدت کل، مدت هر فعالیت، فراوانی، زمان انتظار)",
            fc=SAND, fs=10.5)
    fig.arrow([(1.25, y + h), (1.25, stats[1])])

    neck = (0.15, 3.45, 4.6, 0.95)
    fig.box(*neck, "**شناسایی گلوگاه‌ها**\n(صدک ۷۵ زمان انتظار)", fc=PINK, fs=10.5)
    fig.arrow([(cx(stats), bottom(stats)), (cx(neck), neck[1])])

    pre = (5.15, 3.45, 4.7, 0.95)
    fig.box(*pre, "**استخراج پیشوندها**\n(min_prefix_len = 2)", fc=PURPLE, fs=10.5)
    fig.arrow([(right(neck), cy(neck)), (pre[0], cy(neck))])

    labs = (0.15, 4.85, 9.7, 0.8)
    fig.box(*labs, "**برچسب‌های چندوظیفه‌ای:** فعالیت بعدی + زمان باقی‌مانده "
                   "+ پتانسیل بهبود تأخیر + بردار گلوگاه", fc=PINK, fs=11)
    fig.arrow([(cx(pre), bottom(pre)), (cx(pre), labs[1])])

    out = (2.4, 6.0, 5.2, 0.6)
    fig.box(*out, "**نمونه‌های آموزشی آماده**", fc=GREEN, fs=12)
    fig.arrow([(5.0, bottom(labs)), (5.0, out[1])])
