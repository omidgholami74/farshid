# -*- coding: utf-8 -*-
"""Generate walkthrough_pipeline.ipynb at the project root (run from the project root)."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "walkthrough_pipeline.ipynb")

CELLS = []


def md(text):
    CELLS.append(("markdown", text.strip("\n")))


def code(text):
    CELLS.append(("code", text.strip("\n")))


md(r"""
# راهنمای گام‌به‌گام خط لوله پژوهش

این نوتبوک همان مسیر سه ستون روش‌شناسی پایان‌نامه را روی داده واقعی اجرا می‌کند و در هر گام
نشان می‌دهد داده چه شکلی دارد و چه چیزی به گام بعد تحویل داده می‌شود:

1. خواندن رویدادنگار و نمایش داده خام
2. ساخت نمای پرونده‌محور و شاخص‌های توصیفی
3. ساخت پیشوندها برای یک پرونده نمونه، گام‌به‌گام
4. تبدیل پیشوندها به نمونه‌های آموزش (دیتاست چندوظیفه‌ای)
5. ساخت دسته و گراف پیشوند (ورودی سه جریان مدل)
6. بازسازی معماری و بارگذاری مدل آموزش‌دیده
7. استنتاج روی یک پیشوند و نمایش کامل خروجی‌ها
8. ارزیابی کامل مدل روی داده آزمون
9. رتبه‌بندی گلوگاه‌ها و پتانسیل بهبود
10. ذخیره خروجی‌ها برای گزارش

**پیش‌نیازها**: پایتون ۳٫۱۰+، بسته‌های `torch`، `pm4py`، `scikit-learn`، `pandas`، `matplotlib`
و دو فایل ورودی:

- رویدادنگار `BPI_Challenge_2012.xes.gz` (کنار نوتبوک یا در پوشه `data`)
- چک‌پوینت مدل آموزش‌دیده: `results_tri_stream/best_tri_stream.pt` یا
  `results_tri_stream/bpi2012_tri_stream_model.pt` — همان فایل‌هایی که `main.py` هنگام آموزش می‌سازد.

اگر چک‌پوینت را ندارید، یک بار `python main.py` را اجرا کنید تا ساخته شود.
""")

md("## گام ۰ — تنظیمات و بررسی ورودی‌ها")

code(r"""
import os, sys, json, glob, math
from collections import defaultdict

CWD = os.getcwd()
if CWD not in sys.path:
    sys.path.insert(0, CWD)

DATA_CANDIDATES = [
    "BPI_Challenge_2012.xes.gz",
    "BPI_Challenge_2012.xes",
    os.path.join("data", "BPI_Challenge_2012.xes.gz"),
    os.path.join("data", "BPI_Challenge_2012.xes"),
]
MODEL_CANDIDATES = [
    os.path.join("results_tri_stream", "best_tri_stream.pt"),
    os.path.join("results_tri_stream", "bpi2012_tri_stream_model.pt"),
    "bpi2012_tri_stream_model.pt",
]

DATA_PATH = next((p for p in DATA_CANDIDATES if os.path.exists(p)), DATA_CANDIDATES[0])
MODEL_PATH = next((p for p in MODEL_CANDIDATES if os.path.exists(p)), MODEL_CANDIDATES[0])

MAX_SEQ_LEN = 100
MIN_PREFIX_LEN = 2
OUT_DIR = "results_notebook"
os.makedirs(OUT_DIR, exist_ok=True)

print("رویدادنگار:", DATA_PATH, "|", "موجود" if os.path.exists(DATA_PATH) else "یافت نشد")
print("چک‌پوینت  :", MODEL_PATH, "|", "موجود" if os.path.exists(MODEL_PATH) else "یافت نشد")
""")

md("""
## گام ۱ — خواندن رویدادنگار (ستون یکم: فرآیندکاوی)

واحد داده در فرآیندکاوی رویداد است. پس از خواندن، هر رویداد سه چیز دارد: شناسه پرونده،
نام فعالیت و زمان وقوع. جدول زیر نمونه‌ای از همان چیزی است که مدل در نهایت می‌بیند.
""")

code(r"""
import pandas as pd
from pm4py import read_xes
from pm4py.objects.conversion.log import converter as log_converter

if not os.path.exists(DATA_PATH):
    raise FileNotFoundError(
        "رویدادنگار پیدا نشد. فایل BPI_Challenge_2012.xes.gz را کنار نوتبوک بگذارید "
        "یا مقدار DATA_PATH را در گام ۰ اصلاح کنید."
    )

