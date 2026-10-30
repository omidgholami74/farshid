# -*- coding: utf-8 -*-
"""Second pass: typography and cover fixes."""
import os
import sys

import docx
from docx.oxml.ns import qn
from lxml import etree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_thesis as B  # noqa: E402

W = B.w


def rebuild_text(p, text):
    runs = p.runs
    if not runs:
        p._p.append(B.make_run(text))
        return
    runs[0].text = text
    for r in runs[1:]:
        r._r.getparent().remove(r._r)


def set_simple_heading(p, size=32):
    ppr = p._p.get_or_add_pPr()
    for ch in list(ppr):
        ppr.remove(ch)
    etree.SubElement(ppr, qn("w:pageBreakBefore"))
    sp = etree.SubElement(ppr, qn("w:spacing"))
    sp.set(qn("w:before"), "240")
    sp.set(qn("w:after"), "240")
    etree.SubElement(ppr, qn("w:jc")).set(qn("w:val"), "center")
    for run in p.runs:
        run.bold = True
        run.font.size = docx.shared.Pt(size / 2)
    for run in p.runs[1:]:
        run._r.getparent().remove(run._r)


def main():
    doc = docx.Document(B.DOCX)

    # 1) Arabic kaf / yeh -> Persian forms (cover page and everywhere else)
    norm = 0
    for p in doc.paragraphs:
        for run in p.runs:
            if not run.text:
                continue
            t = run.text.replace("\u0643", "\u06a9").replace("\u064a", "\u06cc")
            if t != run.text:
                norm += 1
                run.text = t

    # 2) cover cover-page details
    fixed = []
    for p in doc.paragraphs:
        t = p.text.strip()
        if t.startswith("پایان‌نامه کارشناسی") and "دکتری" in t:
            rebuild_text(p, "پایان‌نامه کارشناسی ارشد")
            fixed.append("درجه در صفحه عنوان")
        elif t.replace("\u200c", "") in ("May & 2026", "May&2026") or t == "May & 2026":
            rebuild_text(p, "May 2026")
            fixed.append("May 2026")
        elif t.startswith("شهریور 1405"):
            rebuild_text(p, "شهریور ۱۴۰۵")
            fixed.append("تاریخ صفحه عنوان")
        elif t.startswith("بهبود تاخیر زمانی"):
            rebuild_text(p, t.replace("تاخیر", "تأخیر"))
            fixed.append("عنوان: تأخیر")
    print("normalised runs:", norm, "| cover fixes:", fixed)

    # 3) empty headings create phantom TOC entries
    removed = 0
    for p in list(doc.paragraphs):
        if p.style.name.startswith("Heading") and not p.text.strip():
            p._p.getparent().remove(p._p)
            removed += 1
    print("empty headings removed:", removed)

    # 4) the sources heading must not take the next chapter number
    for p in doc.paragraphs:
        if p.text.strip() == "منابع":
            set_simple_heading(p)
            print("منابع heading -> unnumbered bold title")
            break

    doc.save(B.DOCX)
    doc = docx.Document(B.DOCX)
    xml = doc.element.xml
    print("oMath:", xml.count("<m:oMath"),
          "| tables:", len(doc.tables),
          "| عنوان:", "دانشکده مدیریت علم و فناوری" in xml,
          "| منابع:", "منابع" in xml)


if __name__ == "__main__":
    main()
