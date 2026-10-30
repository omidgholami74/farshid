# -*- coding: utf-8 -*-
"""Figure: Prometheus-based operational monitoring architecture with an intelligent agent."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import figlib  # noqa: E402

W, H = 11.4, 7.0
SPEC = {"size": (W, H), "boxes": [], "arrows": [], "texts": []}

BLUE = "#DEEAF6"
GREEN = "#E2EFDA"
SAND = "#FFF2CC"
ORANGE = "#FBE5D6"
GREY = "#F2F2F2"


def b(x, y, w, h, t, fc=BLUE, fs=10.5, bold=False, ec=figlib.LINE, r=0.07,
      dash=False, color=figlib.INK, lw=1.3, shape="round"):
    SPEC["boxes"].append(dict(x=x, y=y, w=w, h=h, t=t, fc=fc, fs=fs, bold=bold, ec=ec,
                              r=r, dash=dash, color=color, lw=lw, shape=shape))
    return (x, y, w, h)


def cx(bx):
    return bx[0] + bx[2] / 2.0


def cy(bx):
    return bx[1] + bx[3] / 2.0


def bot(bx):
    return bx[1] + bx[3]


def a(p, label=None, dash=False, color=figlib.LINE, lw=1.6, dx=0.0, dy=0.0):
    SPEC["arrows"].append(dict(p=p, label=label, dash=dash, color=color, lw=lw,
                               dx=dx, dy=dy))


def t(x, y, s, fs=9.5, bold=False, color=figlib.LINE):
    SPEC["texts"].append(dict(x=x, y=y, t=s, fs=fs, bold=bold, color=color))


# ---------------- row 1: data sources ----------------
s1 = b(0.35, 0.45, 3.25, 0.85, "سامانه مالی / ERP\n(رویدادهای فرآیند)", BLUE)
s2 = b(4.05, 0.45, 3.25, 0.85, "پایگاه داده رویدادنگار\n(BPI Challenge 2012)", BLUE)
s3 = b(7.75, 0.45, 3.3, 0.85, "سرویس پیش‌بینی\n(مدل سه‌جریانه)", BLUE)

# ---------------- row 2: exporters ----------------
e1 = b(0.35, 1.72, 3.25, 0.8, "صادرکننده متریک فرآیند\n(exporter اختصاصی پایتون)", GREEN)
e2 = b(4.05, 1.72, 3.25, 0.8, "Prometheus Agent\n(حالت عامل: حفظ کوتاه‌مدت)", SAND)
e3 = b(7.75, 1.72, 3.3, 0.8, "node_exporter\n(سخت‌افزار و سرویس)", GREEN)

# ---------------- row 3: prometheus server ----------------
b(0.35, 2.95, 10.7, 1.62, "", GREY, dash=True, ec="#7F7F7F", lw=1.1)
SPEC["texts"].append(dict(x=5.7, y=3.16, t="سرور پرومتئوس (Prometheus Server)", fs=11, bold=True))
p1 = b(0.65, 3.45, 2.15, 0.82, "کشف سرویس\n(Service Discovery)", BLUE, fs=10)
p2 = b(3.15, 3.45, 2.35, 0.82, "واکشی متریک\n(Pull / Scrape)", BLUE, fs=10)
p3 = b(5.85, 3.45, 2.45, 0.82, "پایگاه داده سری‌زمانی\n(TSDB)", BLUE, fs=10)
p4 = b(8.65, 3.45, 2.1, 0.82, "قواعد هشدار\n(Alerting Rules / PromQL)", BLUE, fs=9.5)

# ---------------- row 4: consumers ----------------
d1 = b(0.55, 5.02, 2.85, 0.85, "Alertmanager\n(مسیریابی و خاموش‌سازی هشدار)", ORANGE, fs=9.5)
d2 = b(3.75, 5.02, 2.95, 0.85, "Grafana\n(داشبورد عملیاتی)", ORANGE, fs=10)
d3 = b(7.05, 4.95, 4.0, 0.98, "عامل هوشمند تصمیم‌یار\n(ادراک – استدلال – اقدام)", SAND, fs=10.5, bold=True)

# ---------------- row 5: action ----------------
out = b(0.55, 6.15, 10.5, 0.68, "اقدام اصلاحی، هشدار به تیم عملیات و بازخورد به سامانه مالی",
        GREY, fs=10.5, bold=True)

# ---------------- arrows ----------------
a([(cx(s1), bot(s1)), (cx(s1), e1[1])])
a([(cx(s2), bot(s2)), (cx(s2), 1.52), (cx(e1) + 0.55, 1.52), (cx(e1) + 0.55, e1[1])])
a([(cx(s3), bot(s3)), (cx(s3), e3[1])])

a([(cx(e1), bot(e1)), (cx(e1), 2.72), (cx(p1) + 0.3, 2.72), (cx(p1) + 0.3, p1[1])])
a([(cx(e3), bot(e3)), (cx(e3), 2.72), (cx(p2) + 0.75, 2.72), (cx(p2) + 0.75, p2[1])])
a([(cx(e2), bot(e2)), (cx(e2), 2.72), (cx(p3), 2.72), (cx(p3), p3[1])], dash=True)

a([(cx(p4), bot(p4)), (cx(p4), 4.66), (cx(d1), 4.66), (cx(d1), d1[1])])
a([(cx(p3) - 0.35, bot(p3)), (cx(p3) - 0.35, 4.50), (cx(d2), 4.50), (cx(d2), d2[1])])
a([(cx(p3) + 0.55, bot(p3)), (cx(p3) + 0.55, 4.82), (cx(d3), 4.82), (cx(d3), d3[1])])

# alert -> agent, routed under Grafana instead of through it
a([(cx(d1), bot(d1)), (cx(d1), 6.04), (7.9, 6.04), (7.9, bot(d3))], lw=1.4)

a([(cx(d3), bot(d3)), (cx(d3), out[1])])
a([(out[0], cy(out)), (0.12, cy(out)), (0.12, cy(s1)), (s1[0], cy(s1))], dash=True)

# ---------------- explicit labels (placed by hand, off the lines) ----------------
t(4.55, 2.86, "remote write", 9.5)
t(0.62, 4.86, "بازخورد", 9.5)
t(9.62, 6.03, "تصمیم", 9.5)

if __name__ == "__main__":
    outdir = os.path.join(os.path.dirname(HERE), "figs", "out")
    png = os.path.join(outdir, "prometheus.png")
    figlib.render(SPEC, png, svg_path=png.replace(".png", ".svg"), dpi=300)
    print("rendered:", png, os.path.getsize(png))
