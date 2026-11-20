# -*- coding: utf-8 -*-
"""Figures 3.16 to 3.22 — heads, tying, loss, schedules, bottleneck, demo."""
import math

from figchart import bars, lines, xy
from figkit import (BLUE, GREEN, GREY, INK, LINE, MUTED, ORANGE, PINK, PURPLE,
                    SAND, bottom, cx, cy, figure, right)

RED = "#C00000"
DORANGE = "#C55A11"


# ---------------------------------------------------------------- fig 3.16
@figure("fig_3_16_shared_heads", 10.0, 5.6)
def f316(fig):
    fig.title("شکل ۳.۱۶: ساختار سر مشترک و چهار سر تخصصی خروجی", fs=15)

    top = (3.2, 0.62, 3.6, 0.6)
    fig.box(*top, "**نمایش ادغام‌شده**", fc=SAND, fs=12)

    sh = (2.1, 1.45, 5.8, 0.92)
    fig.box(*sh, "**سر مشترک**\nLayerNorm → Linear → GELU → Dropout → Linear → GELU",
            fc=SAND, fs=11.5)
    fig.arrow([(cx(top), bottom(top)), (cx(sh), sh[1])])

    heads = [
        ("**سر ۱**\nفعالیت بعدی\nLinear → Softmax", BLUE),
        ("**سر ۲**\nزمان باقی‌مانده\nLinear → Scalar", GREEN),
        ("**سر ۳**\nبهبود تأخیر\nLinear → tanh", SAND),
        ("**سر ۴**\nگلوگاه\nLinear → Logits", PINK),
    ]
    outs = ["توزیع احتمال\n(تعداد فعالیت)", "مقدار اسکالر\n(log1p نرمال‌شده)",
            "مقدار اسکالر\n(tanh نرمال‌شده)", "بردار لوجیت\n(برای هر توکن)"]
    xs = [7.55, 5.1, 2.65, 0.2]
    for (t, fc), o, x in zip(heads, outs, xs):
        fig.box(x, 2.65, 2.3, 0.98, t, fc=fc, fs=11)
        fig.arrow([(cx(sh), bottom(sh)), (x + 1.15, 2.63)], lw=1.3)
        fig.box(x, 3.8, 2.3, 0.72, o, fc=None, ec=LINE, fs=10, shape="rect",
                color=MUTED, radius=0)

    fig.box(2.4, 4.8, 5.2, 0.5,
            "**گره‌بندی وزنی:** فعالیت بعدی ↔ تعبیه فعالیت", fc=PINK, ec=RED,
            fs=11, color=RED)


# ---------------------------------------------------------------- fig 3.17
@figure("fig_3_17_weight_tying", 10.0, 5.4)
def f317(fig):
    fig.title("شکل ۳.۱۷: گره‌بندی وزنی میان لایه تعبیه فعالیت و سر خروجی", fs=15)

    emb = (0.45, 0.95, 4.2, 1.05)
    hd = (5.35, 0.95, 4.2, 1.05)
    fig.box(*emb, "**لایه تعبیه فعالیت**\n(num_activities × d_model)", fc=BLUE,
            fs=11.5)
    fig.box(*hd, "**سر خروجی فعالیت**\n(d_model × num_activities)", fc=SAND,
            fs=11.5)

    fig.line([(4.75, 1.47), (5.25, 1.47)], lw=2.0, dash=True, color=RED)
    fig.box(4.25, 0.45, 1.5, 0.42, "**اشتراک وزن**", fc=PINK, ec=RED, fs=10.5,
            color=RED)

    fig.text(5.0, 2.3, 4.6, 0.34, "**مزایای گره‌بندی وزنی:**", fs=12,
             align="r")
    bullets = [
        "کاهش تعداد پارامترها (۵۰٪ در این دو لایه)",
        "بهبود تعمیم‌پذیری",
        "هم‌راستایی فضای تعبیه و فضای خروجی",
        "کاهش حافظه مصرفی",
        "جلوگیری از بیش‌برازش",
    ]
    for i, b in enumerate(bullets):
        fig.text(1.0, 2.78 + i * 0.46, 8.6, 0.34, "• " + b, fs=11.5,
                 align="r")


