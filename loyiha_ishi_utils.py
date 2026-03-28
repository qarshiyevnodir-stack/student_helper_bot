
import os
import re
import logging
from io import BytesIO
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from openai import OpenAI

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
client = OpenAI()

# Rasmlar yo'li
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
GERB_PATH  = os.path.join(ASSETS_DIR, "gerb.jpeg")
KITOB_PATH = os.path.join(ASSETS_DIR, "kitob.png")


# ─────────────────────────────────────────────
# Yordamchi funksiyalar
# ─────────────────────────────────────────────

def strip_markdown(text: str) -> str:
    """GPT javobidagi markdown belgilarini tozalaydi."""
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,3}(.*?)_{1,3}', r'\1', text)
    text = re.sub(r'`(.*?)`', r'\1', text)
    text = re.sub(r'^[-\*]{3,}\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def add_page_border(document):
    """Har sahifaga to'rtburchak ramka qo'shadi."""
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    for section in document.sections:
        sectPr = section._sectPr
        for old in sectPr.findall(qn('w:pgBorders')):
            sectPr.remove(old)
        pgBorders = OxmlElement('w:pgBorders')
        pgBorders.set(qn('w:offsetFrom'), 'page')
        for edge in ('top', 'left', 'bottom', 'right'):
            border_el = OxmlElement(f'w:{edge}')
            border_el.set(qn('w:val'),   'single')
            border_el.set(qn('w:sz'),    '18')
            border_el.set(qn('w:space'), '24')
            border_el.set(qn('w:color'), '000000')
            pgBorders.append(border_el)
        sectPr.append(pgBorders)


def set_font(run, size=14, bold=False, italic=False, name='Times New Roman'):
    run.font.name = name
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic


def add_paragraph(doc, text='', alignment=WD_ALIGN_PARAGRAPH.LEFT,
                  size=14, bold=False, italic=False,
                  space_before=0, space_after=6):
    p = doc.add_paragraph()
    p.alignment = alignment
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after  = Pt(space_after)
    if text:
        r = p.add_run(text)
        set_font(r, size=size, bold=bold, italic=italic)
    return p


def gpt_generate(prompt: str, system: str = "Siz foydali yordamchisiz.") -> str:
    try:
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
        )
        return strip_markdown(resp.choices[0].message.content.strip())
    except Exception as e:
        logging.error(f"GPT xatolik: {e}")
        return f"Kontent yaratishda xatolik: {e}"


# ─────────────────────────────────────────────
# 1-sahifa: Muqova
# ─────────────────────────────────────────────

