# -*- coding: utf-8 -*-
"""Patch payannameh.docx:
1) Insert real Word (OMML) equations, each inside a borderless 1x2 table with
   the equation number on the right-hand side.
2) Add the "Prometheus architecture + intelligent agent" section to chapter 3.
3) Fix a set of clear defects (garbage reference, cover typos, caption styles,
   caption placement, ZWNJ spacing, references alignment, missing sources).
"""
import copy
import os
import re
import subprocess
import sys
import tempfile
import zipfile

import docx
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import parse_xml
from docx.oxml.ns import qn
from lxml import etree

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def w(tag):
    return "{%s}%s" % (W_NS, tag)


def m(tag):
    return "{%s}%s" % (M_NS, tag)


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCX = os.path.join(ROOT, "payannameh.docx")
PANDOC = os.path.join(HERE, "pandoc")

# ---------------------------------------------------------------- equations
# key -> LaTeX (kept deliberately simple so pandoc -> OMML stays clean)
EQ = {
    "class_weight": r"w_c=\left(\frac{N}{C\,n_c}\right)^{\beta}",
    "gap": (r"\tilde{g}_t=\ln\left(1+g_t\right),\qquad "
            r"e^{g}_t=W_2\,\mathrm{GELU}\left(W_1\tilde{g}_t+b_1\right)+b_2"),
    "role": (r"e^{r}_t=W_r\left[\mathrm{isFirst}_t,\ \mathrm{isLast}_t\right]^{\top}+b_r"),
    "freq": (r"\mathbf{f}_t=\frac{1}{t}\sum_{s=1}^{t}\mathrm{onehot}\left(a_s\right),\qquad "
             r"e^{f}_t=W_f\mathbf{f}_t"),
    "relpos": (r"\bar{e}^{rel}_t=\frac{1}{t}\sum_{j=1}^{t}E_{rel}\left[\mathrm{clip}"
               r"\left(t-j,-D,D\right)\right]"),
    "input": (r"h^{0}_t=\mathrm{Dropout}\left(\mathrm{LN}\left(\sum_{k=1}^{8}"
              r"e^{(k)}_t\right)\right)"),
    "attn": (r"\mathrm{Attn}(Q,K,V)=\mathrm{softmax}\left(\frac{QK^{\top}}{\sqrt{d_k}}"
             r"+M\right)V"),
    "mha": (r"\mathrm{MHA}(X)=\mathrm{Concat}\left(\mathrm{head}_1,\dots,\mathrm{head}_H\right)W^{O},"
            r"\qquad \mathrm{head}_i=\mathrm{Attn}\left(XW^{Q}_i,XW^{K}_i,XW^{V}_i\right)"),
    "resid": r"u=\mathrm{LN}\left(x+\mathrm{Sublayer}(x)\right)",
    "ffn": r"\mathrm{FFN}(x)=W_2\,\mathrm{GELU}\left(W_1x+b_1\right)+b_2",
    "dilconv": r"(F\ast_{d}x)(t)=\sum_{k=0}^{K-1}F(k)\,x_{t-dk}",
    "tcn": (r"y_t=\mathrm{GELU}\left(\mathrm{LN}\left(x_t+(F\ast_{d}x)(t)\right)\right)"
            r"\odot m_t"),
    "xattn": (r"C=\mathrm{softmax}\left(\frac{Q_TK_C^{\top}}{\sqrt{d_k}}\right)V_C"),
    "gnn_msg": (r"\tilde{h}^{(l)}_i=\mathrm{LN}\left(\mathrm{GELU}\left(W_1h^{(l)}_i"
                r"+W_2\,\frac{1}{\left|N(i)\right|}\sum_{j\in N(i)}h^{(l)}_j\right)\right)"),
    "gnn_gate": (r"h^{(l+1)}_i=g_i\odot\tilde{h}^{(l)}_i+\left(1-g_i\right)\odot h^{(l)}_i,"
                 r"\qquad g_i=\sigma\left(W_g\left[h^{(l)}_i;\tilde{h}^{(l)}_i\right]\right)"),
    "fusion": (r"z=\mathrm{LN}\left(\mathrm{GELU}\left(W_2\,\mathrm{GELU}\left(W_1"
               r"\left[u;\,u\odot h_G\right]+b_1\right)+b_2\right)\right)"),
    "tying": (r"\hat{y}_t=\mathrm{softmax}\left(W_{act}h_t\right),\qquad W_{out}=W_{act}^{\top}"),
    "loss": (r"\mathcal{L}=\lambda_{act}\mathcal{L}_{act}+\lambda_{rem}\mathcal{L}_{rem}"
             r"+\lambda_{imp}\mathcal{L}_{imp}+\lambda_{bn}\mathcal{L}_{bn}"),
    "lr": (r"\eta_t=\min\left(\eta_{max}\frac{t}{T_w},\ \eta_{min}+\frac{\eta_{max}-\eta_{min}}{2}"
           r"\left(1+\cos\left(\pi\frac{t-T_w}{T-T_w}\right)\right)\right)"),
    "clip": r"g\leftarrow g\cdot\min\left(1,\frac{c}{\|g\|_2}\right)",
    "swa": r"\theta_{SWA}=\frac{1}{K}\sum_{k=1}^{K}\theta_k",
    "complex": r"\mathcal{O}\left(n^{2}d+nd^{2}\right)",
    "ewma": r"\bar{T}_t=\alpha T_t+\left(1-\alpha\right)\bar{T}_{t-1}",
    "alert": r"A_t=\mathbf{1}\left[\hat{R}_t>\rho\,R^{SLO}\right]",
    "policy": r"a^{*}=\arg\max_{a\in\mathcal{A}}\ \mathrm{E}\left[U\left(a\mid s_t\right)\right]",
    "topk": (r"\mathrm{Acc@}k=\frac{1}{N}\sum_{i=1}^{N}\mathbf{1}\left[y_i\in"
             r"\mathrm{TopK}\left(\hat{p}_i,k\right)\right]"),
    "precision": r"P_c=\frac{TP_c}{TP_c+FP_c}",
    "recall": r"R_c=\frac{TP_c}{TP_c+FN_c}",
    "f1": r"F1_c=\frac{2\,P_c\,R_c}{P_c+R_c}",
    "macrof1": r"\mathrm{MacroF1}=\frac{1}{C}\sum_{c=1}^{C}F1_c",
}