log = read_xes(DATA_PATH)
df = log_converter.apply(log, variant=log_converter.Variants.TO_DATA_FRAME)

# XES keys are stable strings; CASE_CONCEPT_NAME is absent in some pm4py releases.
CASE, ACT, TS = "case:concept:name", "concept:name", "time:timestamp"
missing_columns = [key for key in (CASE, ACT, TS) if key not in df.columns]
if missing_columns:
    raise KeyError("ستون‌های موردنیاز در داده نیستند: %s | ستون‌های موجود: %s"
                   % (missing_columns, list(df.columns)))

print("تعداد پرونده :", len(log))
print("تعداد رویداد :", sum(len(c) for c in log))
print("تعداد فعالیت :", df[ACT].nunique())
print("بازه زمانی   :", df[TS].min(), "→", df[TS].max())
df[[CASE, ACT, TS]].head(8)
""")

md("""
## گام ۲ — نمای پرونده‌محور

مدل روی «پرونده» کار می‌کند نه روی جدول رویدادها. طول هر پرونده و مدت اجرای آن، دو ویژگی
پایه‌ای است که بعداً به شاخص‌های پایش تبدیل می‌شود.
""")

code(r"""
summary = df.groupby(CASE).agg(events=(ACT, "size"), start=(TS, "min"), end=(TS, "max"))
summary["duration_h"] = (summary["end"] - summary["start"]).dt.total_seconds() / 3600

print("میانگین طول پرونده:", round(summary["events"].mean(), 2), "رویداد")
print("میانه مدت اجرا     :", round(summary["duration_h"].median(), 2), "ساعت")
summary.head(6)
""")

code(r"""
activity_counts = df[ACT].value_counts().rename_axis("فعالیت").reset_index(name="تعداد")
activity_counts.head(15)
""")

md("""
## گام ۳ — ساخت پیشوندها برای یک پرونده، گام‌به‌گام

برای هر پرونده، یک رویداد را انتخاب می‌کنیم و همه پیشوندهای ممکن را می‌سازیم. هر پیشوند
یک نمونه آموزش است: ورودی مدل، رویدادهای دیده‌شده تا آن لحظه و خروجی مطلوب، رویداد بعدی،
زمان باقی‌مانده تا پایان پرونده و انتظار واقعی تا رویداد بعد.
""")

code(r"""
sample_case = next((c for c in log if len(c) >= 8), log[0])
case_id = sample_case.attributes.get("concept:name", "<نامشخص>")
print("پرونده نمونه:", case_id, "| تعداد رویداد:", len(sample_case))
print()

prev = None
for i, ev in enumerate(sample_case, start=1):
    ts = ev[TS]
    gap = 0.0 if prev is None else (ts - prev).total_seconds() / 3600
    print("  رویداد %2d | %-40s | %s | فاصله از قبلی: %6.1f ساعت"
          % (i, str(ev[ACT])[:40], ts.strftime("%Y-%m-%d %H:%M"), gap))
    prev = ts
""")

code(r"""
acts = [ev[ACT] for ev in sample_case]
times = [ev[TS] for ev in sample_case]

prefix_rows = []
for i in range(MIN_PREFIX_LEN, len(acts)):
    prefix_rows.append({
        "پیشوند (چهار رویداد آخر)": " ← ".join(acts[:i][-4:]),
        "طول پیشوند": i,
        "فعالیت هدف": acts[i],
        "زمان باقی‌مانده تا پایان (ساعت)": round((times[-1] - times[i]).total_seconds() / 3600, 2),
        "انتظار واقعی تا رویداد بعد (ساعت)": round((times[i] - times[i - 1]).total_seconds() / 3600, 2),
    })

print("تعداد نمونه ساخته‌شده از این پرونده:", len(prefix_rows))
pd.DataFrame(prefix_rows).head(8)
""")

md("""
## گام ۴ — دیتاست چندوظیفه‌ای (ستون دوم: یادگیری ماشین)

همین منطق برای همه پرونده‌ها اجرا می‌شود. خروجی هر نمونه چهار هدف دارد: فعالیت بعدی
(طبقه‌بندی)، زمان باقی‌مانده (رگرسیون)، پتانسیل بهبود تأخیر (رگرسیون محدود) و نشانگر گلوگاه.
""")

code(r"""
import main as M

activities_index = ["<PAD>"] + sorted({ev[ACT] for c in log for ev in c})

dataset = M.MultiTaskProcessDataset(
    eventlog=log,
    activities_index=activities_index,
    max_seq_len=MAX_SEQ_LEN,
    min_prefix_len=MIN_PREFIX_LEN,
    use_time=True,
)