# ---------------------------------------------------------------- fig 3.18
@figure("fig_3_18_multitask_loss", 10.0, 5.8)
def f318(fig):
    fig.title("شکل ۳.۱۸: ساختار تابع زیان چندوظیفه‌ای و وزن‌های هر مؤلفه", fs=15)

    parts = [
        ("**L_activity**\nCrossEntropy\n+ Label Smoothing\n+ Class Weights",
         BLUE, "λ = 1.0"),
        ("**L_remaining**\nHuber Loss\n(δ=1.0)", GREEN, "λ = 0.3"),
        ("**L_improvement**\nHuber Loss\n+ tanh", SAND, "λ = 0.3"),
        ("**L_bottleneck**\nBinary CE\n(میانه زمان)", PINK, "λ = 0.1"),
    ]
    xs = [7.55, 5.1, 2.65, 0.2]
    centers = []
    for (t, fc, lam), x in zip(parts, xs):
        fig.box(x, 0.62, 2.3, 1.62, t, fc=fc, fs=11)
        lam_box = (x + 0.35, 2.42, 1.6, 0.5)
        fig.box(*lam_box, "**%s**" % lam, fc=None, ec=RED, fs=11, color=RED,
                shape="rect", radius=0)
        centers.append(cx(lam_box))

    total = (0.85, 3.55, 8.3, 0.9)
    fig.box(*total, "**L_total = λ_activity · L_activity + λ_remaining · L_remaining "
                    "+ λ_improvement · L_improvement + λ_bottleneck · L_bottleneck**",
            fc=PINK, fs=9.5)
    for c in centers:
        fig.arrow([(c, 2.94), (c, total[1])], lw=1.3)

    out = (2.6, 4.9, 4.8, 0.62)
    fig.box(*out, "**پس‌انتشار و به‌روزرسانی وزن‌ها**", fc=GREEN, fs=12)
    fig.arrow([(cx(total), bottom(total)), (cx(out), out[1])])


# ---------------------------------------------------------------- fig 3.19
def _lr(step, base=3.0e-04, warm=150, total=1000):
    if step <= warm:
        return base * step / warm
    return base * 0.5 * (1 + math.cos(math.pi * (step - warm) / (total - warm)))


@figure("fig_3_19_lr_scheduler", 10.0, 4.8)
def f319(fig):
    fig.title("شکل ۳.۱۹: زمان‌بند نرخ یادگیری — گرم‌کردن خطی + کاهش کسینوسی",
              fs=15)
    steps = list(range(0, 1001, 10))
    vals = [_lr(s) for s in steps]
    xy(fig, 0.9, 0.72, 7.0, 3.5, steps, vals, color="#1F3864", lw=2.2, fs=9,
       xtitle="مرحله آموزش (Step)", ytitle="نرخ یادگیری")
    fig.chart_gap(0.9, 0.72, 7.0, 3.5, "نمودار نرخ یادگیری")

    fig.box(8.1, 1.15, 1.7, 0.5, "Base LR = 3.0e-04", fc=None, ec=LINE, fs=9.5,
            shape="rect", radius=0, color=INK)
    fig.box(8.1, 1.8, 1.7, 0.85, "**Warmup = 150 steps**\n(افزایش خطی)", fc=None,
            ec=RED, fs=9.5, shape="rect", radius=0, color=RED)


# ---------------------------------------------------------------- fig 3.20
@figure("fig_3_20_swa", 10.0, 5.5)
def f320(fig):
    fig.title("شکل ۳.۲۰: فرآیند میانگین‌گیری وزنی تصادفی (SWA) در طول آموزش",
              fs=15)
    epochs = list(range(0, 147))
    pre, post, mean = [], [], []
    for e in epochs:
        if e < 80:
            v = 50.5 + 33.4 * (1 - math.exp(-e / 26.0)) + 0.55 * math.sin(e * 1.7) \
                + 0.35 * math.sin(e * 0.55)
            pre.append(round(v, 2))
            post.append(None)
        else:
            v = 83.8 + 0.85 * math.sin(e * 1.15) + 0.45 * math.sin(e * 0.5)
            pre.append(None)
            post.append(round(v, 2))
        mean.append(84.48)

    lines(fig, 0.9, 0.72, 8.2, 3.75, [str(e) for e in epochs],
          [dict(name="دقت اعتبارسنجی (قبل از SWA)", vals=pre, color="#5B9BD5",
                lw=2.0),
           dict(name="دقت اعتبارسنجی (فاز SWA)", vals=post, color="#00B050",
                lw=2.0),
           dict(name="میانگین SWA = 84.48٪", vals=mean, color="#C00000",
                lw=1.6, dash=True)],
          fs=8.5, ymin=48, ymax=88, xtitle="دوره (Epoch)",
          ytitle="دقت اعتبارسنجی (٪)", legend=True)
    fig.chart_gap(0.9, 0.72, 8.2, 3.75, "نمودار SWA")
    fig.text(0.4, 4.75, 9.2, 0.32,
             "فعال‌سازی SWA از دوره ۸۰؛ میانگین وزن‌ها در ۳۰ دوره پایانی گرفته می‌شود",
             fs=10, color=MUTED, align="ctr")


