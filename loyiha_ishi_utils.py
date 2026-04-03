"""
loyiha_ishi_utils.py — Yangi shablon asosida Loyiha Ishi yaratuvchi modul.

Shablon sahifalari (LOYIHAISHI.docx dizaynidan ilhomlangan):
  Sahifa 1: Muqova (O'zbekiston gerbi, "LOYIHA ISHI", bajardi)
  Sahifa 2: Kirish sahifasi (sarlavha + rasm + matn)
  Sahifa 3+: Almashib keluvchi 4 ta shablon (A, B, C, D)

Mantiq:
  5  sahifa -> muqova + kirish + 3 content (A, B, C)
  10 sahifa -> muqova + kirish + 8 content (A,B,C,D,A,B,C,D)
  15 sahifa -> muqova + kirish + 13 content
  20+ sahifa -> har 5 ta yangi content qo'shiladi
"""

import os
import re
import logging
import tempfile
import requests
from io import BytesIO

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from openai import OpenAI

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
client = OpenAI()

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
GERB_PATH  = os.path.join(ASSETS_DIR, "gerb.jpeg")
KITOB_PATH = os.path.join(ASSETS_DIR, "kitob.png")

GOLD_COLOR = (200, 160, 0)   # Sariq/oltin rang


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


def set_font(run, size=14, bold=False, italic=False,
             name='Times New Roman', color=None):
    run.font.name = name
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    if color:
        run.font.color.rgb = RGBColor(*color)


def add_paragraph(doc_or_cell, text='', alignment=WD_ALIGN_PARAGRAPH.LEFT,
                  size=14, bold=False, italic=False,
                  space_before=0, space_after=6, color=None):
    p = doc_or_cell.add_paragraph()
    p.alignment = alignment
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after  = Pt(space_after)
    if text:
        r = p.add_run(text)
        set_font(r, size=size, bold=bold, italic=italic, color=color)
    return p


def add_page_border(document):
    """Barcha sahifalarga qora chegara qo'shadi."""
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


def remove_cell_borders(cell):
    """Jadval katakchasidan chegara olib tashlanadi."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement('w:tcBorders')
    for edge in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
        el = OxmlElement(f'w:{edge}')
        el.set(qn('w:val'), 'none')
        tcBorders.append(el)
    tcPr.append(tcBorders)


def add_gold_line(doc, width=30):
    """Sariq/oltin ajratuvchi chiziq qo'shadi."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after  = Pt(4)
    run = p.add_run("─" * width)
    set_font(run, size=10, color=GOLD_COLOR)
    return p


# ─────────────────────────────────────────────
# Rasm yuklash
# ─────────────────────────────────────────────

def fetch_topic_images(topic: str, count: int = 10) -> list:
    """Mavzuga oid rasmlarni Unsplash dan yuklab, yo'llar ro'yxatini qaytaradi."""
    images = []
    keyword = gpt_generate(
        f"'{topic}' mavzusi uchun eng mos 1-2 ta inglizcha kalit so'z yozing "
        f"(faqat kalit so'zlar, boshqa hech narsa yo'q).",
        system="Siz tarjimon va kalit so'z mutaxassisizsiz."
    ).split('\n')[0].strip()
    logging.info(f"Rasm qidirish kalit so'zi: {keyword}")

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = f"https://source.unsplash.com/featured/1200x800/?{requests.utils.quote(keyword)}"
        for i in range(count):
            r = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            if r.status_code == 200 and r.headers.get('content-type', '').startswith('image'):
                tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
                tmp.write(r.content)
                tmp.close()
                images.append(tmp.name)
    except Exception as e:
        logging.warning(f"Unsplash xatolik: {e}")

    # Yetarli rasm bo'lmasa, picsum.photos dan olamiz
    while len(images) < count:
        try:
            r = requests.get(
                f"https://picsum.photos/1200/800?random={len(images) + 100}",
                timeout=10, allow_redirects=True
            )
            if r.status_code == 200:
                tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
                tmp.write(r.content)
                tmp.close()
                images.append(tmp.name)
        except Exception:
            break

    return images


# ─────────────────────────────────────────────
# GPT: Reja va kontent
# ─────────────────────────────────────────────