# ordering defines the equation numbers per chapter
ORDER_CH3 = ["class_weight", "gap", "role", "freq", "relpos", "input", "attn", "mha",
             "resid", "ffn", "dilconv", "tcn", "xattn", "gnn_msg", "gnn_gate",
             "fusion", "tying", "loss", "lr", "clip", "swa", "complex",
             "ewma", "policy", "alert"]
ORDER_CH4 = ["topk", "precision", "recall", "f1", "macrof1"]

# (key, anchor-paragraph prefix, intro sentence with {} for the number)
# key == None means the intro introduces the equation group that follows
ANCHORS = [
    ("class_weight",
     "این رویکرد نرم‌شده، از یک سو کلاس‌های کم‌فراوان",
     "برای مقابله با عدم تعادل کلاس‌ها، به هر کلاس وزنی متناسب با معکوس فراوانی آن "
     "اختصاص می‌یابد؛ رابطه ({}) نحوه محاسبه این وزن را بیان می‌کند و نمای تعدیل‌کننده "
     "β از بیش‌وزن‌دهی به کلاس‌های بسیار نادر جلوگیری می‌نماید."),
    ("gap",
     "پس از نرمال‌سازی، هر مقدار اسکالر از طریق یک شبکه دو لایه",
     "رابطه ({}) دو گام این رمزگذاری را نشان می‌دهد: نخست نرمال‌سازی لگاریتمی بازه "
     "زمانی و سپس نگاشت آن به بردار d_model با یک شبکه پیش‌خور دو لایه."),
    ("role",
     "رمزگذاری نقش رویداد، دو ویژگی ساختاری مهم",
     "بردار دوبعدی نقش رویداد از طریق رابطه ({}) به فضای d_model نگاشت می‌شود."),
    ("freq",
     "رمزگذاری فراوانی فعالیت، اطلاعاتی درباره توزیع",
     "بردار فراوانی نسبی فعالیت‌ها و نگاشت خطی آن در رابطه ({}) فرموله شده است؛ این "
     "بردار به تمام توکن‌های توالی افزوده می‌شود و یک نمایش سراسری از ترکیب فعالیت‌های "
     "پیشوند فراهم می‌آورد."),
    ("relpos",
     "در محاسبه رمزگذاری موقعیت نسبی، ابتدا ماتریس فاصله",
     "رابطه ({}) میانگین تعبیه‌های موقعیت نسبی را برای هر توکن محاسبه می‌کند؛ در این "
     "رابطه D حداکثر فاصله مجاز (۱۲۸) و تابع clip مقادیر را در بازه [−D, D] محدود "
     "می‌سازد."),
    ("input",
     "استفاده از جمع به‌جای الحاق برای ترکیب تعبیه‌ها",
     "پس از جمع هشت مؤلفه تعبیه، نمایش ورودی از نرمال‌سازی لایه‌ای و لایه رهاکردن عبور "
     "می‌کند؛ رابطه ({}) نمایش نهایی ورودی به رمزگذار را نشان می‌دهد."),
    ("attn",
     "سازوکار خودتوجهی علّی، قلب جریان تبدیل کننده",
     "رابطه ({}) سازوکار توجه مقیاس‌شده را با ماتریس ماسک M بیان می‌کند که در آن "
     "موقعیت‌های آینده و توکن‌های پدینگ با مقدار منفی بی‌نهایت مسدود می‌شوند. رابطه "
     "({}) نیز خروجی توجه چندسری را از الحاق سرهای موازی می‌سازد."),
    (None, None, None),
    ("resid",
     "اتصالات باقی‌مانده در هر زیرلایه رمزگذار اعمال می‌شوند",
     "هر زیرلایه با اتصال باقی‌مانده و نرمال‌سازی لایه‌ای مطابق رابطه ({}) ترکیب "
     "می‌شود."),
    ("ffn",
     "هر لایه رمزگذار شامل یک شبکه پیش‌خور دو لایه",
     "شبکه پیش‌خور نقطه‌به‌نقطه با تابع فعال‌سازی GELU در رابطه ({}) تعریف می‌شود."),
    ("dilconv",
     "بلوک TCN در مدل پیشنهادی از سه لایه پیچشی",
     "پیچش dilated با گام d در رابطه ({}) و بلوک کامل TCN همراه با اتصال باقی‌مانده و "
     "ماسک پدینگ در رابطه ({}) فرموله شده است."),
    (None, None, None),
    ("xattn",
     "ادغام جریان TCN با جریان تبدیل کننده از طریق یک ماژول توجه متقابل",
     "رابطه ({}) توجه متقابل میان خروجی تبدیل کننده (به‌عنوان پرس‌وجو) و خروجی TCN "
     "(به‌عنوان کلید و مقدار) را بیان می‌کند."),
    ("gnn_msg",
     "در عملیات تجمیع پیام، برای هر گره، پیام‌های گره‌های همسایه",
     "گام تجمیع پیام و به‌روزرسانی نمایش گره در رابطه ({}) و مکانیزم دروازه‌ای با تابع "
     "سیگموئید در رابطه ({}) تعریف می‌شود."),
    (None, None, None),
    ("fusion",
     "ماژول ادغام سه‌گانه، خروجی سه جریان تبدیل کننده",
     "رابطه ({}) نحوه ترکیب الحاقی و عنصری سه جریان و تولید نمایش نهایی را نشان می‌دهد."),
    ("tying",
     "گره‌بندی وزنی یک تکنیک کارآمد است",
     "با گره‌بندی وزنی، ماتریس سر خروجی و ماتریس تعبیه فعالیت یکسان می‌شوند و لوجیت‌ها "
     "مطابق رابطه ({}) محاسبه می‌گردند."),
    ("loss",
     "تابع زیان مورد استفاده در این پژوهش، یک تابع زیان چندوظیفه‌ای",
     "رابطه ({}) تابع زیان چندوظیفه‌ای را با وزن‌های λ هر مؤلفه نشان می‌دهد."),
    ("lr",
     "زمان‌بند نرخ یادگیری از دو فاز تشکیل شده است",
     "رابطه ({}) زمان‌بند نرخ یادگیری را با فاز گرم‌کردن خطی و فاز کاهش کسینوسی به‌صورت "
     "یکپارچه بیان می‌کند؛ در این رابطه T_w تعداد مراحل گرم‌کردن و T تعداد کل مراحل "
     "آموزش است."),
    ("clip",
     "برش گرادیان با مقدار ۱٫۰ اعمال می‌شود",
     "رابطه ({}) نحوه محدودسازی نرم گرادیان‌ها با آستانه c را نشان می‌دهد."),
    ("swa",
     "میانگین‌گیری وزنی تصادفی (SWA) از دوره ۸۰ آموزش فعال می‌شود",
     "میانگین وزن‌های K نقطه از مسیر آموزش مطابق رابطه ({}) محاسبه می‌شود."),
    ("complex",
     "پیچیدگی زمانی رمزگذار تبدیل کننده از مرتبه",
     "رابطه ({}) مرتبه پیچیدگی محاسباتی جریان تبدیل کننده را بر حسب طول توالی n و "
     "ابعاد مدل d نشان می‌دهد."),
]

