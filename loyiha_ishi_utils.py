
import os
import re
import logging
import tempfile
import requests
from io import BytesIO
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from openai import OpenAI

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
client = OpenAI()

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
GERB_PATH  = os.path.join(ASSETS_DIR, "gerb.jpeg")
KITOB_PATH = os.path.join(ASSETS_DIR, "kitob.png")

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


def add_page_border(document):
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
# Rasm yuklash (Unsplash API orqali)
# ─────────────────────────────────────────────

def fetch_topic_images(topic: str, count: int = 4) -> list:
    """
    Mavzuga oid rasmlarni Unsplash dan yuklab, vaqtinchalik fayllar ro'yxatini qaytaradi.
    Agar Unsplash ishlamasa, Wikimedia Commons dan urinib ko'radi.
    """
    images = []
    # GPT yordamida inglizcha kalit so'z olamiz
    keyword = gpt_generate(
        f"'{topic}' mavzusi uchun eng mos 1-2 ta inglizcha kalit so'z yozing "
        f"(faqat kalit so'zlar, boshqa hech narsa yo'q).",
        system="Siz tarjimon va kalit so'z mutaxassisizsiz."
    ).split('\n')[0].strip()

    logging.info(f"Rasm qidirish uchun kalit so'z: {keyword}")

    # Unsplash (API key shart emas — demo endpoint)
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = f"https://source.unsplash.com/featured/800x600/?{requests.utils.quote(keyword)}"
        for i in range(count):
            r = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            if r.status_code == 200 and r.headers.get('content-type', '').startswith('image'):
                tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
                tmp.write(r.content)
                tmp.close()
                images.append(tmp.name)
                logging.info(f"Rasm {i+1} yuklandi: {tmp.name}")
    except Exception as e:
        logging.warning(f"Unsplash xatolik: {e}")

    # Agar yetarli rasm bo'lmasa — Wikimedia Commons dan urinib ko'ramiz
    if len(images) < count:
        try:
            search_url = (
                f"https://commons.wikimedia.org/w/api.php"
                f"?action=query&list=search&srsearch={requests.utils.quote(keyword)}"
                f"&srnamespace=6&srlimit={count * 2}&format=json"
            )
            resp = requests.get(search_url, timeout=10)
            data = resp.json()
            titles = [r['title'] for r in data.get('query', {}).get('search', [])]
            for title in titles:
                if len(images) >= count:
                    break
                info_url = (
                    f"https://commons.wikimedia.org/w/api.php"
                    f"?action=query&titles={requests.utils.quote(title)}"
                    f"&prop=imageinfo&iiprop=url&format=json"
                )
                info = requests.get(info_url, timeout=10).json()
                pages = info.get('query', {}).get('pages', {})
                for page in pages.values():
                    img_url = page.get('imageinfo', [{}])[0].get('url', '')
                    if img_url and img_url.lower().endswith(('.jpg', '.jpeg', '.png')):
                        r2 = requests.get(img_url, timeout=10)
                        if r2.status_code == 200:
                            ext = '.png' if img_url.endswith('.png') else '.jpg'
                            tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
                            tmp.write(r2.content)
                            tmp.close()
                            images.append(tmp.name)
                            break
        except Exception as e:
            logging.warning(f"Wikimedia xatolik: {e}")

    return images


# ─────────────────────────────────────────────
# 1-sahifa: Muqova
# ─────────────────────────────────────────────

def create_cover_page(doc, university_info, subject_name, topic, name_surname, teacher_name):
    """
    Muqova:
      - Gerb rasmi (markazlashgan)
      - Ta'lim muassasasi nomi (agar kiritilsa, aks holda bo'sh)
      - Fan/yo'nalish nomi (agar kiritilsa, aks holda bo'sh)
      - LOYIHA ISHI (katta, qalin, markazlashgan)
      - Bajardi: Ism Familiya (chapga, qalin, bir qatorda)
      - Qabul qildi: O'qituvchi (chapga, qalin, bir qatorda)
      - Kitob rasmi (pastda, markazlashgan)
    """
    # ── Gerb rasmi ──
    if os.path.exists(GERB_PATH):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after  = Pt(6)
        p.add_run().add_picture(GERB_PATH, width=Inches(4.5))

    # ── Ta'lim muassasasi nomi ──
    univ_text = university_info.strip().upper() if university_info and university_info.strip() else ""
    add_paragraph(doc, univ_text,
                  alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  size=14, bold=True, space_before=4, space_after=2)

    # ── Fan / yo'nalish nomi ──
    subj_text = subject_name.strip().upper() if subject_name and subject_name.strip() else ""
    add_paragraph(doc, subj_text,
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

    # ── Bajardi: Ism Familiya (bir qatorda) ──
    p_b = doc.add_paragraph()
    p_b.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_b.paragraph_format.space_before = Pt(6)
    p_b.paragraph_format.space_after  = Pt(2)
    r1 = p_b.add_run("Bajardi: ")
    set_font(r1, size=14, bold=True)
    r2 = p_b.add_run(name_surname.strip() if name_surname else "")
    set_font(r2, size=14, bold=True)

    # ── Qabul qildi: O'qituvchi (bir qatorda) ──
    p_q = doc.add_paragraph()
    p_q.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p_q.paragraph_format.space_before = Pt(2)
    p_q.paragraph_format.space_after  = Pt(24)
    r3 = p_q.add_run("Qabul qildi: ")
    set_font(r3, size=14, bold=True)
    r4 = p_q.add_run(teacher_name.strip() if teacher_name and teacher_name.strip() else "")
    set_font(r4, size=14, bold=True)

    # ── Kitob rasmi ──
    if os.path.exists(KITOB_PATH):
        p_k = doc.add_paragraph()
        p_k.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_k.paragraph_format.space_before = Pt(0)
        p_k.paragraph_format.space_after  = Pt(0)
        p_k.add_run().add_picture(KITOB_PATH, width=Inches(1.8))

    doc.add_page_break()


# ─────────────────────────────────────────────
# 2-sahifa: Reja
# ─────────────────────────────────────────────

def create_plan_page(doc, topic, language):
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
        f"Boshqa hech narsa yozmang."
    )
    raw = gpt_generate(prompt)

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
# Kontent sahifalari (rasmlar bilan)
# ─────────────────────────────────────────────

def create_content_pages(doc, topic, language, plan_items, page_count, topic_images):
    lang_map = {
        "uz": "o'zbek", "en": "ingliz", "ru": "rus",
        "ko": "kores",  "zh": "xitoy",  "de": "nemis",
        "kaa": "qoraqalpoq", "tk": "turkman", "tg": "tojik",
    }
    lang_name = lang_map.get(language, "o'zbek")

    words_per_page   = 300
    main_sections    = len(plan_items) if plan_items else 4
    main_words_each  = max(
        words_per_page,
        int((page_count - 3) * words_per_page / max(main_sections, 1))
    )

    sys_msg = (
        f"Siz {lang_name} tilida akademik matn yozuvchi mutaxassississiz. "
        f"Faqat sof matn yozing, markdown belgilari ishlatmang."
    )

    # Rasmlarni bo'limlarga taqsimlash
    img_idx = 0

    def insert_image_if_available():
        nonlocal img_idx
        if img_idx < len(topic_images):
            try:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(6)
                p.paragraph_format.space_after  = Pt(6)
                p.add_run().add_picture(topic_images[img_idx], width=Inches(4.0))
                img_idx += 1
            except Exception as e:
                logging.warning(f"Rasm qo'shishda xatolik: {e}")

    # ── Kirish ──
    intro = gpt_generate(
        f"'{topic}' mavzusida loyiha ishi uchun kirish qismini yozing "
        f"({lang_name} tilida, taxminan {words_per_page} so'z). "
        f"Mavzuning dolzarbligi, maqsad va vazifalari haqida yozing.",
        system=sys_msg
    )
    add_paragraph(doc, "Kirish", alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  size=14, bold=True, space_before=12, space_after=6)
    for para in intro.split('\n'):
        para = para.strip()
        if para:
            add_paragraph(doc, para, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY,
                          size=14, space_before=0, space_after=6)
    insert_image_if_available()   # 1-rasm: kirishdan keyin
    doc.add_page_break()

    # ── Asosiy bo'limlar ──
    for i, section_title in enumerate(plan_items, 1):
        content = gpt_generate(
            f"'{topic}' mavzusida loyiha ishi uchun '{section_title}' bo'limini yozing "
            f"({lang_name} tilida, taxminan {main_words_each} so'z). "
            f"Ilmiy uslubda, batafsil yozing.",
            system=sys_msg
        )
        add_paragraph(doc, f"{i}. {section_title}",
                      alignment=WD_ALIGN_PARAGRAPH.CENTER,
                      size=14, bold=True, space_before=12, space_after=6)
        for para in content.split('\n'):
            para = para.strip()
            if para:
                add_paragraph(doc, para, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY,
                              size=14, space_before=0, space_after=6)
        insert_image_if_available()   # har bo'limdan keyin rasm
        doc.add_page_break()

    # ── Xulosa ──
    conclusion = gpt_generate(
        f"'{topic}' mavzusida loyiha ishi uchun xulosa qismini yozing "
        f"({lang_name} tilida, taxminan {words_per_page} so'z). "
        f"Asosiy natijalar va tavsiyalarni yozing.",
        system=sys_msg
    )
    add_paragraph(doc, "Xulosa", alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  size=14, bold=True, space_before=12, space_after=6)
    for para in conclusion.split('\n'):
        para = para.strip()
        if para:
            add_paragraph(doc, para, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY,
                          size=14, space_before=0, space_after=6)
    insert_image_if_available()   # xulosadan keyin rasm
    doc.add_page_break()

    # ── Foydalanilgan adabiyotlar ──
    refs = gpt_generate(
        f"'{topic}' mavzusida loyiha ishi uchun foydalanilgan adabiyotlar ro'yxatini tuzing "
        f"({lang_name} tilida, 8-10 ta manba). "
        f"Har bir manbani raqamlang: 1. Muallif. Kitob nomi. Nashriyot, yil.",
        system=sys_msg
    )
    add_paragraph(doc, "Foydalanilgan adabiyotlar",
                  alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  size=14, bold=True, space_before=12, space_after=6)
    for para in refs.split('\n'):
        para = para.strip()
        if para:
            add_paragraph(doc, para, alignment=WD_ALIGN_PARAGRAPH.LEFT,
                          size=14, space_before=0, space_after=6)


# ─────────────────────────────────────────────
# Asosiy funksiya
# ─────────────────────────────────────────────

def generate_loyiha_ishi(topic, page_count, language,
                         name_surname, university_info,
                         subject_name, teacher_name):
    """To'liq loyiha ishi hujjatini yaratadi va BytesIO qaytaradi."""

    # Rasmlarni oldindan yuklab olamiz
    # Sahifa soniga qarab rasm soni: min 3, max page_count//3
    img_count = max(3, min(page_count // 3, 8))
    logging.info(f"Mavzu uchun {img_count} ta rasm yuklanmoqda: {topic}")
    topic_images = fetch_topic_images(topic, count=img_count)
    logging.info(f"Yuklangan rasmlar soni: {len(topic_images)}")

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

    # 1. Muqova
    create_cover_page(doc, university_info, subject_name, topic, name_surname, teacher_name)

    # 2. Reja
    plan_items = create_plan_page(doc, topic, language)

    # 3. Kontent + rasmlar
    create_content_pages(doc, topic, language, plan_items, page_count, topic_images)

    # Vaqtinchalik rasm fayllarini tozalash
    for img_path in topic_images:
        try:
            os.unlink(img_path)
        except Exception:
            pass

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf
