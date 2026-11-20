# -*- coding: utf-8 -*-
"""Insert three methodology slides before "مراحل اجرای پژوهش" (run from project root)."""
import copy
import os
import sys

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.util import Inches, Pt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PPTX = os.path.join(ROOT, "payan-name.pptx")

DONOR = 17          # slide 18: pre-processing, "روش و معماری" highlighted
INSERT_AT = 14      # before slide 15 ("مراحل اجرای پژوهش")

CHROME = {
    "!!مستطیل ثابت راست", "!!مستطیل ثابت چب",
    "!!دکمه اسلاید بعد", "!!دکمه فهرست مطالب", "!!دکمه اسلاید قبل",
    "!!آنالیز", "!!روش\u200cشناسی", "!!کلیات پژوهش", "!!پیشنینه پژوهش",
    "!!مقدمه پژوهش", "Rectangle 54", "Rectangle 52", "Rectangle 48",
    "!!دایره شماره صفحه", "شماره صفحه", "TextBox 36",
}

ACCENT = RGBColor(0x44, 0x72, 0xC4)
GREY = RGBColor(0x59, 0x59, 0x59)
DARK = RGBColor(0x26, 0x26, 0x26)

SLIDES = [
    dict(
        title="ستون یکم: فرآیندکاوی",
        sub="روش کشف و بازنمایی فرآیند از رویدادنگار",
        lines=[
            "واحد داده: رویداد سه‌گانه — شناسه پرونده، نام فعالیت، زمان وقوع",
            "کشف مدل مرجع فرآیند از رویدادنگار BPI Challenge 2012",
            "بررسی انطباق رفتار واقعی با مدل مرجع و استخراج انحراف ساختاری",
            "استخراج پیشوند–ادامه به‌عنوان واحد تحلیل مرحله بعد",
            "خروجی: مدل مرجع فرآیند و شاخص‌های ساختاری گلوگاه",
        ],
    ),
    dict(
        title="ستون دوم: یادگیری ماشین",
        sub="صورت‌بندی مسئله پیش‌بینی به‌صورت یادگیری چندوظیفه‌ای",
        lines=[
            "ورودی: پیشوند رویدادهای یک پرونده در حال اجرا",
            "خروجی‌ها: فعالیت بعدی، زمان باقی‌مانده، پتانسیل بهبود، نشانگر گلوگاه",
            "معماری سه‌جریانه: تبدیل‌کننده، TCN و GNN با ادغام توجه متقابل",
            "تقسیم داده بر اساس شناسه پرونده برای پرهیز از نشت اطلاعات",
            "سنجش: دقت Top-k، خطای زمان، و Precision/Recall/F1 به تفکیک کلاس",
        ],
    ),
    dict(
        title="ستون سوم: پرومتئوس به‌عنوان روش سنجش",
        sub="تفکیک لایه اندازه‌گیری از لایه استقرار و عملیات",
        lines=[
            "DevOps: چگونه مستقر کنیم — پرومتئوس: چه چیزی و با چه دقتی بسنجیم",
            "مدل اندازه‌گیری ابعادی: شاخص با برچسب نوع فرآیند، شعبه و مرحله",
            "نمونه‌برداری دوره‌ای: تبدیل رویداد گسسته به سری زمانی قابل تحلیل",
            "قاعده‌پذیر کردن فرضیه: قواعد ثبت و هشدار به‌جای قضاوت شخصی",
            "سامانه چندعاملی: هماهنگ‌کننده، ادراک، تشخیص، پیش‌بینی، برنامه‌ریز، مجری، ممیز",
            "سه شاخص داوری: نرخ تحقق هدف خدمت، زمان تشخیص، نرخ اقدام موفق",
        ],
    ),
]


def clone_slide(prs, src):
    new = prs.slides.add_slide(src.slide_layout)
    for sh in list(new.shapes):
        sh._element.getparent().remove(sh._element)

    tree = new.shapes._spTree
    for el in list(src.shapes._spTree):
        tag = el.tag.split("}")[-1]
        if tag in ("nvGrpSpPr", "grpSpPr"):
            continue
        c_nv = el.find(".//" + qn("p:cNvPr"))
        name = c_nv.get("name") if c_nv is not None else ""
        is_pic = el.find(".//" + qn("p:pic")) is not None
        if name not in CHROME and not is_pic:
            continue
        new_el = copy.deepcopy(el)
        for blip in new_el.iter(qn("a:blip")):
            rid = blip.get(qn("r:embed"))
            if not rid:
                continue
            img = src.part.related_part(rid)
            blip.set(qn("r:embed"), new.part.relate_to(img, RT.IMAGE))
        tree.append(new_el)
    return new


def set_paragraph(tf, text, size, color, bold=False, align=PP_ALIGN.CENTER):
    p = tf.paragraphs[0]
    for r in list(p.runs)[1:]:
        r._r.getparent().remove(r._r)
    if not p.runs:
        run = p.add_run()
    else:
        run = p.runs[0]
    run.text = text
    f = run.font
    f.size = Pt(size)
    f.bold = bold
    f.name = "Vazir"
    f.color.rgb = color
    p.alignment = align
    p._p.get_or_add_pPr().set("rtl", "1")
    return p


def main():
    prs = Presentation(PPTX)
    src = prs.slides[DONOR]

    added = []
    for spec in SLIDES:
        s = clone_slide(prs, src)

        # clear the leftover white text inside the content panel
        panel = next(sh for sh in s.shapes if sh.name == "!!مستطیل ثابت چب")
        set_paragraph(panel.text_frame, "", 20, RGBColor(0xFF, 0xFF, 0xFF))

        # title
        title = next(sh for sh in s.shapes if sh.name == "TextBox 36")
        title.left, title.top = Inches(0.95), Inches(0.42)
        title.width, title.height = Inches(8.9), Inches(0.78)
        set_paragraph(title.text_frame, spec["title"], 26, DARK, bold=False)

        # subtitle
        sub = s.shapes.add_textbox(Inches(0.95), Inches(1.22), Inches(8.9), Inches(0.42))
        sub.text_frame.word_wrap = True
        set_paragraph(sub.text_frame, spec["sub"], 15, GREY)

        # accent rule
        rule = s.shapes.add_shape(1, Inches(1.9), Inches(1.74), Inches(6.5), Pt(2.2))
        rule.fill.solid()
        rule.fill.fore_color.rgb = ACCENT
        rule.line.fill.background()
        rule.shadow.inherit = False

        # body lines
        body = s.shapes.add_textbox(Inches(0.75), Inches(1.98), Inches(9.35), Inches(4.55))
        tf = body.text_frame
        tf.word_wrap = True
        paras = spec["lines"]
        for i, line in enumerate(paras):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = PP_ALIGN.RIGHT
            p._p.get_or_add_pPr().set("rtl", "1")
            p.space_after = Pt(14)
            p.line_spacing = 1.25
            num = p.add_run()
            num.text = "%s) " % "۱۲۳۴۵۶"[i]
            num.font.size = Pt(16)
            num.font.name = "Vazir"
            num.font.color.rgb = ACCENT
            num.font.bold = True
            run = p.add_run()
            run.text = line
            run.font.size = Pt(16)
            run.font.name = "Vazir"
            run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

        added.append(s)

    # move the three slides before "مراحل اجرای پژوهش"
    sld_ids = prs.slides._sldIdLst
    ids = list(sld_ids)
    tail = ids[-3:]
    for el in tail:
        sld_ids.remove(el)
    for offset, el in enumerate(tail):
        sld_ids.insert(INSERT_AT + offset, el)

    # renumber page placeholders
    for i, s in enumerate(prs.slides, start=1):
        for sh in s.shapes:
            if sh.name == "شماره صفحه" and sh.has_text_frame:
                p = sh.text_frame.paragraphs[0]
                if p.runs:
                    p.runs[0].text = str(i)
                    for extra in list(p.runs)[1:]:
                        extra._r.getparent().remove(extra._r)

    prs.save(PPTX)

    chk = Presentation(PPTX)
    print("slides:", len(chk.slides))
    for i in range(13, 19):
        s = chk.slides[i]
        title = next((sh.text_frame.text for sh in s.shapes
                      if sh.name == "TextBox 36"), "")
        num = next((sh.text_frame.text for sh in s.shapes
                    if sh.name == "شماره صفحه"), "")
        print("%2d shapes=%2d page=%s title=%s" % (i + 1, len(s.shapes), num, title))


if __name__ == "__main__":
    main()