ANCHORS_CH4 = [
    ("topk",
     "جدول ۴.۳ دقت مدل پیشنهادی را در سطوح مختلف Top-k",
     "معیار دقت در سطح k مطابق رابطه ({}) تعریف می‌شود؛ در این رابطه برچسب واقعی نمونه "
     "i با مجموعه k پیش‌بینی برتر مدل مقایسه می‌گردد."),
    ("precision",
     None,
     "معیارهای ارزیابی به‌کاررفته در این پژوهش به‌صورت زیر تعریف می‌شوند. دقت "
     "(Precision) نسبت پیش‌بینی‌های صحیح یک کلاس به کل پیش‌بینی‌های آن کلاس است "
     "(رابطه {})."),
]

# ------------------------------------------------------------------- helpers
def fa_num(n):
    return str(n).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def el_from_string(xml):
    """Parse XML with python-docx's parser so the element gets its typed class
    (CT_P, CT_Tbl, ...) and Paragraph/Table wrappers keep working on it."""
    return parse_xml(xml.encode("utf-8"))


def make_run(text, rtl=True, bold=False, size=None):
    run = el_from_string("<w:r xmlns:w='%s'/>" % W_NS)
    rpr = etree.SubElement(run, w("rPr"))
    # rPr children must follow the schema order: b, sz, szCs, rtl, lang
    if bold:
        etree.SubElement(rpr, w("b"))
    if size:
        etree.SubElement(rpr, w("sz")).set(w("val"), str(size))
        etree.SubElement(rpr, w("szCs")).set(w("val"), str(size))
    if rtl:
        etree.SubElement(rpr, w("rtl"))
        lang = etree.SubElement(rpr, w("lang"))
        lang.set(w("bidi"), "fa-IR")
    t = etree.SubElement(run, w("t"))
    t.text = text
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    return run


def make_para(text, style_id=None, jc="both", rtl=True, bold=False,
              spacing_after=None, spacing_before=None, page_break_before=False):
    p = el_from_string("<w:p xmlns:w='%s'/>" % W_NS)
    ppr = etree.SubElement(p, w("pPr"))
    if style_id:
        etree.SubElement(ppr, w("pStyle")).set(w("val"), style_id)
    if page_break_before:
        etree.SubElement(ppr, w("pageBreakBefore"))
    if not rtl:
        etree.SubElement(ppr, w("bidi")).set(w("val"), "0")
    if spacing_after is not None or spacing_before is not None:
        sp = etree.SubElement(ppr, w("spacing"))
        if spacing_before is not None:
            sp.set(w("before"), str(spacing_before))
        if spacing_after is not None:
            sp.set(w("after"), str(spacing_after))
    if jc:
        etree.SubElement(ppr, w("jc")).set(w("val"), jc)
    if text:
        p.append(make_run(text, rtl=rtl, bold=bold))
    return p


def make_eq_table(omath, number_label, text_width=8503, num_width=1250):
    """Borderless 1x2 table: right cell = number (RTL table), left cell = equation."""
    eq_width = text_width - num_width
    tbl = el_from_string("""
<w:tbl xmlns:w="{w}">
  <w:tblPr>
    <w:tblStyle w:val="TableGrid"/>
    <w:bidiVisual/>
    <w:tblW w:w="{tw}" w:type="dxa"/>
    <w:jc w:val="center"/>
    <w:tblBorders>
      <w:top w:val="none" w:sz="0" w:space="0" w:color="auto"/>
      <w:left w:val="none" w:sz="0" w:space="0" w:color="auto"/>
      <w:bottom w:val="none" w:sz="0" w:space="0" w:color="auto"/>
      <w:right w:val="none" w:sz="0" w:space="0" w:color="auto"/>
      <w:insideH w:val="none" w:sz="0" w:space="0" w:color="auto"/>
      <w:insideV w:val="none" w:sz="0" w:space="0" w:color="auto"/>
    </w:tblBorders>
    <w:tblLayout w:type="fixed"/>
    <w:tblCellMar>
      <w:top w:w="0" w:type="dxa"/><w:left w:w="0" w:type="dxa"/>
      <w:bottom w:w="0" w:type="dxa"/><w:right w:w="0" w:type="dxa"/>
    </w:tblCellMar>
    <w:tblLook w:val="0000"/>
  </w:tblPr>
  <w:tblGrid>
    <w:gridCol w:w="{nw}"/>
    <w:gridCol w:w="{ew}"/>
  </w:tblGrid>
  <w:tr>
    <w:trPr><w:cantSplit/></w:trPr>
    <w:tc>
      <w:tcPr><w:tcW w:w="{nw}" w:type="dxa"/>
        <w:tcBorders>
          <w:top w:val="none" w:sz="0"/><w:left w:val="none" w:sz="0"/>
          <w:bottom w:val="none" w:sz="0"/><w:right w:val="none" w:sz="0"/>
        </w:tcBorders>
        <w:vAlign w:val="center"/>
      </w:tcPr>
      <w:p><w:pPr><w:bidi/>
        <w:spacing w:before="80" w:after="80" w:line="240" w:lineRule="auto"/>
        <w:jc w:val="right"/><w:rPr><w:rtl/></w:rPr></w:pPr>
        <w:r><w:rPr><w:sz w:val="24"/><w:szCs w:val="24"/><w:rtl/><w:lang w:bidi="fa-IR"/></w:rPr>
          <w:t>{num}</w:t></w:r>
      </w:p>
    </w:tc>
    <w:tc>
      <w:tcPr><w:tcW w:w="{ew}" w:type="dxa"/>
        <w:tcBorders>
          <w:top w:val="none" w:sz="0"/><w:left w:val="none" w:sz="0"/>
          <w:bottom w:val="none" w:sz="0"/><w:right w:val="none" w:sz="0"/>
        </w:tcBorders>
        <w:vAlign w:val="center"/>
      </w:tcPr>
      <w:p><w:pPr><w:bidi w:val="0"/>
        <w:spacing w:before="80" w:after="80" w:line="240" w:lineRule="auto"/>
        <w:jc w:val="center"/><w:rPr><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr></w:pPr>
      </w:p>
    </w:tc>
  </w:tr>
</w:tbl>""".format(w=W_NS, tw=text_width, nw=num_width, ew=eq_width, num=number_label))
    eq_p = tbl.findall(".//" + w("tr"))[0].findall(w("tc"))[1].find(w("p"))
    eq_p.append(omath)
    return tbl


def make_data_table(rows, widths, text_width=8503):
    cols = len(widths)
    grid = "".join('<w:gridCol w:w="%d"/>' % wd for wd in widths)
    trs = []
    for r_i, row in enumerate(rows):
        tcs = []
        for c_i, cell in enumerate(row):
            bold = r_i == 0
            shd = ('<w:shd w:val="clear" w:color="auto" w:fill="F2F2F2"/>' if bold else "")
            ppr = ('<w:pPr><w:bidi/>'
                   '<w:spacing w:before="40" w:after="40" w:line="240" w:lineRule="auto"/>'
                   '<w:jc w:val="center"/></w:pPr>')
            rpr = '<w:rPr>%s<w:sz w:val="22"/><w:szCs w:val="22"/><w:rtl/></w:rPr>' % (
                "<w:b/>" if bold else "")
            tcs.append(
                '<w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/>%s'
                '<w:tcMar><w:top w:w="60" w:type="dxa"/>'
                '<w:left w:w="80" w:type="dxa"/><w:bottom w:w="60" w:type="dxa"/>'
                '<w:right w:w="80" w:type="dxa"/></w:tcMar><w:vAlign w:val="center"/></w:tcPr>'
                '<w:p>%s<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r></w:p></w:tc>'
                % (widths[c_i], shd, ppr, rpr, cell))
        trs.append("<w:tr><w:trPr><w:cantSplit/></w:trPr>%s</w:tr>" % "".join(tcs))
    xml = ('<w:tbl xmlns:w="%s"><w:tblPr><w:tblStyle w:val="TableGrid"/><w:bidiVisual/>'
           '<w:tblW w:w="%d" w:type="dxa"/><w:jc w:val="center"/>'
           '<w:tblBorders>'
           '<w:top w:val="single" w:sz="6" w:space="0" w:color="auto"/>'
           '<w:left w:val="single" w:sz="6" w:space="0" w:color="auto"/>'
           '<w:bottom w:val="single" w:sz="6" w:space="0" w:color="auto"/>'
           '<w:right w:val="single" w:sz="6" w:space="0" w:color="auto"/>'
           '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
           '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
           '</w:tblBorders><w:tblLayout w:type="fixed"/>'
           '<w:tblCellMar><w:top w:w="40" w:type="dxa"/><w:left w:w="60" w:type="dxa"/>'
           '<w:bottom w:w="40" w:type="dxa"/><w:right w:w="60" w:type="dxa"/></w:tblCellMar>'
           '</w:tblPr><w:tblGrid>%s</w:tblGrid>%s</w:tbl>'
           % (W_NS, text_width, grid, "".join(trs)))
    return el_from_string(xml)


