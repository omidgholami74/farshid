# -*- coding: utf-8 -*-
"""Figures 3.5 (prefix-length histogram) and 3.6 (data split)."""
from figchart import bars
from figkit import BLUE, GREEN, INK, LINE, MUTED, PINK, SAND, bottom, cx, figure

RED = "#C00000"

BINS = [2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20, 22.5, 25, 27.5, 30, 32.5, 35,
        37.5, 40, 42.5, 45, 47.5, 50, 52.5, 55, 57.5, 60, 62.5, 65, 67.5, 70,
        72.5, 75, 77.5, 80, 82.5, 85, 87.5, 90, 92.5, 95, 97.5, 100]
COUNTS = [480, 990, 1385, 1750, 1790, 1780, 850, 1670, 1480, 1300, 1130, 1015,
          440, 715, 635, 520, 430, 310, 205, 270, 170, 135, 95, 60, 50, 35, 30,
          20, 15, 12, 8, 6, 5, 4, 3, 2, 2, 1, 1, 0]


@figure("fig_3_5_prefix_distribution", 10.0, 4.3)
def f35(fig):
    fig.title("شکل ۳.۵: توزیع طول پیشوندها و استراتژی برش از انتها", fs=15)

    cats = ["0" if abs(b) < 1e-6 else ("%d" % round(b) if round(b) % 20 == 0 else "")
            for b in BINS]
    bars(fig, 1.15, 0.6, 7.45, 2.9, cats, COUNTS, color="#9DC3E6",
         xtitle="طول پیشوند (تعداد رویدادها)", ytitle="فراوانی", fs=9, gap=8)

    fig.box(8.75, 1.35, 1.2, 0.75,
            "**ناحیه برش از انتها**\n(Truncation)", fc=PINK, ec=RED, fs=9.5,
            color=RED)

    fig.text(0.3, 3.72, 9.4, 0.4,
             "حداکثر طول مجاز پیشوند ۱۰۰ رویداد است؛ نمونه‌های بلندتر از انتها برش می‌خورند",
             fs=10.5, color=MUTED, align="ctr")


@figure("fig_3_6_data_split", 10.0, 5.0)
def f36(fig):
    fig.title("شکل ۳.۶: طرح تقسیم‌بندی داده‌ها بر اساس شناسه نمونه", fs=15)

    root = (2.7, 0.62, 4.6, 0.66)
    fig.box(*root, "**کل Caseها**", fc=SAND, fs=13)

    train = (5.1, 1.75, 4.7, 0.95)
    temp = (0.2, 1.75, 4.7, 0.95)
    fig.box(*train, "**مجموعه آموزش**\n۶۷٪", fc=GREEN, fs=12)
    fig.box(*temp, "**مجموعه موقت**\n۳۳٪", fc=SAND, fs=12)

    fig.text(0.35, 1.36, 2.2, 0.3, "تقسیم اول: ۶۷٪ / ۳۳٪", fs=10, color=LINE,
             align="r")
    fig.arrow([(5.0, bottom(root)), (5.0, 1.5)])
    fig.arrow([(5.0, 1.5), (7.45, train[1])])
    fig.arrow([(5.0, 1.5), (2.55, temp[1])])

    tr2 = (5.1, 3.1, 4.7, 0.7)
    fig.box(*tr2, "مجموعه آموزش\n(۶۷٪ کل)", fc=GREEN, fs=11)
    fig.arrow([(cx(train), bottom(train)), (cx(train), tr2[1])])

    val = (2.65, 3.1, 2.25, 0.7)
    tst = (0.2, 3.1, 2.2, 0.7)
    fig.box(*val, "اعتبارسنجی\n(۲۷٪ کل)", fc=SAND, fs=11)
    fig.box(*tst, "آزمون\n(۳۳٪ کل)", fc=PINK, fs=11)

    fig.text(0.2, 2.78, 2.2, 0.28, "تقسیم دوم: ۸۰٪ / ۲۰٪", fs=10, color=RED,
             align="r")
    fig.arrow([(2.55, bottom(temp)), (2.55, 2.92)])
    fig.arrow([(2.55, 2.92), (1.3, 2.92), (1.3, tst[1])])
    fig.arrow([(2.55, 2.92), (3.77, 2.92), (3.77, val[1])])

    fig.box(0.6, 4.2, 8.8, 0.66,
            "**تقسیم بر اساس Case ID (نه نمونه‌های منفرد)** برای جلوگیری از نشت اطلاعات",
            fc=PINK, fs=11)