def generate_plan(topic: str, language: str, section_count: int) -> list:
    """Loyiha ishi bo'limlari rejasini yaratadi."""
    lang_map = {
        'uz': "o'zbek", 'ru': "rus", 'en': "ingliz",
        'ko': "kores",  'zh': "xitoy", 'de': "nemis"
    }
    lang_name = lang_map.get(language, "o'zbek")
    prompt = (
        f"'{topic}' mavzusida loyiha ishi uchun {section_count} ta bo'lim nomini yozing. "
        f"Har bir bo'lim nomi yangi qatorda bo'lsin. "
        f"Faqat bo'lim nomlarini yozing, raqam yoki boshqa belgi qo'shmang. "
        f"Til: {lang_name}."
    )
    result = gpt_generate(prompt, system="Siz akademik reja tuzuvchi mutaxassississiz.")
    items = [re.sub(r'^[\d\.\-\*\s]+', '', line).strip()
             for line in result.split('\n') if line.strip()]
    return [item for item in items if item][:section_count]


def generate_section_content(topic: str, section_title: str, language: str,
                              word_count: int = 200) -> str:
    """Bir bo'lim uchun matn yaratadi."""
    lang_map = {
        'uz': "o'zbek", 'ru': "rus", 'en': "ingliz",
        'ko': "kores",  'zh': "xitoy", 'de': "nemis"
    }
    lang_name = lang_map.get(language, "o'zbek")
    sys_msg = (
        f"Siz {lang_name} tilida akademik matn yozuvchi mutaxassississiz. "
        f"Faqat sof matn yozing, markdown belgilari ishlatmang."
    )
    prompt = (
        f"'{topic}' mavzusidagi loyiha ishi uchun '{section_title}' bo'limini yozing. "
        f"Til: {lang_name}. Taxminan {word_count} so'z. "
        f"Ilmiy uslubda, paragraflar bilan yozing."
    )
    return gpt_generate(prompt, system=sys_msg)


# ─────────────────────────────────────────────
# 1-SAHIFA: Muqova
# ─────────────────────────────────────────────

def create_cover_page(doc, university_info, subject_name, topic,
                      name_surname, teacher_name):
    """O'zbekiston gerbi bilan rasmiy muqova sahifasi."""
    # Gerb
    if os.path.exists(GERB_PATH):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after  = Pt(6)
        p.add_run().add_picture(GERB_PATH, width=Inches(2.5))

    # Muassasa nomi
    univ_text = university_info.strip().upper() if university_info and university_info.strip() \
        else "TA'LIM MUASSASA NOMI"
    add_paragraph(doc, univ_text,
                  alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  size=14, bold=True, space_before=4, space_after=2)

    # Fan nomi
    subj_text = subject_name.strip().upper() if subject_name and subject_name.strip() \
        else "TANLANGAN FANIDAN"
    add_paragraph(doc, subj_text,
                  alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  size=14, bold=True, space_before=0, space_after=12)

    # LOYIHA ISHI (katta sarlavha)
    add_paragraph(doc, "LOYIHA ISHI",
                  alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  size=36, bold=True, space_before=12, space_after=8)

    # Mavzu
    if topic and topic.strip():
        add_paragraph(doc, f"Mavzu: {topic.strip()}",
                      alignment=WD_ALIGN_PARAGRAPH.CENTER,
                      size=14, bold=True, space_before=4, space_after=16)

    # Bajardi
    p_b = doc.add_paragraph()
    p_b.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_b.paragraph_format.space_before = Pt(4)
    p_b.paragraph_format.space_after  = Pt(2)
    r1 = p_b.add_run("Bajardi: ")
    set_font(r1, size=14, bold=True)
    r2 = p_b.add_run(name_surname.strip() if name_surname else "")
    set_font(r2, size=14, bold=True)

    # O'qituvchi
    p_q = doc.add_paragraph()
    p_q.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_q.paragraph_format.space_before = Pt(2)
    p_q.paragraph_format.space_after  = Pt(20)
    r3 = p_q.add_run("Qabul qildi: ")
    set_font(r3, size=14, bold=True)
    r4 = p_q.add_run(teacher_name.strip() if teacher_name and teacher_name.strip() else "")
    set_font(r4, size=14)

    # Kitob rasmi
    if os.path.exists(KITOB_PATH):
        p_k = doc.add_paragraph()
        p_k.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_k.paragraph_format.space_before = Pt(0)
        p_k.paragraph_format.space_after  = Pt(0)
        p_k.add_run().add_picture(KITOB_PATH, width=Inches(1.8))

    doc.add_page_break()


