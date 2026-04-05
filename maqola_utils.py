"""
maqola_utils.py — Sifatli akademik/ilmiy maqola yaratuvchi modul.

Tuzilma:
  1. Sarlavha sahifasi: mavzu, muallif, muassasa, annotatsiya, kalit so'zlar
  2. Kirish: dolzarblik, maqsad, vazifalar
  3. Asosiy bo'limlar (hajmga qarab 2-4 ta)
  4. Xulosa: natijalar va tavsiyalar
  5. Adabiyotlar ro'yxati

OPTIMIZATSIYA: Barcha kontent BITTA mega-so'rovda (JSON) olinadi.
"""

import os
import json
import logging
import re
from io import BytesIO

from docx import Document
from docx.shared import Pt, Inches, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from openai import OpenAI

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
client = OpenAI()

# Ranglar
DARK_BLUE  = (31, 73, 125)
GOLD_COLOR = (180, 140, 0)
GRAY_COLOR = (89, 89, 89)


# ─────────────────────────────────────────────
# Yordamchi funksiyalar
# ─────────────────────────────────────────────

def strip_markdown(text: str) -> str:
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,3}(.*?)_{1,3}', r'\1', text)
    text = re.sub(r'`(.*?)`', r'\1', text)
    text = re.sub(r'^[-\*]{3,}\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def set_font(run, size=12, bold=False, italic=False,
             name='Times New Roman', color=None):
    run.font.name = name
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    if color:
        run.font.color.rgb = RGBColor(*color)


def add_paragraph(doc_or_cell, text='', alignment=WD_ALIGN_PARAGRAPH.LEFT,
                  size=12, bold=False, italic=False,
                  space_before=0, space_after=6, color=None,
                  line_spacing=None):
    p = doc_or_cell.add_paragraph()
    p.alignment = alignment
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after  = Pt(space_after)
    if line_spacing:
        p.paragraph_format.line_spacing = Pt(line_spacing)
    if text:
        r = p.add_run(text)
        set_font(r, size=size, bold=bold, italic=italic, color=color)
    return p


def add_horizontal_line(doc, color_hex='1F497D'):
    """Ko'k rangli ajratuvchi chiziq."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after  = Pt(2)
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '12')
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), color_hex)
    pBdr.append(bottom)
    pPr.append(pBdr)
    return p


def add_page_border(document):
    """Barcha sahifalarga chegara."""
    for section in document.sections:
        sectPr = section._sectPr
        for old in sectPr.findall(qn('w:pgBorders')):
            sectPr.remove(old)
        pgBorders = OxmlElement('w:pgBorders')
        pgBorders.set(qn('w:offsetFrom'), 'page')
        for edge in ('top', 'left', 'bottom', 'right'):
            border_el = OxmlElement(f'w:{edge}')
            border_el.set(qn('w:val'),   'single')
            border_el.set(qn('w:sz'),    '12')
            border_el.set(qn('w:space'), '24')
            border_el.set(qn('w:color'), '1F497D')
            pgBorders.append(border_el)
        sectPr.append(pgBorders)


# ─────────────────────────────────────────────
# MEGA-SO'ROV: Barcha kontentni bitta so'rovda
# ─────────────────────────────────────────────

def generate_all_content(topic: str, language: str,
                          article_type: str, page_count: int) -> dict:
    """
    Maqolaning barcha kontentini BITTA GPT so'rovida oladi.

    Qaytaradi:
      {
        "title": "...",
        "annotation": "...",
        "keywords": ["...", "...", ...],
        "introduction": "...",
        "sections": [
          {"title": "...", "text": "..."},
          ...
        ],
        "conclusion": "...",
        "references": ["...", "...", ...]
      }
    """
    lang_map = {
        'uz': "o'zbek", 'ru': "rus", 'en': "ingliz",
        'ko': "kores",  'zh': "xitoy", 'de': "nemis"
    }
    type_map = {
        'ilmiy':       "ilmiy-tadqiqot",
        'publitsistik': "publitsistik",
        'tahliliy':    "tahliliy-analitik"
    }
    lang_name = lang_map.get(language, "o'zbek")
    type_name = type_map.get(article_type, "ilmiy-tadqiqot")

    # Hajmga qarab bo'limlar soni
    if page_count <= 3:
        section_count = 2
        word_per_section = 200
        intro_words = 120
        conclusion_words = 100
        ref_count = 5
    elif page_count <= 5:
        section_count = 3
        word_per_section = 250
        intro_words = 150
        conclusion_words = 120
        ref_count = 7
    else:  # 8 sahifa
        section_count = 4
        word_per_section = 300
        intro_words = 180
        conclusion_words = 150
        ref_count = 10

    system_msg = (
        f"Siz {lang_name} tilida {type_name} maqola yozuvchi mutaxassississiz. "
        f"Faqat sof matn yozing, markdown belgilari ishlatmang. "
        f"Javobingiz to'liq JSON formatida bo'lsin."
    )

    sections_template = "\n".join([
        f'    {{"title": "{i+1}-bo\'lim nomi", "text": "{word_per_section} so\'zlik akademik matn"}}'
        for i in range(section_count)
    ])

    prompt = f"""'{topic}' mavzusida {type_name} maqola uchun quyidagi JSON strukturasini to'ldiring.
Til: {lang_name}. Barcha matnlar {lang_name} tilida bo'lsin.
Maqola turi: {type_name}. Taxminiy hajm: {page_count} sahifa.

{{
  "title": "Maqolaning rasmiy sarlavhasi ({lang_name} tilida)",
  "annotation": "80-100 so'zlik annotatsiya (abstract) — maqolaning qisqacha mazmuni",
  "keywords": ["kalit so'z 1", "kalit so'z 2", "kalit so'z 3", "kalit so'z 4", "kalit so'z 5"],
  "introduction": "{intro_words} so'zlik kirish — dolzarblik, maqsad va vazifalar",
  "sections": [
{sections_template}
  ],
  "conclusion": "{conclusion_words} so'zlik xulosa — asosiy natijalar va amaliy tavsiyalar",
  "references": [
    "1. Birinchi adabiyot (APA formatida)",
    "2. Ikkinchi adabiyot",
    ... ({ref_count} ta manba)
  ]
}}

Faqat JSON qaytaring, boshqa hech narsa yo'q.
Bo'limlar soni: {section_count} ta. Har bir bo'lim {word_per_section} so'z atrofida bo'lsin."""

    try:
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user",   "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content.strip()
        data = json.loads(raw)
        logging.info(f"Maqola mega-so'rov muvaffaqiyatli: {len(data.get('sections', []))} bo'lim")
        return data
    except Exception as e:
        logging.error(f"Maqola mega-so'rov xatolik: {e}")
        return {
            "title": topic,
            "annotation": "Annotatsiya yaratishda xatolik.",
            "keywords": [topic],
            "introduction": "Kirish yaratishda xatolik.",
            "sections": [{"title": f"Bo'lim {i+1}", "text": "Matn yaratishda xatolik."} for i in range(2)],
            "conclusion": "Xulosa yaratishda xatolik.",
            "references": ["1. -"]
        }


# ─────────────────────────────────────────────
# DOCX YARATISH
# ─────────────────────────────────────────────

def build_maqola_docx(content: dict, topic: str, language: str,
                       article_type: str, page_count: int,
                       name_surname: str = '', university: str = '') -> BytesIO:
    """
    Maqola kontentidan professional DOCX hujjat yaratadi.
    """
    lang_map = {
        'uz': "O'zbek tili", 'ru': "Rus tili", 'en': "Ingliz tili",
        'ko': "Kores tili",  'zh': "Xitoy tili", 'de': "Nemis tili"
    }
    type_map = {
        'ilmiy':       "Ilmiy maqola",
        'publitsistik': "Publitsistik maqola",
        'tahliliy':    "Tahliliy maqola"
    }
    lang_display = lang_map.get(language, "O'zbek tili")
    type_display = type_map.get(article_type, "Ilmiy maqola")

    doc = Document()

    # Sahifa sozlamalari (A4)
    for section in doc.sections:
        section.page_width    = Inches(8.27)
        section.page_height   = Inches(11.69)
        section.left_margin   = Inches(1.18)
        section.right_margin  = Inches(0.79)
        section.top_margin    = Inches(0.98)
        section.bottom_margin = Inches(0.98)

    # Ko'k chegara
    add_page_border(doc)

    # Standart shrift
    style = doc.styles['Normal']
    style.font.name = 'Times New Roman'
    style.font.size = Pt(14)

    # ── 1-SAHIFA: Sarlavha ──
    # Maqola turi (kichik, ko'k)
    add_paragraph(doc, type_display.upper(),
                  alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  size=11, bold=False, space_before=0, space_after=4,
                  color=DARK_BLUE)

    # Asosiy sarlavha
    title = content.get("title", topic)
    add_paragraph(doc, title,
                  alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  size=18, bold=True, space_before=8, space_after=6,
                  color=DARK_BLUE)

    # Ko'k chiziq
    add_horizontal_line(doc)

    # Muallif va muassasa
    if name_surname and name_surname.strip():
        add_paragraph(doc, name_surname.strip(),
                      alignment=WD_ALIGN_PARAGRAPH.CENTER,
                      size=13, bold=True, space_before=8, space_after=2)
    if university and university.strip():
        add_paragraph(doc, university.strip(),
                      alignment=WD_ALIGN_PARAGRAPH.CENTER,
                      size=12, bold=False, italic=True,
                      space_before=0, space_after=2,
                      color=GRAY_COLOR)

    # Til va tur
    add_paragraph(doc, f"{lang_display}  |  {type_display}  |  ~{page_count} sahifa",
                  alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  size=11, bold=False, space_before=4, space_after=12,
                  color=GRAY_COLOR)

    # Ko'k chiziq
    add_horizontal_line(doc)

    # Annotatsiya bloki
    add_paragraph(doc, "ANNOTATSIYA",
                  alignment=WD_ALIGN_PARAGRAPH.LEFT,
                  size=12, bold=True, space_before=10, space_after=4,
                  color=DARK_BLUE)

    annotation = content.get("annotation", "")
    if annotation:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after  = Pt(6)
        p.paragraph_format.left_indent  = Inches(0.3)
        p.paragraph_format.right_indent = Inches(0.3)
        r = p.add_run(strip_markdown(annotation))
        set_font(r, size=12, italic=True, color=GRAY_COLOR)

    # Kalit so'zlar
    keywords = content.get("keywords", [])
    if keywords:
        kw_text = ", ".join(str(k) for k in keywords if k)
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after  = Pt(4)
        r1 = p.add_run("Kalit so'zlar: ")
        set_font(r1, size=12, bold=True, color=DARK_BLUE)
        r2 = p.add_run(kw_text)
        set_font(r2, size=12, italic=True)

    doc.add_page_break()

    # ── 2-SAHIFA+: Kirish ──
    add_paragraph(doc, "1. KIRISH",
                  alignment=WD_ALIGN_PARAGRAPH.LEFT,
                  size=15, bold=True, space_before=6, space_after=4,
                  color=DARK_BLUE)
    add_horizontal_line(doc)

    introduction = content.get("introduction", "")
    for para in introduction.split('\n'):
        para = strip_markdown(para).strip()
        if para:
            add_paragraph(doc, para,
                          alignment=WD_ALIGN_PARAGRAPH.JUSTIFY,
                          size=14, space_before=0, space_after=6,
                          line_spacing=18)

    # ── ASOSIY BO'LIMLAR ──
    sections = content.get("sections", [])
    for i, sec in enumerate(sections):
        sec_title = strip_markdown(str(sec.get("title", f"Bo'lim {i+1}"))).strip()
        sec_text  = strip_markdown(str(sec.get("text", ""))).strip()

        add_paragraph(doc, f"{i+2}. {sec_title.upper()}",
                      alignment=WD_ALIGN_PARAGRAPH.LEFT,
                      size=15, bold=True, space_before=12, space_after=4,
                      color=DARK_BLUE)
        add_horizontal_line(doc)

        for para in sec_text.split('\n'):
            para = para.strip()
            if para:
                add_paragraph(doc, para,
                              alignment=WD_ALIGN_PARAGRAPH.JUSTIFY,
                              size=14, space_before=0, space_after=6,
                              line_spacing=18)

    # ── XULOSA ──
    xulosa_num = len(sections) + 2
    add_paragraph(doc, f"{xulosa_num}. XULOSA",
                  alignment=WD_ALIGN_PARAGRAPH.LEFT,
                  size=15, bold=True, space_before=12, space_after=4,
                  color=DARK_BLUE)
    add_horizontal_line(doc)

    conclusion = content.get("conclusion", "")
    for para in conclusion.split('\n'):
        para = strip_markdown(para).strip()
        if para:
            add_paragraph(doc, para,
                          alignment=WD_ALIGN_PARAGRAPH.JUSTIFY,
                          size=14, space_before=0, space_after=6,
                          line_spacing=18)

    # ── ADABIYOTLAR ──
    add_paragraph(doc, "FOYDALANILGAN ADABIYOTLAR",
                  alignment=WD_ALIGN_PARAGRAPH.LEFT,
                  size=15, bold=True, space_before=14, space_after=4,
                  color=DARK_BLUE)
    add_horizontal_line(doc)

    references = content.get("references", [])
    for ref in references:
        ref = strip_markdown(str(ref)).strip()
        if ref:
            add_paragraph(doc, ref,
                          alignment=WD_ALIGN_PARAGRAPH.LEFT,
                          size=12, space_before=0, space_after=4)

    # BytesIO ga saqlash
    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────
# Asosiy generator
# ─────────────────────────────────────────────

def generate_maqola(topic: str, language: str, article_type: str,
                     page_count: int, name_surname: str = '',
                     university: str = '') -> BytesIO:
    """
    To'liq maqola hujjatini yaratadi va BytesIO qaytaradi.

    Parametrlar:
      topic        — maqola mavzusi
      language     — til kodi: uz/ru/en/ko/zh/de
      article_type — tur: ilmiy/publitsistik/tahliliy
      page_count   — hajm: 3/5/8
      name_surname — muallif ismi (ixtiyoriy)
      university   — muassasa nomi (ixtiyoriy)
    """
    logging.info(f"Maqola yaratilmoqda: '{topic}' | til={language} | tur={article_type} | hajm={page_count}")

    # Bitta mega-so'rov bilan barcha kontent
    content = generate_all_content(topic, language, article_type, page_count)

    # DOCX yaratish
    buf = build_maqola_docx(
        content=content,
        topic=topic,
        language=language,
        article_type=article_type,
        page_count=page_count,
        name_surname=name_surname,
        university=university,
    )

    logging.info("Maqola muvaffaqiyatli yaratildi.")
    return buf