# ------------------------------------------------------- LaTeX -> OMML (pandoc)
def build_omml_map(keys):
    tmpdir = tempfile.mkdtemp()
    tex_path = os.path.join(tmpdir, "eqs.tex")
    docx_path = os.path.join(tmpdir, "eqs.docx")
    lines = []
    for k in keys:
        lines.append("EQMARK%s" % re.sub(r"[^A-Za-z0-9]", "", k))
        lines.append("")
        lines.append("$$%s$$" % EQ[k])
        lines.append("")
    with open(tex_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    subprocess.check_call([PANDOC, tex_path, "-o", docx_path])
    with zipfile.ZipFile(docx_path) as zf:
        xml = zf.read("word/document.xml")
    root = etree.fromstring(xml)
    body = root.find(w("body"))
    paras = body.findall(w("p"))
    out = {}
    safe_to_key = {re.sub(r"[^A-Za-z0-9]", "", k): k for k in keys}
    for i, p in enumerate(paras):
        text = "".join(p.itertext()).strip()
        mark = re.match(r"^EQMARK([A-Za-z0-9]+)$", text)
        if not mark:
            continue
        key = safe_to_key.get(mark.group(1))
        if key is None:
            continue
        # find next paragraph carrying math
        for nxt in paras[i + 1:]:
            omath = nxt.find(m("oMathPara"))
            if omath is not None:
                inner = omath.find(m("oMath"))
                out[key] = copy.deepcopy(inner)
                break
            omath = nxt.find(m("oMath"))
            if omath is not None:
                out[key] = copy.deepcopy(omath)
                break
    missing = [k for k in keys if k not in out]
    if missing:
        raise RuntimeError("pandoc did not produce math for: %s" % missing)
    # uniform, clean math typography (Cambria Math, 12 pt like the body text)
    for omath in out.values():
        for mr in omath.iter(m("r")):
            rpr = etree.Element(w("rPr"))
            fonts = etree.SubElement(rpr, w("rFonts"))
            for a in ("ascii", "hAnsi", "cs"):
                fonts.set(w(a), "Cambria Math")
            etree.SubElement(rpr, w("sz")).set(w("val"), "24")
            etree.SubElement(rpr, w("szCs")).set(w("val"), "24")
            t = mr.find(m("t"))
            if t is not None:
                t.addprevious(rpr)
            else:
                mr.append(rpr)
    return out