# ---------------------------------------------------------------- fig 3.21
@figure("fig_3_21_bottleneck", 10.0, 5.5)
def f321(fig):
    fig.title("شکل ۳.۲۱: نمودار شناسایی گلوگاه‌ها بر اساس میانگین زمان انتظار",
              fs=15)
    names = ["A%d" % i for i in range(1, 16)]
    vals = [139.5, 131.0, 86.0, 74.1, 71.8, 63.2, 60.0, 44.8, 41.8, 41.5,
            41.5, 33.9, 31.7, 20.1, 6.5]
    bars(fig, 1.0, 0.68, 8.6, 4.0, list(reversed(names)), list(reversed(vals)),
         color="#5B9BD5", fs=9, xtitle="میانگین زمان انتظار (دقیقه)",
         ytitle="فعالیت", gap=45, data_labels=True, horizontal=True,
         labels_fmt='0.0" دقیقه"')
    fig.chart_gap(1.0, 0.68, 8.6, 4.0, "نمودار گلوگاه‌ها")
    fig.text(0.3, 4.82, 9.4, 0.3,
             "ستون‌های قرمز: بالاتر از آستانه گلوگاه (صدک ۷۰ ≈ ۷۱٫۵ دقیقه)",
             fs=10, color=RED, align="ctr")


# ---------------------------------------------------------------- fig 3.22
@figure("fig_3_22_recommendations", 10.0, 6.4)
def f322(fig):
    fig.title("شکل ۳.۲۲: نمونه‌ای از پیشنهاد فعالیت‌های بعدی برای یک پیشوند دلخواه",
              fs=15)

    src = (2.3, 0.62, 5.4, 0.7)
    fig.box(*src, "**پیشوند ورودی:** [A, B, C, D]", fc=SAND, fs=12)

    mdl = (3.0, 1.7, 4.0, 0.8)
    fig.box(*mdl, "**مدل سه‌جریانه**", fc=BLUE, fs=12.5)
    fig.arrow([(cx(src), bottom(src)), (cx(mdl), mdl[1])])

    fig.text(5.55, 2.78, 4.2, 0.34, "**پیشنهاد فعالیت‌های بعدی:**", fs=11.5,
             align="r")
    fig.text(0.3, 2.78, 5.0, 0.34, "**خروجی‌های جانبی:**", fs=11.5, align="r")

    acts = [("فعالیت E", "۵۲٫۰٪", "#2E9E5B"), ("فعالیت F", "۲۴٫۰٪", "#2F5597"),
            ("فعالیت G", "۱۳٫۰٪", "#C55A11"), ("فعالیت H", "۷٫۰٪", "#833C0B"),
            ("فعالیت I", "۴٫۰٪", "#595959")]
    for i, (nm, p, fc) in enumerate(acts):
        y = 3.25 + i * 0.55
        fig.box(7.65, y, 2.0, 0.48, "**%s**" % nm, fc=fc, ec=LINE, fs=11,
                color=WHITE_TXT if i != 0 else WHITE_TXT)
        fig.box(5.65, y, 1.9, 0.48, "احتمال: %s" % p, fc=GREY, ec=LINE, fs=10,
                shape="rect", radius=0)

    sides = [("پتانسیل بهبود: +۰٫۱۸۰ (زمان باقی‌مانده تخمینی: ۴٫۵ دقیقه)", GREEN),
             ("پتانسیل بهبود: +۰٫۱۲۰ (پتانسیل بهبود کل: +۰٫۱۵)", SAND),
             ("پتانسیل بهبود: −۰٫۰۵۰ (گلوگاه‌های شناسایی‌شده: ۲ مورد)", PINK),
             ("پتانسیل بهبود: +۰٫۰۲۰", GREEN)]
    for i, (t, fc) in enumerate(sides):
        fig.box(0.3, 3.25 + i * 0.55, 5.15, 0.48, t, fc=fc, fs=10, align="r")

    fig.arrow([(cx(mdl), bottom(mdl)), (8.6, 3.23)], lw=1.3)
    fig.arrow([(cx(mdl), bottom(mdl)), (2.8, 3.23)], lw=1.3)


WHITE_TXT = "#FFFFFF"