def create_cover_page(doc, university_info, subject_name, topic, name_surname, teacher_name):
    """
    Muqova sahifasi:
      - Yuqorida: O'zbekiston gerbi rasmi (markazlashgan)
      - Ta'lim muassasa nomi (agar kiritilsa, markazlashgan, qalin)
      - Fan nomi (markazlashgan, qalin)
      - LOYIHA ISHI (juda katta, markazlashgan, qalin)
      - Mavzu: ... (markazlashgan, qalin)
      - Bajardi: Ism Familiya (chapga, qalin)
      - Qabul qildi: O'qituvchi (chapga, qalin)
      - Pastda: kitob rasmi (markazlashgan)
    """
    # ── Gerb rasmi ──
    if os.path.exists(GERB_PATH):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after  = Pt(6)
        run = p.add_run()
        run.add_picture(GERB_PATH, width=Inches(4.5))

    # ── Ta'lim muassasasi (agar kiritilsa) ──
    if university_info and university_info.strip():
        add_paragraph(doc, university_info.strip().upper(),
                      alignment=WD_ALIGN_PARAGRAPH.CENTER,
                      size=14, bold=True, space_before=4, space_after=2)

    # ── Fan nomi (agar kiritilsa) ──
    if subject_name and subject_name.strip():
        add_paragraph(doc, subject_name.strip().upper(),
                      alignment=WD_ALIGN_PARAGRAPH.CENTER,
                      size=14, bold=True, space_before=2, space_after=12)

    # ── LOYIHA ISHI ──
    add_paragraph(doc, "LOYIHA ISHI",
                  alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  size=36, bold=True, space_before=18, space_after=12)

    # ── Mavzu ──
    if topic and topic.strip():
        add_paragraph(doc, f"Mavzu: {topic.strip()}",
                      alignment=WD_ALIGN_PARAGRAPH.CENTER,
                      size=14, bold=True, space_before=6, space_after=18)

    # ── Bajardi ──
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after  = Pt(2)
    r = p.add_run("Bajardi: ")
    set_font(r, size=14, bold=True)
    if name_surname and name_surname.strip():
        r2 = p.add_run(name_surname.strip())
        set_font(r2, size=14, bold=True)

    # ── Qabul qildi ──
    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p2.paragraph_format.space_before = Pt(2)
    p2.paragraph_format.space_after  = Pt(24)
    r3 = p2.add_run("Qabul qildi: ")
    set_font(r3, size=14, bold=True)
    if teacher_name and teacher_name.strip():
        r4 = p2.add_run(teacher_name.strip())
        set_font(r4, size=14, bold=True)

    # ── Kitob rasmi (pastda) ──
    if os.path.exists(KITOB_PATH):
        p3 = doc.add_paragraph()
        p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p3.paragraph_format.space_before = Pt(0)
        p3.paragraph_format.space_after  = Pt(0)
        run3 = p3.add_run()
        run3.add_picture(KITOB_PATH, width=Inches(1.8))

    doc.add_page_break()


# ─────────────────────────────────────────────
# 2-sahifa: Reja
# ─────────────────────────────────────────────

def create_plan_page(doc, topic, language):
    """GPT yordamida reja tuzadi va sahifaga yozadi. plan_items ro'yxatini qaytaradi."""
    lang_map = {
        "uz": "o'zbek", "en": "ingliz", "ru": "rus",
        "ko": "kores",  "zh": "xitoy",  "de": "nemis",
        "kaa": "qoraqalpoq", "tk": "turkman", "tg": "tojik",
    }
    lang_name = lang_map.get(language, "o'zbek")

    prompt = (
        f"'{topic}' mavzusida loyiha ishi uchun reja tuzing ({lang_name} tilida).\n"
        f"Faqat quyidagi formatda yozing:\n"
        f"Kirish\n"
        f"1. [birinchi asosiy bo'lim]\n"
        f"2. [ikkinchi asosiy bo'lim]\n"
        f"3. [uchinchi asosiy bo'lim]\n"
        f"4. [to'rtinchi asosiy bo'lim]\n"
        f"Xulosa\n"
        f"Foydalanilgan adabiyotlar\n"
        f"Boshqa hech narsa yozmang. Raqamlarni faqat asosiy bo'limlarga qo'ying."
    )
    raw = gpt_generate(prompt)

    # Reja sarlavhasi
    add_paragraph(doc, "Reja", alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  size=16, bold=True, space_before=0, space_after=12)

    plan_items = []
    no_number = {"kirish", "xulosa", "foydalanilgan adabiyotlar",
                 "introduction", "conclusion", "references",
                 "введение", "заключение", "список литературы"}

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        clean = re.sub(r'^[\d]+[\d\.]*\.?\s*', '', line).strip()
        is_special = clean.lower() in no_number

        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after  = Pt(4)
        r = p.add_run(clean)
        set_font(r, size=14, bold=is_special)

        if not is_special:
            plan_items.append(clean)

    doc.add_page_break()
    return plan_items


# ─────────────────────────────────────────────
# Qolgan sahifalar
# ─────────────────────────────────────────────

def add_section(doc, title, content, is_heading=True):
    """Sarlavha va matnni hujjatga qo'shadi."""
    if is_heading:
        add_paragraph(doc, title, alignment=WD_ALIGN_PARAGRAPH.CENTER,
                      size=14, bold=True, space_before=12, space_after=6)
    for para in content.split('\n'):
        para = para.strip()
        if para:
            add_paragraph(doc, para, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY,
                          size=14, space_before=0, space_after=6)


def create_content_pages(doc, topic, language, plan_items, page_count):
    """Kirish, asosiy bo'limlar, xulosa va adabiyotlarni yaratadi."""
    lang_map = {
        "uz": "o'zbek", "en": "ingliz", "ru": "rus",
        "ko": "kores",  "zh": "xitoy",  "de": "nemis",
        "kaa": "qoraqalpoq", "tk": "turkman", "tg": "tojik",
    }
    lang_name = lang_map.get(language, "o'zbek")

    words_per_page = 300
    main_sections  = len(plan_items) if plan_items else 4
    intro_words    = words_per_page
    conclusion_words = words_per_page
    main_words_each  = max(
        words_per_page,
        int((page_count - 3) * words_per_page / max(main_sections, 1))
    )

    sys_msg = (
        f"Siz {lang_name} tilida akademik matn yozuvchi mutaxasssissiz. "
        f"Faqat sof matn yozing, markdown belgilari ishlatmang."
    )

    # ── Kirish ──
    intro = gpt_generate(
        f"'{topic}' mavzusida loyiha ishi uchun kirish qismini yozing "
        f"({lang_name} tilida, taxminan {intro_words} so'z). "
        f"Mavzuning dolzarbligi, maqsad va vazifalari haqida yozing.",
        system=sys_msg
    )
    add_section(doc, "Kirish", intro)
    doc.add_page_break()

    # ── Asosiy bo'limlar ──
    for i, section_title in enumerate(plan_items, 1):
        content = gpt_generate(
            f"'{topic}' mavzusida loyiha ishi uchun '{section_title}' bo'limini yozing "
            f"({lang_name} tilida, taxminan {main_words_each} so'z). "
            f"Ilmiy uslubda, batafsil yozing.",
            system=sys_msg
        )
        add_section(doc, f"{i}. {section_title}", content)
        doc.add_page_break()

    # ── Xulosa ──
    conclusion = gpt_generate(
        f"'{topic}' mavzusida loyiha ishi uchun xulosa qismini yozing "
        f"({lang_name} tilida, taxminan {conclusion_words} so'z). "
        f"Asosiy natijalar va tavsiyalarni yozing.",
        system=sys_msg
    )
    add_section(doc, "Xulosa", conclusion)
    doc.add_page_break()

    # ── Foydalanilgan adabiyotlar ──
    refs = gpt_generate(
        f"'{topic}' mavzusida loyiha ishi uchun foydalanilgan adabiyotlar ro'yxatini tuzing "
        f"({lang_name} tilida, 8-10 ta manba). "
        f"Har bir manbani raqamlang: 1. Muallif. Kitob nomi. Nashriyot, yil.",
        system=sys_msg
    )
    add_section(doc, "Foydalanilgan adabiyotlar", refs)


# ─────────────────────────────────────────────
# Asosiy funksiya
# ─────────────────────────────────────────────

def generate_loyiha_ishi(topic, page_count, language,
                         name_surname, university_info,
                         subject_name, teacher_name):
    """To'liq loyiha ishi hujjatini yaratadi va BytesIO qaytaradi."""
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Times New Roman'
    style.font.size = Pt(14)

    # Sahifa sozlamalari
    for section in doc.sections:
        section.page_width  = Inches(8.27)   # A4
        section.page_height = Inches(11.69)
        section.left_margin   = Inches(1.18)
        section.right_margin  = Inches(0.79)
        section.top_margin    = Inches(0.98)
        section.bottom_margin = Inches(0.98)

    # Ramka
    add_page_border(doc)

    # 1. Muqova
    create_cover_page(doc, university_info, subject_name, topic, name_surname, teacher_name)

    # 2. Reja
    plan_items = create_plan_page(doc, topic, language)

    # 3. Kontent
    create_content_pages(doc, topic, language, plan_items, page_count)

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf
