# اصلاح پایان‌نامه — راهنمای بازتولید

خروجی اصلی: `../payannameh.docx`
نسخه پیش از تغییرات: `payannameh.original.docx`

## اسکریپت‌ها
- `build_thesis.py` — تعریف معادله‌ها به LaTeX، ساخت جدول بی‌کادر شماره‌دار (۱×۲، راست‌به‌چپ)، ساخت جدول داده.
- `patch_doc.py` — درج ۳۰ رابطه در فصل‌های ۳ و ۴، افزودن بخش «معماری پرومتئوس و عامل هوشمند»، اصلاح منابع و عنوان‌ها.
- `fix_pass2.py` — اصلاحات صفحه عنوان، حروف عربی، حذف سرفصل خالی، تیتر «منابع».
- `validate.py` — بررسی ترتیب عناصر OOXML، شمارش معادله‌ها و جدول‌ها (`python validate.py [فایل]`).

## پیش‌نیازها
```bash
python3 -m venv .venv && .venv/bin/pip install python-docx lxml
# pandoc 3.x را در _work/pandoc قرار دهید
```

## بازتولید
```bash
cp _work/payannameh.original.docx payannameh.docx
.venv/bin/python _work/patch_doc.py
.venv/bin/python _work/fix_pass2.py
.venv/bin/python _work/validate.py
```

پس از باز کردن فایل در Word، به‌روزرسانی فیلدها (فهرست مطالب و شماره سرفصل‌ها) را تأیید کنید.
