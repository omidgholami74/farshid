# -*- coding: utf-8 -*-
"""Figure: Prometheus-based operational monitoring architecture with an intelligent agent.

The canvas is split into the three design stages of the thesis (system specification,
architectural design, detailed design) by dashed rules, each labelled on the left.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import figlib  # noqa: E402

W, H = 11.9, 7.45
SPEC = {"size": (W, H), "boxes": [], "arrows": [], "texts": [], "lines": []}

BLUE = "#DEEAF6"
GREEN = "#E2EFDA"
SAND = "#FFF2CC"
ORANGE = "#FBE5D6"
GREY = "#F2F2F2"
SEP = "#8C8C8C"


def b(x, y, w, h, t, fc=BLUE, fs=10.5, bold=False, ec=figlib.LINE, r=0.07,
      dash=False, color=figlib.INK, lw=1.3, shape="round"):
    SPEC["boxes"].append(dict(x=x, y=y, w=w, h=h, t=t, fc=fc, fs=fs, bold=bold, ec=ec,
                              r=r, dash=dash, color=color, lw=lw, shape=shape))
    return (x, y, w, h)


def cx(bx):
    return bx[0] + bx[2] / 2.0


def bot(bx):
    return bx[1] + bx[3]


def a(p, label=None, dash=False, color=figlib.LINE, lw=1.6, head=11):
    SPEC["arrows"].append(dict(p=p, label=label, dash=dash, color=color, lw=lw, head=head))


def t(x, y, s, fs=9.5, bold=False, color=figlib.LINE, rot=0):
    SPEC["texts"].append(dict(x=x, y=y, t=s, fs=fs, bold=bold, color=color, rot=rot))


# ---------------- stage separators (dashed) ----------------
SPEC["lines"].append(dict(p=[(0.14, 1.44), (11.76, 1.44)], dash=True, lw=1.1, color=SEP))
SPEC["lines"].append(dict(p=[(0.14, 5.24), (11.76, 5.24)], dash=True, lw=1.1, color=SEP))

# stage labels, rotated along the left margin
t(0.46, 0.86, "۱.\nمشخصات سامانه", 9.2, bold=True, color="#1F3864", rot=90)
t(0.46, 3.30, "۲.\nطراحی معماری", 9.2, bold=True, color="#1F3864", rot=90)
t(0.46, 6.34, "۳.\nطراحی تفصیلی", 9.2, bold=True, color="#1F3864", rot=90)

# ---------------- stage 1: monitored sources ----------------
s1 = b(1.05, 0.42, 3.22, 0.78, "سامانه مالی / ERP\n(رویدادهای فرآیند)", BLUE)
s2 = b(4.72, 0.42, 3.20, 0.78, "پایگاه داده رویدادنگار\n(BPI Challenge 2012)", BLUE)
s3 = b(8.43, 0.42, 3.22, 0.78, "سرویس پیش‌بینی\n(مدل سه‌جریانه)", BLUE)

# ---------------- stage 2: exporters ----------------
e1 = b(1.05, 1.60, 3.22, 0.76, "صادرکننده متریک فرآیند\n(exporter اختصاصی پایتون)", GREEN)
e2 = b(4.72, 1.60, 3.20, 0.76, "Prometheus Agent\n(حالت عامل: حفظ کوتاه‌مدت)", SAND)
e3 = b(8.43, 1.60, 3.22, 0.76, "node_exporter\n(سخت‌افزار و سرویس)", GREEN)

# ---------------- stage 2: prometheus server ----------------
b(1.05, 2.78, 10.60, 1.30, "", GREY, dash=True, ec="#7F7F7F", lw=1.1)
t(6.35, 2.93, "سرور پرومتئوس (Prometheus Server)", 11, bold=True)
p1 = b(1.45, 3.10, 2.20, 0.76, "کشف سرویس\n(Service Discovery)", BLUE, fs=9.8)
p2 = b(4.02, 3.10, 2.50, 0.76, "واکشی متریک\n(Pull / Scrape)", BLUE, fs=9.8)
p3 = b(6.72, 3.10, 2.40, 0.76, "پایگاه داده سری‌زمانی\n(TSDB)", BLUE, fs=9.8)
p4 = b(9.32, 3.10, 2.03, 0.76, "قواعد هشدار\n(Alerting Rules / PromQL)", BLUE, fs=9)

# ---------------- stage 2: consumers ----------------
d2 = b(1.05, 4.42, 4.30, 0.70, "Grafana\n(داشبورد عملیاتی)", ORANGE, fs=9.8)
d1 = b(5.75, 4.42, 5.90, 0.70, "Alertmanager\n(مسیریابی و خاموش‌سازی هشدار)", ORANGE, fs=9.5)

# ---------------- stage 3: agent and action ----------------
ag = b(5.75, 5.58, 5.90, 0.95, "عامل هوشمند تصمیم‌یار\n(ادراک – استدلال – اقدام)", SAND,
       fs=10.5, bold=True)
out = b(1.05, 6.75, 10.60, 0.58, "اقدام اصلاحی، هشدار به تیم عملیات و بازخورد به سامانه مالی",
        GREY, fs=10, bold=True)

# ---------------- stage 1 -> exporters ----------------
a([(cx(s1), bot(s1)), (cx(s1), e1[1])])
a([(cx(s2), bot(s2)), (cx(s2), 1.30), (3.20, 1.30), (3.20, e1[1])])
a([(cx(s3), bot(s3)), (cx(s3), e3[1])])

# ---------------- exporters -> server ----------------
a([(cx(e1), bot(e1)), (cx(e1), p1[1])])
a([(cx(e2), bot(e2)), (cx(e2), p2[1])], dash=True)
a([(cx(e3), bot(e3)), (cx(e3), p4[1])])

# ---------------- inside the server ----------------
a([(p1[0] + p1[2], p1[1] + p1[3] / 2), (p2[0], p2[1] + p2[3] / 2)], lw=1.3, head=9)
a([(p2[0] + p2[2], p2[1] + p2[3] / 2), (p3[0], p3[1] + p3[3] / 2)], lw=1.3, head=9)
a([(p3[0] + p3[2], p3[1] + p3[3] / 2), (p4[0], p4[1] + p4[3] / 2)], lw=1.3, head=9)

# ---------------- server -> consumers ----------------
a([(cx(p3), bot(p3)), (cx(p3), 4.22), (cx(d2), 4.22), (cx(d2), d2[1])])
a([(cx(p4), bot(p4)), (cx(p4), 4.22), (cx(d1), 4.22), (cx(d1), d1[1])])

# ---------------- alerts -> agent, agent query -> server ----------------
a([(cx(d1), bot(d1)), (cx(d1), ag[1])])
a([(ag[0], ag[1] + 0.32), (5.55, ag[1] + 0.32), (5.55, 4.08)], dash=True, lw=1.4)

# ---------------- action + feedback loop ----------------
a([(cx(ag), bot(ag)), (cx(ag), out[1])])
a([(out[0], out[1] + out[3] / 2), (0.86, out[1] + out[3] / 2), (0.86, 0.81),
   (s1[0], 0.81)], dash=True, lw=1.4)

# ---------------- off-line labels ----------------
t(7.20, 2.56, "remote write", 8.5)
t(8.05, 5.36, "هشدار", 8.8)
t(0.63, 2.10, "بازخورد", 8.6, rot=90)

if __name__ == "__main__":
    outdir = os.path.join(os.path.dirname(HERE), "figs", "out")
    png = os.path.join(outdir, "prometheus.png")
    figlib.render(SPEC, png, svg_path=png.replace(".png", ".svg"), dpi=300)
    figlib.to_pptx(SPEC, png.replace(".png", ".pptx"))
    print("rendered:", png, os.path.getsize(png))