# ─────────────────────────────────────────────
# 2-SAHIFA: Kirish (sariq dizayn)
# ─────────────────────────────────────────────

def create_intro_page(doc, topic, intro_text, img_path=None,
                      author='', extra_info=''):
    """
    Kirish sahifasi: katta sarlavha + rasm + sariq rangdagi matn bloklari.
    Shablon 2-sahifasiga mos (sariq uchburchak dizayn).
    """
    # Katta sarlavha
    add_paragraph(doc, topic,
                  alignment=WD_ALIGN_PARAGRAPH.LEFT,
                  size=22, bold=True, space_before=6, space_after=12)

    # Rasm
    if img_path and os.path.exists(img_path):
        try:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after  = Pt(10)
            p.add_run().add_picture(img_path, width=Inches(5.5))
        except Exception as e:
            logging.warning(f"Kirish rasmi: {e}")

    # Muallif (sariq rang)
    if author:
        add_paragraph(doc, author,
                      alignment=WD_ALIGN_PARAGRAPH.LEFT,
                      size=13, bold=False, space_before=6, space_after=4,
                      color=GOLD_COLOR)

    # Kirish matni
    if intro_text:
        for para in intro_text.split('\n'):
            para = para.strip()
            if para:
                add_paragraph(doc, para,
                              alignment=WD_ALIGN_PARAGRAPH.JUSTIFY,
                              size=13, space_before=2, space_after=4)

    # Qo'shimcha ma'lumot (sariq rang)
    if extra_info:
        add_paragraph(doc, extra_info,
                      alignment=WD_ALIGN_PARAGRAPH.LEFT,
                      size=12, bold=False, space_before=6, space_after=4,
                      color=GOLD_COLOR)

    doc.add_page_break()


# ─────────────────────────────────────────────
# CONTENT SAHIFALAR: A, B, C, D shablonlari
# ─────────────────────────────────────────────

def create_content_page_A(doc, heading, text_content, img_path=None):
    """
    Shablon A (3-sahifa): Sarlavha yuqorida, chap matn + o'ng rasm.
    INCREATE uslubi: sarlavha markazda, matn chap, rasm o'ng pastda.
    """
    # Sarlavha
    add_paragraph(doc, heading,
                  alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  size=16, bold=True, space_before=6, space_after=6)

    # Sariq chiziq
    add_gold_line(doc, 25)

    # Matn chap, rasm o'ng (jadval bilan)
    table = doc.add_table(rows=1, cols=2)
    remove_cell_borders(table.cell(0, 0))
    remove_cell_borders(table.cell(0, 1))

    # Chap: matn
    left_cell = table.cell(0, 0)
    left_cell.width = Inches(3.6)
    for para in text_content.split('\n'):
        para = para.strip()
        if not para:
            continue
        p = left_cell.add_paragraph(para)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after  = Pt(5)
        for run in p.runs:
            set_font(run, size=12)

    # O'ng: rasm
    right_cell = table.cell(0, 1)
    right_cell.width = Inches(2.4)
    if img_path and os.path.exists(img_path):
        try:
            p = right_cell.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run().add_picture(img_path, width=Inches(2.2))
        except Exception as e:
            logging.warning(f"Content A rasm: {e}")

    doc.add_page_break()


def create_content_page_B(doc, heading, text_content, img_path=None):
    """
    Shablon B (4-sahifa): Yuqorida to'liq kenglikdagi rasm,
    pastda sariq chiziq + sarlavha + matn.
    """
    # Yuqorida rasm
    if img_path and os.path.exists(img_path):
        try:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after  = Pt(8)
            p.add_run().add_picture(img_path, width=Inches(6.0))
        except Exception as e:
            logging.warning(f"Content B rasm: {e}")

    # Sarlavha
    add_paragraph(doc, heading,
                  alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  size=16, bold=True, space_before=6, space_after=2)

    # Sariq chiziq
    add_gold_line(doc, 25)

    # Matn
    for para in text_content.split('\n'):
        para = para.strip()
        if not para:
            continue
        p = doc.add_paragraph(para)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after  = Pt(4)
        for run in p.runs:
            set_font(run, size=12)

    doc.add_page_break()


def create_content_page_C(doc, heading, text_content, img_path=None):
    """
    Shablon C (5-sahifa): Sariq chiziq yuqorida, katta rasm,
    pastda katta sarlavha + matn bloki.
    """
    # Sariq chiziq yuqorida
    add_gold_line(doc, 20)

    # Katta rasm
    if img_path and os.path.exists(img_path):
        try:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after  = Pt(8)
            p.add_run().add_picture(img_path, width=Inches(6.0))
        except Exception as e:
            logging.warning(f"Content C rasm: {e}")

    # Katta sarlavha
    add_paragraph(doc, heading,
                  alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  size=20, bold=True, space_before=6, space_after=6)

    # Matn (markazda, katta)
    for para in text_content.split('\n'):
        para = para.strip()
        if not para:
            continue
        p = doc.add_paragraph(para)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after  = Pt(2)
        for run in p.runs:
            set_font(run, size=13, bold=True)

    doc.add_page_break()


def create_content_page_D(doc, heading, text_left, text_right=None):
    """
    Shablon D (6-sahifa): Ikki ustunli matn sahifasi.
    """
    # Sarlavha
    add_paragraph(doc, heading,
                  alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  size=16, bold=True, space_before=6, space_after=6)

    # Sariq chiziq
    add_gold_line(doc, 25)

    # Ikki ustunli jadval
    table = doc.add_table(rows=1, cols=2)
    remove_cell_borders(table.cell(0, 0))
    remove_cell_borders(table.cell(0, 1))

    # Chap ustun
    left_cell = table.cell(0, 0)
    left_cell.width = Inches(3.0)
    for para in text_left.split('\n'):
        para = para.strip()
        if not para:
            continue
        p = left_cell.add_paragraph(para)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after  = Pt(5)
        for run in p.runs:
            set_font(run, size=12)

    # O'ng ustun
    right_cell = table.cell(0, 1)
    right_cell.width = Inches(3.0)
    content_right = text_right or text_left
    for para in content_right.split('\n'):
        para = para.strip()
        if not para:
            continue
        p = right_cell.add_paragraph(para)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after  = Pt(5)
        for run in p.runs:
            set_font(run, size=12)

    doc.add_page_break()


# ─────────────────────────────────────────────
# OXIRGI SAHIFA: Xulosa + jadval + rasm
# ─────────────────────────────────────────────

def create_final_page(doc, topic, language, topic_images, img_idx):
    """
    Oxirgi sahifa: Xulosa va takliflar matni + taqqoslash jadvali + rasm.
    Bu sahifa har doim to'liq ma'lumot bilan to'ldiriladi.
    """
    lang_map = {
        'uz': "o'zbek", 'ru': "rus", 'en': "ingliz",
        'ko': "kores",  'zh': "xitoy", 'de': "nemis"
    }
    lang_name = lang_map.get(language, "o'zbek")

    # Sarlavha
    add_paragraph(doc, "Xulosa va takliflar",
                  alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  size=18, bold=True, space_before=6, space_after=4)

    # Sariq chiziq
    add_gold_line(doc, 25)

    # Xulosa matni (GPT)
    sys_msg = (
        f"Siz {lang_name} tilida akademik matn yozuvchi mutaxassississiz. "
        f"Faqat sof matn yozing, markdown belgilari ishlatmang."
    )
    conclusion = gpt_generate(
        f"'{topic}' mavzusida loyiha ishi uchun 'Xulosa va takliflar' qismini yozing "
        f"({lang_name} tilida, taxminan 120 so'z). "
        f"Asosiy natijalar va amaliy tavsiyalarni yozing.",
        system=sys_msg
    )
    for para in conclusion.split('\n'):
        para = para.strip()
        if para:
            add_paragraph(doc, para,
                          alignment=WD_ALIGN_PARAGRAPH.JUSTIFY,
                          size=12, space_before=0, space_after=4)

    # Jadval: Mavzu bo'yicha asosiy tushunchalar
    table_data_raw = gpt_generate(
        f"'{topic}' mavzusi bo'yicha 4 ta asosiy tushuncha va ularning qisqacha ta'rifini "
        f"yozing ({lang_name} tilida). "
        f"Har bir qator: 'Tushuncha | Ta'rif' formatida, faqat 4 ta qator, boshqa hech narsa yo'q.",
        system="Siz akademik jadval tuzuvchi mutaxassississiz. Faqat so'ralgan formatda javob bering."
    )

    # Jadval sarlavhasi
    add_paragraph(doc, "Asosiy tushunchalar jadvali",
                  alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  size=13, bold=True, space_before=10, space_after=4,
                  color=GOLD_COLOR)

    # Jadval yaratish (5 qator: 1 sarlavha + 4 ma'lumot)
    try:
        table = doc.add_table(rows=5, cols=2)
        table.style = 'Table Grid'

        # Sarlavha qatori
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = "Tushuncha"
        hdr_cells[1].text = "Ta'rif"
        for cell in hdr_cells:
            for para in cell.paragraphs:
                for run in para.runs:
                    set_font(run, size=12, bold=True, color=GOLD_COLOR)
            cell._tc.get_or_add_tcPr()

        # Ma'lumot qatorlari
        rows_data = []
        for line in table_data_raw.split('\n'):
            line = line.strip()
            if '|' in line:
                parts = [p.strip() for p in line.split('|', 1)]
                if len(parts) == 2 and parts[0] and parts[1]:
                    rows_data.append(parts)
            if len(rows_data) >= 4:
                break

        # Yetarli ma'lumot bo'lmasa, bo'sh qatorlar bilan to'ldirish
        while len(rows_data) < 4:
            rows_data.append(["-", "-"])

        for i, (term, definition) in enumerate(rows_data[:4]):
            row_cells = table.rows[i + 1].cells
            row_cells[0].text = term
            row_cells[1].text = definition
            for cell in row_cells:
                for para in cell.paragraphs:
                    for run in para.runs:
                        set_font(run, size=11)
    except Exception as e:
        logging.warning(f"Jadval yaratishda xatolik: {e}")

    # Rasm (mavzuga mos)
    img = topic_images[img_idx % len(topic_images)] if topic_images else None
    if img and os.path.exists(img):
        try:
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after  = Pt(4)
            p.add_run().add_picture(img, width=Inches(4.5))
        except Exception as e:
            logging.warning(f"Oxirgi sahifa rasmi: {e}")

    # Adabiyotlar (qisqa)
    add_paragraph(doc, "Foydalanilgan adabiyotlar",
                  alignment=WD_ALIGN_PARAGRAPH.LEFT,
                  size=13, bold=True, space_before=10, space_after=4)
    refs = gpt_generate(
        f"'{topic}' mavzusi bo'yicha 3 ta qisqa adabiyot manbasi yozing "
        f"({lang_name} tilida). Har biri yangi qatorda, raqam bilan. "
        f"Faqat 3 ta manba, boshqa hech narsa yo'q.",
        system="Siz akademik adabiyot ro'yxati tuzuvchisisiz."
    )
    for line in refs.split('\n'):
        line = line.strip()
        if line:
            add_paragraph(doc, line,
                          alignment=WD_ALIGN_PARAGRAPH.LEFT,
                          size=11, space_before=0, space_after=3)


# ─────────────────────────────
# Asosiy generator
# ───────────────────────────────────────────

def generate_loyiha_ishi(topic, page_count, language,
                         name_surname, university_info,
                         subject_name, teacher_name):
    """
    To'liq loyiha ishi hujjatini yaratadi va BytesIO qaytaradi.

    Sahifalar tuzilishi:
      1-sahifa : Muqova (har doim)
      2-sahifa : Kirish (har doim)
      3+ sahifa: A, B, C, D, A, B, C, D, ... (almashib keladi)

    Misollar:
      page_count=5  -> muqova + kirish + 3 content (A, B, C)
      page_count=10 -> muqova + kirish + 8 content (A,B,C,D,A,B,C,D)
      page_count=15 -> muqova + kirish + 13 content
    """
    lang_map = {
        'uz': "o'zbek", 'ru': "rus", 'en': "ingliz",
        'ko': "kores",  'zh': "xitoy", 'de': "nemis"
    }
    lang_name = lang_map.get(language, "o'zbek")

    # Nechta content sahifa kerak
    content_page_count = max(3, page_count - 2)

    # Rasmlar (kirish + content sahifalar uchun)
    img_count = content_page_count + 2
    logging.info(f"'{topic}' uchun {img_count} ta rasm yuklanmoqda...")
    topic_images = fetch_topic_images(topic, count=img_count)
    logging.info(f"Yuklangan rasmlar: {len(topic_images)}")

    # Bo'limlar rejasi
    plan_items = generate_plan(topic, language, content_page_count + 1)
    logging.info(f"Reja ({len(plan_items)} bo'lim): {plan_items}")

    # ── Hujjat yaratish ──
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Times New Roman'
    style.font.size = Pt(14)

    for section in doc.sections:
        section.page_width    = Inches(8.27)
        section.page_height   = Inches(11.69)
        section.left_margin   = Inches(1.18)
        section.right_margin  = Inches(0.79)
        section.top_margin    = Inches(0.98)
        section.bottom_margin = Inches(0.98)

    add_page_border(doc)

    # ── 1-SAHIFA: Muqova ──
    create_cover_page(
        doc,
        university_info=university_info,
        subject_name=subject_name,
        topic=topic,
        name_surname=name_surname,
        teacher_name=teacher_name
    )

    # ── 2-SAHIFA: Kirish ──
    img_idx = 0
    intro_section = plan_items[0] if plan_items else "Kirish"
    intro_text = generate_section_content(
        topic, intro_section, language, word_count=150
    )
    intro_img = topic_images[img_idx] if img_idx < len(topic_images) else None
    img_idx += 1

    create_intro_page(
        doc,
        topic=topic,
        intro_text=intro_text,
        img_path=intro_img,
        author=name_surname if name_surname else "",
        extra_info=f"Til: {lang_name.capitalize()} | Sahifalar: {page_count}"
    )

    # ── CONTENT SAHIFALAR (A, B, C, D almashib) ──
    template_cycle = ['A', 'B', 'C', 'D']

    for i in range(content_page_count):
        template_type = template_cycle[i % 4]

        # Bo'lim sarlavhasi (plan_items dan siklik)
        section_idx = (i + 1) % len(plan_items) if plan_items else 0
        section_title = plan_items[section_idx] if plan_items else f"Bo'lim {i + 1}"

        # Matn so'z soni
        word_count = 200 if template_type in ('A', 'B') else 150

        # Matn yaratish
        content = generate_section_content(
            topic, section_title, language, word_count=word_count
        )

        # Rasm (siklik)
        img = topic_images[img_idx % len(topic_images)] if topic_images else None
        img_idx += 1

        logging.info(
            f"Content {i + 1}/{content_page_count}: "
            f"shablon={template_type}, bo'lim={section_title!r}"
        )

        if template_type == 'A':
            create_content_page_A(doc, section_title, content, img_path=img)

        elif template_type == 'B':
            create_content_page_B(doc, section_title, content, img_path=img)

        elif template_type == 'C':
            create_content_page_C(doc, section_title, content, img_path=img)

        elif template_type == 'D':
            # Matnni ikki qismga bo'lamiz
            paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
            mid = len(paragraphs) // 2
            left_text  = '\n'.join(paragraphs[:mid]) if mid > 0 else content
            right_text = '\n'.join(paragraphs[mid:]) if mid < len(paragraphs) else content
            create_content_page_D(doc, section_title, left_text, right_text)

    # ── OXIRGI SAHIFA: Xulosa + jadval + rasm ──
    create_final_page(doc, topic, language, topic_images, img_idx)

    # ── Vaqtinchalik rasmlarni tozalash ──
    for img_path in topic_images:
        try:
            os.unlink(img_path)
        except Exception:
            pass

    # ── BytesIO ga saqlash ──
    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf
