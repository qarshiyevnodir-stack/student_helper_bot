import json
import logging
import os
import copy
import random
import requests
from io import BytesIO
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.text import MSO_AUTO_SIZE

from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

client = OpenAI()

UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")

# ─────────────────────────────────────────────
# Template slide structure (1.pptx):
#   Index 0  → Slide 1: TITLE            (sarlavha)
#   Index 1  → Slide 2: TITLE_AND_BODY   (reja)
#   Index 2  → Slide 3: BLANK_1_1_1_1_1_1  (kontent 1)
#   Index 3  → Slide 4: TITLE_AND_TWO_COLUMNS_1_1 (kontent 2)
#   Index 4  → Slide 5: ONE_COLUMN_TEXT  (kontent 3, rasm bilan)
#   Index 5  → Slide 6: BLANK_1_1        (kontent 4)
#   Index 6  → Slide 7: CUSTOM           (kontent 5, rasm bilan)
#   Index 7  → Slide 8: TITLE_AND_BODY_1 (xulosa)
#
# Takrorlash qoidasi:
#   5 ta slayd  → 1 marta  (3-7 slaydlar)
#   10 ta slayd → 2 marta
#   15 ta slayd → 3 marta
#   20 ta slayd → 4 marta
#   25 ta slayd → 5 marta
#   30 ta slayd → 6 marta
# ─────────────────────────────────────────────

CONTENT_SLIDE_TEMPLATE_INDICES = [2, 3, 4, 5, 6]  # Shablondagi 3-7 slaydlar indekslari


def duplicate_slide(prs, template_slide_index):
    """Shablondagi slaydni nusxalab, taqdimot oxiriga qo'shadi."""
    template_slide = prs.slides[template_slide_index]
    slide_layout = template_slide.slide_layout
    new_slide = prs.slides.add_slide(slide_layout)

    # Yangi slayddagi standart shakllarni o'chirish
    for shape in list(new_slide.shapes):
        shape._element.getparent().remove(shape._element)

    # Shablon slayddagi barcha shakllarni nusxalash
    for shape in template_slide.shapes:
        new_slide.shapes._spTree.append(copy.deepcopy(shape._element))

    return new_slide


def move_slide(prs, old_index, new_index):
    """Slaydni old_index dan new_index ga ko'chiradi."""
    xml_slides = prs.slides._sldIdLst
    slides = list(xml_slides)
    slide_elem = slides[old_index]
    xml_slides.remove(slide_elem)
    xml_slides.insert(new_index, slide_elem)


def build_slide_structure(prs, requested_content_count):
    """
    Taqdimot tuzilmasini quradi:
      - 1-2 slaydlar: har doim boshida (shablon)
      - 3-7 slaydlar: requested_content_count / 5 marta takrorlanadi
      - 8-slayd: har doim oxirida

    Qaytaradi: kontent slaydlari indekslari ro'yxati (final taqdimotda)
    """
    # Necha marta to'liq takrorlash kerak
    full_repeats = max(1, round(requested_content_count / 5))
    total_content_slides = full_repeats * 5

    logging.info(f"Kontent slaydlari: {requested_content_count} so'raldi, "
                 f"{full_repeats} marta takrorlanadi ({total_content_slides} ta kontent slayd)")

    # Shablon allaqachon 1 to'plam (slaydlar 3-7) va xulosa (slayd 8) ni o'z ichiga oladi.
    # Agar ko'proq takrorlash kerak bo'lsa, qo'shimcha nusxalar qo'shamiz.
    # Xulosa slayd hozircha index 7 da turibdi.

    extra_sets_needed = full_repeats - 1  # Birinchi to'plam allaqachon bor

    for set_num in range(extra_sets_needed):
        for slide_template_idx in CONTENT_SLIDE_TEMPLATE_INDICES:
            duplicate_slide(prs, slide_template_idx)
        logging.info(f"  {set_num + 2}-to'plam qo'shildi. Jami slaydlar: {len(prs.slides)}")

    # Xulosa slaydini (index 7) oxiriga ko'chirish
    conclusion_current_index = 7
    last_index = len(prs.slides) - 1
    move_slide(prs, conclusion_current_index, last_index)

    logging.info(f"Yakuniy tuzilma: {len(prs.slides)} ta slayd")
    for i, s in enumerate(prs.slides):
        logging.info(f"  [{i}] {s.slide_layout.name}")

    return total_content_slides


def find_placeholder_by_idx(slide, idx):
    """Placeholder ni indeks bo'yicha topadi."""
    for ph in slide.placeholders:
        if ph.placeholder_format.idx == idx:
            return ph
    return None


def set_text(shape, text, font_size_pt=None, bold=None):
    """Shape yoki placeholder matnini o'rnatadi."""
    if shape is None:
        return
    tf = shape.text_frame
    tf.clear()
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    run = p.runs[0] if p.runs else p.add_run()
    run.text = text
    if font_size_pt:
        run.font.size = Pt(font_size_pt)
    if bold is not None:
        run.font.bold = bold


def set_text_list(shape, items, font_size_pt=18):
    """Shape ga ro'yxat (bullet points) yozadi."""
    if shape is None or not items:
        return
    tf = shape.text_frame
    tf.clear()
    tf.word_wrap = True
    for i, item in enumerate(items):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = str(item)
        if p.runs:
            p.runs[0].font.size = Pt(font_size_pt)


def add_image_to_placeholder(slide, ph_idx, image_query):
    """Rasm placeholder ga rasm qo'shadi."""
    if not UNSPLASH_ACCESS_KEY:
        logging.warning("UNSPLASH_ACCESS_KEY yo'q. Rasm o'tkazib yuborildi.")
        return
    try:
        url = (f"https://api.unsplash.com/search/photos"
               f"?query={image_query}&per_page=1&client_id={UNSPLASH_ACCESS_KEY}")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            logging.warning(f"Rasm topilmadi: {image_query}")
            return
        img_url = results[0]["urls"]["regular"]
        img_data = requests.get(img_url, timeout=15).content
        img_path = f"/tmp/slide_img_{random.randint(0, 99999)}.jpg"
        with open(img_path, "wb") as f:
            f.write(img_data)

        ph = find_placeholder_by_idx(slide, ph_idx)
        if ph:
            slide.shapes.add_picture(img_path, ph.left, ph.top, ph.width, ph.height)
        else:
            slide.shapes.add_picture(img_path, Inches(6.5), Inches(1.5), Inches(3), Inches(3))

        os.remove(img_path)
        logging.info(f"Rasm qo'shildi: {image_query}")
    except Exception as e:
        logging.error(f"Rasm qo'shishda xatolik ({image_query}): {e}")


def generate_slide_content(topic, slide_number, total_slides, language, is_plan=False, is_conclusion=False):
    """GPT orqali slayd uchun kontent yaratadi."""
    if is_plan:
        prompt = (
            f"Mavzu: '{topic}'. Taqdimot rejasini (plan) yarat. "
            f"Faqat 3-4 ta asosiy nuqta. Til: {language}. "
            f"JSON formatida: {{\"title\": \"Reja\", \"content\": [\"...\", \"...\", \"...\"]}}"
        )
    elif is_conclusion:
        prompt = (
            f"Mavzu: '{topic}'. Xulosa slayd uchun matn yarat. "
            f"Asosiy xulosalar. Til: {language}. "
            f"JSON formatida: {{\"title\": \"Xulosa\", \"content\": [\"...\", \"...\"]}}"
        )
    else:
        prompt = (
            f"Mavzu: '{topic}'. Bu {total_slides} ta slaydli taqdimotning {slide_number}-slaydiga kontent yarat. "
            f"Til: {language}. "
            f"JSON formatida: {{\"title\": \"...\", \"content\": [\"...\", \"...\", \"...\"], \"image_query\": \"...\"}}"
        )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Siz taqdimot slaydlari uchun kontent yaratuvchi yordamchisiz. "
                        "Faqat JSON formatida javob bering. Matnlar berilgan tilda bo'lsin."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        logging.error(f"GPT xatolik (slayd {slide_number}): {e}")
        return None


def fill_slide_1_title(slide, topic, name_surname):
    """Slayd 1: Sarlavha slaydini to'ldiradi."""
    title_ph = find_placeholder_by_idx(slide, 0)  # CENTER_TITLE
    subtitle_ph = find_placeholder_by_idx(slide, 1)  # SUBTITLE
    if title_ph:
        set_text(title_ph, topic.upper(), font_size_pt=40, bold=True)
    if subtitle_ph and name_surname and name_surname.strip():
        set_text(subtitle_ph, name_surname, font_size_pt=24)


def fill_slide_2_plan(slide, plan_data):
    """Slayd 2: Reja slaydini to'ldiradi."""
    title_ph = find_placeholder_by_idx(slide, 0)  # TITLE
    body_ph = find_placeholder_by_idx(slide, 1)   # BODY
    if title_ph:
        set_text(title_ph, plan_data.get("title", "Reja"), font_size_pt=32, bold=True)
    if body_ph:
        set_text_list(body_ph, plan_data.get("content", []), font_size_pt=20)


def fill_slide_3_blank(slide, content_data):
    """Slayd 3 (BLANK_1_1_1_1_1_1): Sarlavha + matn."""
    title_ph = find_placeholder_by_idx(slide, 0)  # TITLE
    body_ph = find_placeholder_by_idx(slide, 1)   # SUBTITLE
    if title_ph:
        set_text(title_ph, content_data.get("title", ""), font_size_pt=28, bold=True)
    if body_ph:
        set_text_list(body_ph, content_data.get("content", []), font_size_pt=18)


def fill_slide_4_two_columns(slide, content_data):
    """Slayd 4 (TITLE_AND_TWO_COLUMNS_1_1): Sarlavha + 2 ustun."""
    title_ph = find_placeholder_by_idx(slide, 0)  # TITLE
    col1_ph = find_placeholder_by_idx(slide, 1)   # SUBTITLE (1-ustun)
    col2_ph = find_placeholder_by_idx(slide, 2)   # SUBTITLE (2-ustun)

    if title_ph:
        set_text(title_ph, content_data.get("title", ""), font_size_pt=28, bold=True)

    content = content_data.get("content", [])
    half = max(1, len(content) // 2)
    if col1_ph:
        set_text_list(col1_ph, content[:half], font_size_pt=18)
    if col2_ph:
        set_text_list(col2_ph, content[half:], font_size_pt=18)


def fill_slide_5_one_column_image(slide, content_data, image_query):
    """Slayd 5 (ONE_COLUMN_TEXT): Sarlavha + matn + rasm."""
    title_ph = find_placeholder_by_idx(slide, 0)  # TITLE
    body_ph = find_placeholder_by_idx(slide, 1)   # SUBTITLE
    if title_ph:
        set_text(title_ph, content_data.get("title", ""), font_size_pt=28, bold=True)
    if body_ph:
        set_text_list(body_ph, content_data.get("content", []), font_size_pt=18)
    if image_query:
        add_image_to_placeholder(slide, 2, image_query)


def fill_slide_6_blank(slide, content_data):
    """Slayd 6 (BLANK_1_1): Sarlavha + matn."""
    title_ph = find_placeholder_by_idx(slide, 0)  # TITLE
    body_ph = find_placeholder_by_idx(slide, 1)   # SUBTITLE
    if title_ph:
        set_text(title_ph, content_data.get("title", ""), font_size_pt=28, bold=True)
    if body_ph:
        set_text_list(body_ph, content_data.get("content", []), font_size_pt=18)


def fill_slide_7_custom_image(slide, content_data, image_query):
    """Slayd 7 (CUSTOM): Sarlavha + matn + rasm."""
    title_ph = find_placeholder_by_idx(slide, 0)  # TITLE
    body_ph = find_placeholder_by_idx(slide, 1)   # SUBTITLE
    if title_ph:
        set_text(title_ph, content_data.get("title", ""), font_size_pt=28, bold=True)
    if body_ph:
        set_text_list(body_ph, content_data.get("content", []), font_size_pt=18)
    if image_query:
        add_image_to_placeholder(slide, 2, image_query)


def fill_slide_8_conclusion(slide, conclusion_data):
    """Slayd 8 (TITLE_AND_BODY_1): Xulosa slaydini to'ldiradi."""
    title_ph = find_placeholder_by_idx(slide, 0)  # TITLE
    body_ph = find_placeholder_by_idx(slide, 1)   # BODY
    if title_ph:
        set_text(title_ph, conclusion_data.get("title", "Xulosa"), font_size_pt=32, bold=True)
    if body_ph:
        set_text_list(body_ph, conclusion_data.get("content", []), font_size_pt=20)


# Kontent slaydlari uchun to'ldirish funksiyalari ro'yxati (tartib bo'yicha)
CONTENT_FILL_FUNCTIONS = [
    fill_slide_3_blank,
    fill_slide_4_two_columns,
    fill_slide_5_one_column_image,
    fill_slide_6_blank,
    fill_slide_7_custom_image,
]


def generate_template_1_presentation(prs, topic, requested_slide_count, language, name_surname="", plan=None):
    """
    8 slaydli shablon asosida taqdimot yaratadi.

    Tuzilma:
      - Slayd 1: Sarlavha (har doim birinchi)
      - Slayd 2: Reja     (har doim ikkinchi)
      - Slaydlar 3-7: Kontent (requested_slide_count / 5 marta takrorlanadi)
      - Slayd 8: Xulosa   (har doim oxirgi)

    Takrorlash qoidasi:
      5  → 1 marta, 10 → 2 marta, 15 → 3 marta,
      20 → 4 marta, 25 → 5 marta, 30 → 6 marta
    """
    logging.info(f"Taqdimot yaratilmoqda: mavzu='{topic}', slaydlar={requested_slide_count}, til={language}")

    # ── 1. Shablon tuzilmasini qurish (slaydlarni takrorlash va tartibga solish) ──
    total_content_slides = build_slide_structure(prs, requested_slide_count)
    total_slides = len(prs.slides)  # 2 + total_content_slides + 1

    # ── 2. GPT orqali barcha kontent yaratish ──

    # Reja (plan)
    if plan is None or not isinstance(plan, dict) or not plan.get("content"):
        plan = generate_slide_content(topic, 2, total_slides, language, is_plan=True)
    if not plan:
        plan = {"title": "Reja", "content": ["Kirish", "Asosiy qism", "Xulosa"]}

    # Kontent slaydlari uchun matn
    content_data_list = []
    for i in range(total_content_slides):
        data = generate_slide_content(topic, i + 3, total_slides, language)
        if not data:
            data = {
                "title": f"{topic} — {i + 1}",
                "content": ["Asosiy ma'lumot", "Qo'shimcha tafsilotlar"],
                "image_query": topic
            }
        content_data_list.append(data)

    # Xulosa
    conclusion = generate_slide_content(topic, total_slides, total_slides, language, is_conclusion=True)
    if not conclusion:
        conclusion = {"title": "Xulosa", "content": ["Asosiy xulosalar", "Tavsiyalar"]}

    # ── 3. Slaydlarni to'ldirish ──

    # Slayd 1: Sarlavha
    fill_slide_1_title(prs.slides[0], topic, name_surname)

    # Slayd 2: Reja
    fill_slide_2_plan(prs.slides[1], plan)

    # Slaydlar 3 dan (total_slides - 2) gacha: Kontent
    for i in range(total_content_slides):
        slide_index = i + 2  # 0-indexed: 2, 3, 4, ...
        slide = prs.slides[slide_index]
        data = content_data_list[i]
        image_query = data.get("image_query", topic)

        # Slayd turini aniqlash (0-4 oralig'ida sikl)
        slide_type = i % 5  # 0=3-slayd, 1=4-slayd, 2=5-slayd, 3=6-slayd, 4=7-slayd

        if slide_type == 0:
            fill_slide_3_blank(slide, data)
        elif slide_type == 1:
            fill_slide_4_two_columns(slide, data)
        elif slide_type == 2:
            fill_slide_5_one_column_image(slide, data, image_query)
        elif slide_type == 3:
            fill_slide_6_blank(slide, data)
        elif slide_type == 4:
            fill_slide_7_custom_image(slide, data, image_query)

        logging.info(f"  Slayd {slide_index + 1} to'ldirildi (tur {slide_type + 3}): {data.get('title', '')}")

    # Oxirgi slayd: Xulosa
    fill_slide_8_conclusion(prs.slides[-1], conclusion)

    # ── 4. Faylni xotiraga saqlash ──
    prs_bytes = BytesIO()
    prs.save(prs_bytes)
    prs_bytes.seek(0)

    logging.info(f"Taqdimot tayyor: {total_slides} ta slayd")
    return prs_bytes


# Eski funksiya (zaxira sifatida saqlanadi)
def generate_presentation(prs, topic, slide_count, language, name_surname=""):
    return generate_template_1_presentation(prs, topic, slide_count, language, name_surname)