print()
print("تعداد فعالیت (با PAD):", len(activities_index))
print("تعداد نمونه آموزش   :", len(dataset))
print("تعداد پرونده یکتا   :", len(set(dataset.case_ids)))
""")

code(r"""
sample = dataset[0]
print("نمونه اول دیتاست:")
for key, val in sample.items():
    shape = tuple(val.shape) if hasattr(val, "shape") else val
    print("  %-20s %s" % (key, shape))

print()
print("پیشوند  :", [activities_index[i] for i in sample["activities"].tolist()
                    if i != 0][:8])
print("هدف     :", activities_index[int(sample["target_activity"])])
print("زمان باقی‌مانده واقعی (ثانیه):", float(sample["raw_remaining"]))
""")

md("""
## گام ۵ — دسته‌بندی و گراف پیشوند

سه جریان مدل سه نمایش متفاوت از یک نمونه می‌خواهند: توالی (تبدیل‌کننده)، توالی پیچشی
(TCN) و گراف (GNN). این گام نشان می‌دهد هر سه نمایش چگونه از همان پیشوند ساخته می‌شوند.
""")

code(r"""
import torch
from functools import partial
from torch.utils.data import DataLoader, Subset
from sklearn.model_selection import train_test_split

cases = sorted(set(dataset.case_ids))
train_cases, test_cases = train_test_split(cases, train_size=0.67, random_state=42)
test_set_ids = set(test_cases)
test_idx = [i for i, c in enumerate(dataset.case_ids) if c in test_set_ids]
test_set = Subset(dataset, test_idx)

collate = partial(M.collate_with_graphs, max_seq_len=MAX_SEQ_LEN)
test_loader = DataLoader(test_set, batch_size=64, shuffle=False, collate_fn=collate)

print("پرونده آموزش/آزمون:", len(train_cases), "/", len(test_cases))
print("نمونه آزمون        :", len(test_idx))

batch = next(iter(test_loader))
print()
print("شکل دسته ورودی:")
for key, val in batch.items():
    if key == "graph":
        continue
    print("  %-20s %s" % (key, tuple(val.shape)))
g = batch["graph"]
print("  %-20s %s" % ("graph.nodes", tuple(g["node_activities"].shape)))
print("  %-20s %s" % ("graph.edges[0]", tuple(g["edge_index_list"][0].shape)))
""")

md("""
## گام ۶ — بازسازی معماری و بارگذاری مدل آموزش‌دیده

معماری دقیقاً با همان پیکربندی `main.py` ساخته می‌شود تا کلیدهای چک‌پوینت بخوانند.
اگر شمار کلیدهای بارگذاری‌شده با شمار کلیدهای مدل یکی نباشد، هشدار داده می‌شود.
""")

code(r"""
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
torch.manual_seed(42)

model = M.DelayAwareTriStreamTransformer(
    num_activities=len(activities_index),
    d_model=256, nhead=8, num_layers=6, dim_feedforward=1024,
    dropout=0.05, max_seq_len=MAX_SEQ_LEN, max_position=4000,
    use_time=True, pooling="last", tie_weights=True, gnn_layers=2,
)
print("دستگاه:", DEVICE)
print("تعداد پارامترها:", f"{sum(p.numel() for p in model.parameters()):,}")

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(
        "چک‌پوینت مدل پیدا نشد: %s\n"
        "یک بار main.py را اجرا کنید یا مسیر MODEL_PATH را در گام ۰ اصلاح کنید." % MODEL_PATH
    )

state = torch.load(MODEL_PATH, map_location="cpu")
if isinstance(state, dict) and "state_dict" in state:
    state = state["state_dict"]

missing, unexpected = model.load_state_dict(state, strict=False)
model.to(DEVICE).eval()

print("کلیدهای چک‌پوینت:", len(state))
print("کلیدهای بارگذاری‌نشده:", len(missing), "| کلیدهای اضافی:", len(unexpected))
if missing:
    print("هشدار: بخشی از وزن‌ها مقدار تصادفی دارند →", missing[:5])
""")

md("""
## گام ۷ — استنتاج روی یک پیشوند و نمایش کامل خروجی

مدل برای یک پیشوند واقعی از داده آزمون اجرا می‌شود و هر چهار خروجی خوانده و تفسیر می‌شود:
فهرست فعالیت‌های بعدی با احتمال، زمان باقی‌مانده، پتانسیل بهبود و نشانگر گلوگاه.
""")

code(r"""
prefix_len = min(6, len(acts) - 1)
prefix = acts[:prefix_len]
print("پیشوند ورودی:", " ← ".join(prefix))
print()

rec = M.recommend_improvements_for_prefix(
    model=model, prefix_activities=prefix, activities_index=activities_index,
    dataset=dataset, device=DEVICE, top_k=10,
)

top = pd.DataFrame(rec["next_activity_recommendations"])
top["probability"] = (top["probability"] * 100).round(2)
top["predicted_delay_improvement"] = top["predicted_delay_improvement"].round(4)
top.columns = ["فعالیت پیش‌بینی‌شده", "احتمال (٪)", "پتانسیل بهبود (تانژانت هذلولوی)"]
top
""")

code(r"""
rem_log = rec["predicted_remaining_time_log"]
imp = rec["predicted_improvement"]

print("زمان باقی‌مانده (خروجی خام مدل، لگاریتمی):", round(rem_log, 4))
print("زمان باقی‌مانده (ثانیه، بازگردانی‌شده)  :", round(math.expm1(rem_log), 1))
print("زمان باقی‌مانده (ساعت)                 :", round(math.expm1(rem_log) / 3600, 2))
print()
print("پتانسیل بهبود تأخیر (تانژانت):", round(imp, 4))
print("تفسیر: مقدار مثبت یعنی رویداد بعدی نسبت به میانگین تاریخی این فعالیت،")
print("       انتظار کوتاه‌تری دارد و مقدار منفی یعنی انتظار طولانی‌تر از میانگین.")
""")

md("""
## گام ۸ — ارزیابی کامل روی داده آزمون

داده آزمون بر اساس شناسه پرونده جدا شده است، بنابراین هیچ پرونده‌ای هم‌زمان در آموزش و آزمون
نیست. معیارها همان معیارهای فصل چهارم پایان‌نامه هستند.
""")

code(r"""
from sklearn.metrics import mean_absolute_error, classification_report

topk = {}
for k in (1, 3, 5, 10):
    topk["Top-%d" % k] = M.evaluate_topk(model, test_loader, DEVICE, k=k)

preds = M.collect_predictions(model, test_loader, DEVICE)

mae_rem = mean_absolute_error(preds["rem_true"].numpy(), preds["rem_pred"].numpy())
mae_imp = mean_absolute_error(preds["imp_true"].numpy(), preds["imp_pred"].numpy())

metrics = {name: round(value * 100, 2) for name, value in topk.items()}
metrics["MAE زمان باقی‌مانده"] = round(mae_rem, 4)
metrics["MAE پتانسیل بهبود"] = round(mae_imp, 4)
metrics["تعداد نمونه آزمون"] = len(test_idx)

pd.DataFrame({"معیار": list(metrics), "مقدار": list(metrics.values())})
""")

code(r"""
truth = preds["targets"].numpy()
guess = preds["logits"].argmax(-1).numpy()

report = classification_report(
    truth, guess,
    labels=list(range(len(activities_index))),
    target_names=[str(a)[:28] for a in activities_index],
    zero_division=0, output_dict=True,
)
per_class = pd.DataFrame(report).T
per_class = per_class[per_class.index.isin([str(a)[:28] for a in activities_index])]
per_class = per_class.astype(float).round(3).sort_values("support", ascending=False)
per_class.head(15)
""")

code(r"""
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix
import numpy as np

labels = np.bincount(truth, minlength=len(activities_index)).argsort()[::-1][:15]
cm = confusion_matrix(truth, guess, labels=labels)

fig, ax = plt.subplots(figsize=(9, 7))
im = ax.imshow(cm, cmap="Blues")
ax.set_xticks(range(len(labels)))
ax.set_xticklabels([str(activities_index[i])[:18] for i in labels], rotation=90, fontsize=7)
ax.set_yticks(range(len(labels)))
ax.set_yticklabels([str(activities_index[i])[:18] for i in labels], fontsize=7)
ax.set_xlabel("پیش‌بینی مدل")
ax.set_ylabel("فعالیت واقعی")
ax.set_title("ماتریس درهم‌ریختگی ۱۵ کلاس پرتکرار (داده آزمون)")
fig.colorbar(im, ax=ax, fraction=0.04)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "confusion_top15.png"), dpi=200, bbox_inches="tight")
plt.show()
""")

md("""
## گام ۹ — گلوگاه‌ها و پتانسیل بهبود

این جدول همان خروجی‌ای است که در معماری پایش به متریک تبدیل و به سامانه هشدار داده می‌شود.
""")

code(r"""
imp_by_activity = defaultdict(list)
for act_id, value in zip(preds["targets"].numpy(), preds["imp_pred"].numpy()):
    imp_by_activity[int(act_id)].append(float(value))

wait = {name: float(w) for name, w in dataset.activity_mean_wait.items()}
improve = {activities_index[a]: float(np.mean(v)) for a, v in imp_by_activity.items()
           if a < len(activities_index)}

rows = []
for name, avg_wait in sorted(wait.items(), key=lambda kv: kv[1], reverse=True)[:15]:
    rows.append({
        "فعالیت": name,
        "میانگین انتظار واقعی (دقیقه)": round(avg_wait / 60, 2),
        "پتانسیل بهبود پیش‌بینی‌شده": round(improve.get(name, float("nan")), 4),
    })

bottlenecks = pd.DataFrame(rows)
bottlenecks
""")

md("""
## گام ۱۰ — ذخیره خروجی‌ها

خروجی‌های این نوتبوک در پوشه `results_notebook` ذخیره می‌شوند تا در گزارش و اسلایدها
قابل ارجاع باشند.
""")

code(r"""
out_metrics = {
    "data_path": DATA_PATH,
    "model_path": MODEL_PATH,
    "num_cases": len(log),
    "num_events": int(sum(len(c) for c in log)),
    "num_activities": len(activities_index),
    "num_samples": len(dataset),
    "num_test_samples": len(test_idx),
    "top_k_accuracy_percent": {k: v * 100 for k, v in topk.items()},
    "mae_remaining_normalized": mae_rem,
    "mae_improvement_normalized": mae_imp,
    "sample_prefix": [str(a) for a in prefix],
    "sample_prediction_top1": rec["next_activity_recommendations"][0]["activity"],
    "sample_prediction_top1_prob": rec["next_activity_recommendations"][0]["probability"],
    "sample_remaining_seconds": math.expm1(rec["predicted_remaining_time_log"]),
    "sample_improvement": rec["predicted_improvement"],
}

with open(os.path.join(OUT_DIR, "walkthrough_metrics.json"), "w", encoding="utf8") as f:
    json.dump(out_metrics, f, ensure_ascii=False, indent=2)

top.to_csv(os.path.join(OUT_DIR, "sample_prediction.csv"), index=False, encoding="utf8")
bottlenecks.to_csv(os.path.join(OUT_DIR, "bottlenecks.csv"), index=False, encoding="utf8")
per_class.to_csv(os.path.join(OUT_DIR, "per_class_metrics.csv"), encoding="utf8")

print("فایل‌های ذخیره‌شده در", OUT_DIR, ":")
for path in sorted(glob.glob(os.path.join(OUT_DIR, "*"))):
    print("  ", path)
""")

md(r"""
## جمع‌بندی: هر گام چه چیزی به پایان‌نامه اضافه می‌کند

| گام | خروجی | جایگاه در پایان‌نامه |
|---|---|---|
| ۱–۲ | نمای رویدادمحور و پرونده‌محور، آمار توصیفی | فصل ۳ (ستون فرآیندکاوی) و جدول ۴.۲ |
| ۳–۵ | پیشوندها، دیتاست چندوظیفه‌ای، دسته و گراف | بخش آماده‌سازی داده و ورودی سه جریان |
| ۶ | بارگذاری وزن‌های آموزش‌دیده | بخش استراتژی آموزش |
| ۷ | خروجی کامل یک نمونه: فعالیت، زمان، بهبود، گلوگاه | نمونه کاربردی بخش تحلیل گلوگاه |
| ۸ | دقت Top-k، خطای زمان، معیارهای کلاسی، ماتریس درهم‌ریختگی | فصل ۴ |
| ۹ | رتبه‌بندی گلوگاه و پتانسیل بهبود | بخش شناسایی گلوگاه‌ها |
| ۱۰ | فایل‌های CSV و JSON قابل ارجاع | پیوست نتایج |

اگر شماره‌گذاری بخش‌ها پس از ویرایش تغییر کرد، ارجاع‌های ستون سمت راست را با فهرست مطالب
هم‌تراز کنید.
""")


def build():
    nb_cells = []
    for i, (kind, src) in enumerate(CELLS):
        if kind == "markdown":
            nb_cells.append({
                "cell_type": "markdown",
                "id": "md-%02d" % i,
                "metadata": {},
                "source": src.splitlines(keepends=True),
            })
        else:
            nb_cells.append({
                "cell_type": "code",
                "id": "code-%02d" % i,
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": src.splitlines(keepends=True),
            })

    nb = {
        "cells": nb_cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.12"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    with open(OUT, "w", encoding="utf8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    print("written:", OUT, "| cells:", len(nb_cells))


if __name__ == "__main__":
    build()
