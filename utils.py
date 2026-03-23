import json
import logging
import os
import copy
import random
import requests
from io import BytesIO
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.text import MSO_AUTO_SIZE

from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

client = OpenAI()

PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")

# ─────────────────────────────────────────────
# Template slide structure (1.pptx):
#   Index 0  → Slide 1: TITLE            (sarlavha)
#   Index 1  → Slide 2: TITLE_AND_BODY   (reja)
#   Index 2  → Slide 3: BLANK_1_1_1_1_1_1  (kontent 1 — 3 ustun)
#   Index 3  → Slide 4: TITLE_AND_TWO_COLUMNS_1_1 (kontent 2 — 2 ustun)
#   Index 4  → Slide 5: ONE_COLUMN_TEXT  (kontent 3 — chapda rasm, o'ngda matn)
#   Index 5  → Slide 6: BLANK_1_1        (kontent 4 — katta iqtibos)
#   Index 6  → Slide 7: CUSTOM           (kontent 5 — o'ngda rasm, chapda matn)
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


# ═══════════════════════════════════════════════════════════════
# YORDAMCHI FUNKSIYALAR
# ═══════════════════════════════════════════════════════════════

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
    full_repeats = max(1, round(requested_content_count / 5))
    total_content_slides = full_repeats * 5

    logging.info(f"Kontent slaydlari: {requested_content_count} so'raldi, "
                 f"{full_repeats} marta takrorlanadi ({total_content_slides} ta kontent slayd)")

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
    return total_content_slides


def find_placeholder_by_idx(slide, idx):
    """Placeholder ni indeks bo'yicha topadi."""
    for ph in slide.placeholders:
        if ph.placeholder_format.idx == idx:
            return ph
    return None


def find_textbox_by_position(slide, min_left_cm, max_left_cm):
    """
    Berilgan chapdan oraliq koordinatada joylashgan TEXT_BOX ni topadi.
    3-slayddagi o'rta va o'ng ustunlar uchun ishlatiladi.
    """
    for shape in slide.shapes:
        left_cm = shape.left / 914400 * 2.54
        if min_left_cm <= left_cm <= max_left_cm:
            if hasattr(shape, "text_frame"):
                return shape
    return None


def auto_shrink_text(shape, text, base_font_pt, min_font_pt=10, bold=False):
    """
    Matnni shape ga yozadi. Agar matn uzun bo'lsa, shriftni kichraytiradi.
    base_font_pt dan boshlaydi, min_font_pt gacha kamaytiradi.
    """
    if shape is None:
        return
    tf = shape.text_frame
    tf.clear()
    tf.word_wrap = True

    # Matn uzunligiga qarab shrift o'lchamini hisoblash
    char_count = len(text)
    if char_count <= 60:
        font_pt = base_font_pt
    elif char_count <= 100:
        font_pt = max(min_font_pt, base_font_pt - 4)
    elif char_count <= 150:
        font_pt = max(min_font_pt, base_font_pt - 8)
    elif char_count <= 200:
        font_pt = max(min_font_pt, base_font_pt - 12)
    else:
        font_pt = max(min_font_pt, base_font_pt - 16)

    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = text
    run.font.size = Pt(font_pt)
    if bold:
        run.font.bold = True


def set_text_list_auto(shape, items, base_font_pt=18, min_font_pt=10):
    """
    Ro'yxat matnini yozadi. Elementlar ko'p yoki uzun bo'lsa shriftni kichraytiradi.
    """
    if shape is None or not items:
        return
    tf = shape.text_frame
    tf.clear()
    tf.word_wrap = True

    # Umumiy belgilar soniga qarab shrift o'lchamini hisoblash
    total_chars = sum(len(str(item)) for item in items)
    item_count = len(items)

    if total_chars <= 100 and item_count <= 3:
        font_pt = base_font_pt
    elif total_chars <= 200 and item_count <= 5:
        font_pt = max(min_font_pt, base_font_pt - 2)
    elif total_chars <= 350:
        font_pt = max(min_font_pt, base_font_pt - 4)
    elif total_chars <= 500:
        font_pt = max(min_font_pt, base_font_pt - 6)
    else:
        font_pt = max(min_font_pt, base_font_pt - 8)

    from pptx.enum.text import PP_ALIGN
    for i, item in enumerate(items):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = str(item)
        run.font.size = Pt(font_pt)


def fetch_image(image_query):
    """
    Pixabay orqali rasm yuklab oladi.
    CDN previewURL dan _640.jpg o'lchamli rasm oladi (rate limit yo'q).
    Qaytaradi: lokal fayl yo'li yoki None.
    """
    import re
    if not PIXABAY_API_KEY:
        logging.warning("PIXABAY_API_KEY yo'q. Rasm o'tkazib yuborildi.")
        return None
    try:
        url = (f"https://pixabay.com/api/"
               f"?key={PIXABAY_API_KEY}"
               f"&q={requests.utils.quote(image_query)}"
               f"&image_type=photo&orientation=horizontal"
               f"&per_page=5&safesearch=true")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
        if not hits:
            logging.warning(f"Rasm topilmadi: {image_query}")
            return None

        img_data = None
        img_ext = "jpg"

        for hit in hits:
            preview_url = hit.get("previewURL", "")
            if not preview_url:
                continue

            # Faqat .jpg previewURL larni ishlatamiz (PNG uchun 640px ishlamaydi)
            if not preview_url.lower().endswith(".jpg"):
                continue

            # _150.jpg -> _640.jpg (CDN URL, rate limit yo'q)
            cdn_url = re.sub(r'_\d+\.jpg$', '_640.jpg', preview_url)
            img_resp = requests.get(cdn_url, timeout=15)
            if img_resp.status_code == 200 and "image" in img_resp.headers.get("Content-Type", ""):
                img_data = img_resp.content
                logging.info(f"Rasm yuklandi (640px): {image_query}")
                break

            # Fallback: previewURL (150px)
            img_resp2 = requests.get(preview_url, timeout=15)
            if img_resp2.status_code == 200 and "image" in img_resp2.headers.get("Content-Type", ""):
                img_data = img_resp2.content
                logging.info(f"Rasm yuklandi (150px fallback): {image_query}")
                break

        # Agar .jpg topilmasa, istalgan previewURL dan yuklab olish
        if not img_data:
            for hit in hits:
                preview_url = hit.get("previewURL", "")
                if not preview_url:
                    continue
                img_resp = requests.get(preview_url, timeout=15)
                if img_resp.status_code == 200 and "image" in img_resp.headers.get("Content-Type", ""):
                    img_data = img_resp.content
                    ct = img_resp.headers.get("Content-Type", "")
                    img_ext = "png" if "png" in ct else "jpg"
                    logging.info(f"Rasm yuklandi (preview fallback): {image_query}")
                    break

        if not img_data:
            logging.warning(f"Rasm yuklab bo'lmadi: {image_query}")
            return None

        img_path = f"/tmp/slide_img_{random.randint(0, 99999)}.{img_ext}"
        with open(img_path, "wb") as f:
            f.write(img_data)
        logging.info(f"Rasm saqlandi: {img_path}")
        return img_path
    except Exception as e:
        logging.error(f"Rasm yuklashda xatolik ({image_query}): {e}")
        return None


def place_image_in_placeholder(slide, ph_idx, img_path):
    """
    Rasmni placeholder o'lchamida va koordinatasida joylashtiradi.
    Placeholder ni o'zi esa ko'rinmas qilinadi (rasm ustiga qo'yiladi).
    """
    if not img_path:
        return
    ph = find_placeholder_by_idx(slide, ph_idx)
    if ph is None:
        logging.warning(f"Placeholder idx={ph_idx} topilmadi.")
        return
    try:
        slide.shapes.add_picture(img_path, ph.left, ph.top, ph.width, ph.height)
        os.remove(img_path)
        logging.info(f"Rasm placeholder idx={ph_idx} ga joylashtirildi.")
    except Exception as e:
        logging.error(f"Rasm joylashtirish xatolik: {e}")


# ═══════════════════════════════════════════════════════════════
# GPT KONTENT YARATISH
# ═══════════════════════════════════════════════════════════════

def generate_slide_content(topic, slide_number, total_slides, language,
                           is_plan=False, is_conclusion=False,
                           slide_type=None):
    """GPT orqali slayd uchun kontent yaratadi."""

    if is_plan:
        prompt = (
            f"Mavzu: '{topic}'. Taqdimot rejasini (plan) yarat. "
            f"Faqat 3 yoki 4 ta asosiy nuqta yoz (na ko'proq, na kamroq). Til: {language}. "
            f"JSON formatida qaytarish shart: {{\"title\": \"Reja\", \"content\": [\"1-nuqta\", \"2-nuqta\", \"3-nuqta\"]}}. "
            f"content massivida faqat 3 yoki 4 ta element bo'lsin."
        )
    elif is_conclusion:
        prompt = (
            f"Mavzu: '{topic}'. Xulosa slayd uchun matn yarat. "
            f"Asosiy xulosalar. Til: {language}. "
            f"JSON formatida: {{\"title\": \"Xulosa\", \"content\": [\"...\", \"...\"]}}"
        )
    elif slide_type == "three_columns":
        # 3-slayd: sarlavha + 3 ta alohida ustun matni
        prompt = (
            f"Mavzu: '{topic}'. Bu {total_slides} ta slaydli taqdimotning {slide_number}-slaydiga kontent yarat. "
            f"Til: {language}. "
            f"Slaydda 3 ta alohida ustun bor. Har bir ustun uchun 3-5 jumlali batafsil matn yoz. "
            f"JSON formatida: {{\"title\": \"...\", \"col1\": \"...\", \"col2\": \"...\", \"col3\": \"...\", \"image_query\": \"...\"}}"
        )
    elif slide_type == "two_columns":
        # 4-slayd: sarlavha + 2 ta ustun matni (faqat 2 punkt)
        prompt = (
            f"Mavzu: '{topic}'. Bu {total_slides} ta slaydli taqdimotning {slide_number}-slaydiga kontent yarat. "
            f"Til: {language}. "
            f"Slaydda 2 ta ustun bor, har biriga 4-6 jumlali batafsil paragraf yoz. "
            f"Faqat 2 ta ustun matni kerak, ko'proq emas. "
            f"JSON formatida: {{\"title\": \"...\", \"col1\": \"...\", \"col2\": \"...\", \"image_query\": \"...\"}}"
        )
    else:
        # Oddiy slayd: sarlavha + 2 punkt matn + rasm so'rovi
        prompt = (
            f"Mavzu: '{topic}'. Bu {total_slides} ta slaydli taqdimotning {slide_number}-slaydiga kontent yarat. "
            f"Til: {language}. "
            f"2 ta punkt matn yoz, har biri 3-5 jumlali batafsil bo'lsin. "
            f"JSON formatida: {{\"title\": \"...\", \"content\": [\"...\", \"...\"], \"image_query\": \"...\"}}"
        )

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Siz taqdimot slaydlari uchun kontent yaratuvchi yordamchisiz. "
                        "Faqat JSON formatida javob bering. Matnlar berilgan tilda bo'lsin. "
                        "Matnlar qisqa va aniq bo'lsin."
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


# ═══════════════════════════════════════════════════════════════
# SLAYD TO'LDIRISH FUNKSIYALARI
# ═══════════════════════════════════════════════════════════════

def fill_slide_1_title(slide, topic, name_surname):
    """
    Slayd 1 — Muqova (TITLE).
    Sarlavha: katta shrift, matn uzun bo'lsa kichrayadi.
    Subtitle: ism-familiya yoki taqdimotchi nomi.
    """
    title_ph = find_placeholder_by_idx(slide, 0)   # CENTER_TITLE
    subtitle_ph = find_placeholder_by_idx(slide, 1) # SUBTITLE

    if title_ph:
        auto_shrink_text(title_ph, topic.upper(), base_font_pt=40, min_font_pt=20, bold=True)

    if subtitle_ph:
        if name_surname and name_surname.strip():
            auto_shrink_text(subtitle_ph, name_surname, base_font_pt=24, min_font_pt=14)
        else:
            # Ism kiritilmasa, placeholder ni bo'sh qilish (shablon matni ko'rinmasin)
            subtitle_ph.text_frame.clear()
            subtitle_ph.text_frame.paragraphs[0].text = ""


def fill_slide_2_plan(slide, plan_data):
    """
    Slayd 2 — Reja (TITLE_AND_BODY).
    Sarlavha har doim 'Reja', asosiy matn raqamli ro'yxat (1. 2. 3. 4.).
    """
    title_ph = find_placeholder_by_idx(slide, 0)  # TITLE
    body_ph  = find_placeholder_by_idx(slide, 1)  # BODY

    # Sarlavha har doim "Reja"
    if title_ph:
        auto_shrink_text(title_ph, "Reja", base_font_pt=32, bold=True)

    if body_ph:
        import re
        from pptx.oxml.ns import qn
        from lxml import etree
        from pptx.enum.text import PP_ALIGN
        # Maksimal 4 ta nuqta
        content = plan_data.get("content", [])[:4]
        tf = body_ph.text_frame
        tf.clear()
        tf.word_wrap = True
        for i, item in enumerate(content):
            # Mavjud N. yoki N.M. prefiksini olib tashlash
            text = re.sub(r'^[\d]+[\d\.]*\.?\s*', '', str(item)).strip()
            label = f"{i+1}. {text}"
            if i == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            p.alignment = PP_ALIGN.LEFT
            # Shablon bullet va tartib raqamini o'chirish
            pPr = p._p.get_or_add_pPr()
            # Mavjud buChar, buAutoNum, buNone larni olib tashlash
            for child in list(pPr):
                tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if tag in ('buChar', 'buAutoNum', 'buNone', 'buClr', 'buFont', 'buSzPct'):
                    pPr.remove(child)
            # buNone qo'shish — hech qanday belgi yo'q
            etree.SubElement(pPr, qn('a:buNone'))
            run = p.add_run()
            run.text = label
            run.font.size = Pt(20)


def fill_slide_3_three_columns(slide, content_data):
    """
    Slayd 3 — Uch ustunli kontent (BLANK_1_1_1_1_1_1).
    Sarlavha (idx=0) + 3 ta ustun (idx=1, idx=10, idx=11).
    Har bir ustun uchun alohida matn.
    """
    title_ph = find_placeholder_by_idx(slide, 0)   # TITLE
    col1_ph  = find_placeholder_by_idx(slide, 1)   # Chap ustun
    col2_ph  = find_placeholder_by_idx(slide, 10)  # O'rta ustun
    col3_ph  = find_placeholder_by_idx(slide, 11)  # O'ng ustun

    # Agar yangi placeholder topilmasa, koordinata bo'yicha topishga urinish
    if col2_ph is None:
        col2_ph = find_textbox_by_position(slide, 8.5, 11.5)
    if col3_ph is None:
        col3_ph = find_textbox_by_position(slide, 16.0, 20.0)

    if title_ph:
        auto_shrink_text(title_ph, content_data.get("title", ""), base_font_pt=28, bold=True)

    col1_text = content_data.get("col1", "")
    col2_text = content_data.get("col2", "")
    col3_text = content_data.get("col3", "")

    # Agar col1/col2/col3 yo'q bo'lsa, content ro'yxatidan foydalanish
    if not col1_text:
        items = content_data.get("content", ["", "", ""])
        col1_text = items[0] if len(items) > 0 else ""
        col2_text = items[1] if len(items) > 1 else ""
        col3_text = items[2] if len(items) > 2 else ""

    if col1_ph:
        auto_shrink_text(col1_ph, col1_text, base_font_pt=20, min_font_pt=12)
    if col2_ph:
        auto_shrink_text(col2_ph, col2_text, base_font_pt=20, min_font_pt=12)
    if col3_ph:
        auto_shrink_text(col3_ph, col3_text, base_font_pt=20, min_font_pt=12)


def fill_slide_4_two_columns(slide, content_data):
    """
    Slayd 4 — Ikki ustunli kontent (TITLE_AND_TWO_COLUMNS_1_1).
    Sarlavha + 2 ta ustun (faqat 2 ta paragraf, ko'proq bo'lsa qolganini o'tkazib yuboradi).
    """
    title_ph = find_placeholder_by_idx(slide, 0)  # TITLE
    col1_ph  = find_placeholder_by_idx(slide, 2)  # Chap ustun
    col2_ph  = find_placeholder_by_idx(slide, 1)  # O'ng ustun

    if title_ph:
        auto_shrink_text(title_ph, content_data.get("title", ""), base_font_pt=28, bold=True)

    col1_text = content_data.get("col1", "")
    col2_text = content_data.get("col2", "")

    # Agar col1/col2 yo'q bo'lsa, content ro'yxatidan foydalanish (faqat 2 ta)
    if not col1_text:
        items = content_data.get("content", ["", ""])
        col1_text = items[0] if len(items) > 0 else ""
        col2_text = items[1] if len(items) > 1 else ""

    if col1_ph:
        auto_shrink_text(col1_ph, col1_text, base_font_pt=16, min_font_pt=10)
    if col2_ph:
        auto_shrink_text(col2_ph, col2_text, base_font_pt=16, min_font_pt=10)


def fill_slide_5_image_left(slide, content_data, image_query):
    """
    Slayd 5 — Chapda rasm, o'ngda matn (ONE_COLUMN_TEXT).
    Sarlavha (idx=0) + Asosiy matn (idx=1) + Rasm (idx=2).
    Shrift: sarlavha kichrayadi, asosiy matn 13pt.
    """
    title_ph = find_placeholder_by_idx(slide, 0)  # TITLE (o'ngda)
    body_ph  = find_placeholder_by_idx(slide, 1)  # SUBTITLE (o'ngda)

    if title_ph:
        auto_shrink_text(title_ph, content_data.get("title", ""), base_font_pt=26, min_font_pt=14, bold=True)

    if body_ph:
        items = content_data.get("content", [])
        # Faqat 2 ta paragraf, tartiblanmagan avzasiz, uzunroq matn
        tf = body_ph.text_frame
        tf.clear()
        tf.word_wrap = True
        total_chars = sum(len(str(i)) for i in items[:2])
        if total_chars <= 150:
            font_pt = 18
        elif total_chars <= 300:
            font_pt = 16
        elif total_chars <= 500:
            font_pt = 14
        elif total_chars <= 700:
            font_pt = 12
        else:
            font_pt = 10
        from pptx.enum.text import PP_ALIGN
        from pptx.oxml.ns import qn
        from lxml import etree
        from pptx.util import Emu
        for idx_p, item in enumerate(items[:2]):
            if idx_p == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            p.alignment = PP_ALIGN.LEFT
            pPr = p._p.get_or_add_pPr()
            # Barcha bullet/indent elementlarini o'chirish
            for child in list(pPr):
                tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if tag in ('buChar', 'buAutoNum', 'buNone', 'buClr', 'buFont', 'buSzPct', 'indent', 'marL'):
                    pPr.remove(child)
            etree.SubElement(pPr, qn('a:buNone'))
            # Indent va margin ni nolga tushirish
            pPr.set('indent', '0')
            pPr.set('marL', '0')
            run = p.add_run()
            run.text = str(item)
            run.font.size = Pt(font_pt)

    # Rasm yuklab olish va joylashtirish
    query = image_query or content_data.get("image_query", content_data.get("title", "nature"))
    img_path = fetch_image(query)
    place_image_in_placeholder(slide, 2, img_path)


def fill_slide_6_quote(slide, content_data):
    """
    Slayd 6 — Katta iqtibos / diqqat slayd (BLANK_1_1).
    Sarlavha (idx=0) tepada, Asosiy matn (idx=1) pastda.
    Matn ko'p bo'lsa shrift kichrayadi. Tekislanish tepadan.
    """
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Pt
    from lxml import etree
    from pptx.oxml.ns import qn
    title_ph = find_placeholder_by_idx(slide, 0)  # TITLE (tepada)
    body_ph  = find_placeholder_by_idx(slide, 1)  # SUBTITLE (pastda, katta)

    # idx=6 bo'sh qo'shimcha placeholder ni o'chirish
    extra_ph = find_placeholder_by_idx(slide, 6)
    if extra_ph is not None:
        sp = extra_ph._element
        sp.getparent().remove(sp)

    if title_ph:
        auto_shrink_text(title_ph, content_data.get("title", ""), base_font_pt=26, min_font_pt=14, bold=True)

    if body_ph:
        items = content_data.get("content", [])
        if items:
            # 4 paragraf (2 ta asosiy + har birini 2 ga bo'lish), 16pt, tepadan tekislash
            expanded = []
            for item in items[:2]:
                text = str(item)
                # Matnni taxminan 2 ga bo'lish (birinchi gap va qolgan qism)
                sentences = text.replace('! ', '!|').replace('. ', '.|').replace('? ', '?|').split('|')
                mid = max(1, len(sentences) // 2)
                part1 = ' '.join(sentences[:mid]).strip()
                part2 = ' '.join(sentences[mid:]).strip()
                if part1:
                    expanded.append(part1)
                if part2:
                    expanded.append(part2)
            full_text = "\n\n".join(expanded) if expanded else "\n\n".join(str(i) for i in items)
            auto_shrink_text(body_ph, full_text, base_font_pt=16, min_font_pt=11)
            from pptx.enum.text import MSO_ANCHOR
            body_ph.text_frame.vertical_anchor = MSO_ANCHOR.TOP


def fill_slide_7_image_right(slide, content_data, image_query):
    """
    Slayd 7 — O'ngda rasm, chapda matn (CUSTOM).
    Sarlavha (idx=0) + Asosiy matn (idx=1) + Rasm (idx=2).
    Sarlavha tepadan 3sm, matn uzunroq, 13pt.
    """
    from pptx.util import Cm
    title_ph = find_placeholder_by_idx(slide, 0)  # TITLE (chapda)
    body_ph  = find_placeholder_by_idx(slide, 1)  # SUBTITLE (chapda)

    if title_ph:
        # Sarlavha tepadan 1.5sm, so'zlar ko'p bo'lsa shrift kichrayadi
        title_ph.top = Cm(1.5)
        auto_shrink_text(title_ph, content_data.get("title", ""), base_font_pt=32, min_font_pt=14, bold=True)

    if body_ph:
        items = content_data.get("content", [])
        # Tartiblanmagan avzasiz, kattaroq shrift
        tf = body_ph.text_frame
        tf.clear()
        tf.word_wrap = True
        total_chars = sum(len(str(i)) for i in items[:2])
        if total_chars <= 200:
            font_pt = 18
        elif total_chars <= 350:
            font_pt = 16
        elif total_chars <= 500:
            font_pt = 14
        else:
            font_pt = 12
        from pptx.enum.text import PP_ALIGN
        from pptx.oxml.ns import qn
        from lxml import etree
        for idx_p, item in enumerate(items[:2]):
            if idx_p == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            p.alignment = PP_ALIGN.LEFT
            pPr = p._p.get_or_add_pPr()
            # Barcha bullet/indent elementlarini o'chirish
            for child in list(pPr):
                tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if tag in ('buChar', 'buAutoNum', 'buNone', 'buClr', 'buFont', 'buSzPct', 'indent', 'marL'):
                    pPr.remove(child)
            etree.SubElement(pPr, qn('a:buNone'))
            # Indent va margin ni nolga tushirish
            pPr.set('indent', '0')
            pPr.set('marL', '0')
            run = p.add_run()
            run.text = str(item)
            run.font.size = Pt(font_pt)

    # Rasm yuklab olish va joylashtirish
    query = image_query or content_data.get("image_query", content_data.get("title", "nature"))
    img_path = fetch_image(query)
    place_image_in_placeholder(slide, 2, img_path)


def fill_slide_8_conclusion(slide, conclusion_data):
    """
    Slayd 8 — Xulosa / Rahmat (TITLE_AND_BODY_1).
    Sarlavha (idx=0) + Asosiy matn (idx=1).
    """
    title_ph = find_placeholder_by_idx(slide, 0)  # TITLE
    body_ph  = find_placeholder_by_idx(slide, 1)  # BODY

    if title_ph:
        auto_shrink_text(title_ph, conclusion_data.get("title", "Xulosa"), base_font_pt=32, bold=True)
    if body_ph:
        set_text_list_auto(body_ph, conclusion_data.get("content", []), base_font_pt=20)


# ═══════════════════════════════════════════════════════════════
# 2 BOSQICHLI TIZIM
# ═══════════════════════════════════════════════════════════════

# Slayd turi xaritasi (0-indexed kontent slayd pozitsiyasi → tur nomi)
SLIDE_TYPE_NAMES = {
    0: "three_columns",   # 3-slayd: 3 ustun
    1: "two_columns",     # 4-slayd: 2 ustun
    2: "image_left",      # 5-slayd: chapda rasm
    3: "quote",           # 6-slayd: iqtibos
    4: "image_right",     # 7-slayd: o'ngda rasm
}


def generate_plan_with_titles(topic, slide_count, language):
    """
    1-BOSQICH: Mavzu bo'yicha reja va har bir kontent slayd sarlavhasini yaratadi.

    Qaytaradi:
    {
      "plan": ["1. ...", "2. ...", "3. ..."],   # 3-5 ta, slayd soniga mos
      "slide_titles": ["Sarlavha 1", "Sarlavha 2", ...]  # kontent slaydlar uchun
    }
    """
    # Slayd soniga mos reja punktlari soni
    plan_count_map = {5: 3, 10: 4, 15: 4, 20: 5, 25: 5, 30: 5}
    plan_count = plan_count_map.get(slide_count, 4)

    # Kontent slaydlar soni (5 ta shablon × takrorlash)
    content_count = slide_count  # 5, 10, 15, 20, 25, 30

    prompt = (
        f"Mavzu: '{topic}'. Taqdimot uchun reja va slayd sarlavhalarini yarat.\n"
        f"Slaydlar soni: {slide_count}. Til: {language}.\n\n"
        f"QOIDALAR:\n"
        f"1. 'plan' massivida AYNAN {plan_count} ta nuqta bo'lsin. "
        f"Har bir nuqta mavzuni chuqur yorituvchi, aniq va o'ziga xos bo'lsin. "
        f"'Kirish', 'Asosiy qism', 'Xulosa' kabi umumiy so'zlar ISHLATILMASIN. "
        f"Har bir nuqta FAQAT oddiy arab raqami bilan boshlansin: '1. matn', '2. matn' — "
        f"ichki raqamlash (1.1, 1.2) MUTLAQO ISHLATILMASIN.\n"
        f"2. 'slide_titles' massivida AYNAN {content_count} ta sarlavha bo'lsin. "
        f"Har bir sarlavha qisqa (3-6 so'z), aniq va mavzuga oid bo'lsin. "
        f"Sarlavhalar reja nuqtalariga mos va izchil bo'lsin.\n\n"
        f"JSON formatida qaytarish shart:\n"
        f"{{\"plan\": [\"1. ...\", \"2. ...\"], \"slide_titles\": [\"...\", \"...\", ...]}}"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            max_tokens=1500,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Siz taqdimot reja va sarlavhalar yaratuvchi mutaxasssissiz. "
                        "Faqat JSON formatida javob bering. "
                        "Reja nuqtalari mavzudan kelib chiqib, aniq va o'ziga xos bo'lsin. "
                        "Umumiy iboralar ishlatmang. "
                        "Reja nuqtalarida HECH QACHON ichki raqamlash (1.1, 1.2) ishlatma."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        # Reja punktlarini cheklash va tozalash
        raw_plan = result.get("plan", [])[:plan_count]
        # Ichki raqamlashni tozalash: '1.1. matn' → '1. matn'
        import re
        clean_plan = []
        for idx, item in enumerate(raw_plan):
            # Har qanday "N.M. " yoki "N.M " prefiksini olib tashlash
            cleaned = re.sub(r'^\d+\.\d+\.?\s*', '', str(item)).strip()
            # Agar raqam bilan boshlanmasa, qo'shish
            if not re.match(r'^\d+\.', cleaned):
                cleaned = f"{idx+1}. {cleaned}"
            clean_plan.append(cleaned)
        result["plan"] = clean_plan
        result["slide_titles"] = result.get("slide_titles", [])[:content_count]
        logging.info(f"1-bosqich tayyor: {len(result['plan'])} reja, {len(result['slide_titles'])} sarlavha")
        return result
    except Exception as e:
        logging.error(f"generate_plan_with_titles xatolik: {e}")
        return None


def generate_all_content(topic, slide_count, language, slide_titles):
    """
    2-BOSQICH: Tasdiqlangan sarlavhalar bo'yicha barcha kontent slaydlar uchun
    matnlarni BITTA GPT so'rovida yaratadi.

    Qaytaradi: list of dicts, har biri bir kontent slayd uchun.
    """
    content_count = len(slide_titles)
    slides_info = []
    for i, title in enumerate(slide_titles):
        stype = SLIDE_TYPE_NAMES.get(i % 5, "image_left")
        if stype == "three_columns":
            fmt = f'{{"title": "{title}", "col1": "...", "col2": "...", "col3": "...", "image_query": "..."}}'
            desc = "3 ta ALOHIDA ustun (col1, col2, col3 — UCHALA MAJBURIY), har biri kamida 4-6 jumla, hech biri bo'sh qolmasin"
        elif stype == "two_columns":
            fmt = f'{{"title": "{title}", "col1": "...", "col2": "...", "image_query": "..."}}'  
            desc = "2 ta ustun, har biri kamida 6-8 jumla, matn blokini to'ldirsin"
        elif stype in ("image_left", "image_right"):
            fmt = f'{{"title": "{title}", "content": ["...", "..."], "image_query": "..."}}'
            desc = "2 ta punkt, har biri 3-5 jumla, image_query inglizcha"
        else:  # quote
            fmt = f'{{"title": "{title}", "content": ["...", "..."], "image_query": "..."}}'
            desc = "2 ta paragraf, har biri 3-5 jumla"
        slides_info.append(f"  Slayd {i+1} ('{title}', format: {desc}): {fmt}")

    slides_list_str = "\n".join(slides_info)

    prompt = (
        f"Mavzu: '{topic}'. Til: {language}.\n"
        f"Quyidagi {content_count} ta slayd uchun kontent yoz.\n"
        f"Har bir slayd uchun ko'rsatilgan formatda JSON ob'ekt qaytarish kerak.\n\n"
        f"{slides_list_str}\n\n"
        f"Barcha slaydlarni bitta JSON massivida qaytaring:\n"
        f"{{\"slides\": [{{...}}, {{...}}, ...]}}"
    )

    # Slayd soniga qarab max_tokens hisoblash
    max_tok_map = {5: 2000, 10: 3500, 15: 5000, 20: 6500, 25: 8000, 30: 10000}
    max_tok = max_tok_map.get(len(slide_titles), 4000)

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            max_tokens=max_tok,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Siz taqdimot slaydlari uchun kontent yaratuvchi mutaxasssissiz. "
                        "Faqat JSON formatida javob bering. "
                        "Har bir slayd uchun batafsil, ma'lumotli, to'liq matn yozing — "
                        "matnlarni qisqartirma, har bir ustun/paragraf uchun kamida 3-5 jumla yoz. "
                        "image_query har doim ingliz tilida bo'lsin."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        slides = result.get("slides", [])
        logging.info(f"2-bosqich tayyor: {len(slides)} slayd kontent")
        return slides
    except Exception as e:
        logging.error(f"generate_all_content xatolik: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# ASOSIY FUNKSIYA
# ═══════════════════════════════════════════════════════════════

def generate_template_1_presentation(prs, topic, requested_slide_count, language,
                                       name_surname="", plan=None,
                                       content_data_list=None):
    """
    8 slaydli shablon asosida taqdimot yaratadi.

    2-bosqichli tizim bilan ishlash uchun:
      - plan: {"content": ["1. ...", "2. ...", ...]}  (1-bosqichdan)
      - content_data_list: list of dicts (2-bosqichdan generate_all_content())

    Agar content_data_list berilmasa, eski usulda har bir slayd uchun alohida GPT so'rovi yuboriladi.
    """
    logging.info(f"Taqdimot yaratilmoqda: mavzu='{topic}', slaydlar={requested_slide_count}, til={language}")

    # ── 1. Shablon tuzilmasini qurish ──
    total_content_slides = build_slide_structure(prs, requested_slide_count)
    total_slides = len(prs.slides)

    # ── 2. Kontent ma'lumotlarini tayyorlash ──

    # Reja
    if plan is None or not isinstance(plan, dict) or not plan.get("content"):
        plan = {"title": "Reja", "content": ["Kirish", "Asosiy qism", "Xulosa"]}

    # Kontent slaydlari
    if content_data_list is None:
        # Eski usul: har bir slayd uchun alohida GPT so'rovi
        slide_type_map = {
            0: "three_columns",
            1: "two_columns",
            2: None,
            3: None,
            4: None,
        }
        content_data_list = []
        for i in range(total_content_slides):
            stype = slide_type_map.get(i % 5, None)
            data = generate_slide_content(topic, i + 3, total_slides, language, slide_type=stype)
            if not data:
                if stype == "three_columns":
                    data = {"title": f"{topic} — {i+1}", "col1": "Birinchi ustun", "col2": "Ikkinchi ustun", "col3": "Uchinchi ustun", "image_query": topic}
                elif stype == "two_columns":
                    data = {"title": f"{topic} — {i+1}", "col1": "Birinchi ustun", "col2": "Ikkinchi ustun", "image_query": topic}
                else:
                    data = {"title": f"{topic} — {i+1}", "content": ["Asosiy ma'lumot", "Qo'shimcha tafsilotlar"], "image_query": topic}
            content_data_list.append(data)
    else:
        # 2-bosqich: content_data_list tayyor, faqat uzunligini tekshirish
        while len(content_data_list) < total_content_slides:
            content_data_list.append({"title": topic, "content": ["Ma'lumot"], "image_query": topic})

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
        slide_index = i + 2  # 0-indexed
        slide = prs.slides[slide_index]
        data = content_data_list[i]
        image_query = data.get("image_query", topic)

        slide_type = i % 5  # 0=3-slayd, 1=4-slayd, 2=5-slayd, 3=6-slayd, 4=7-slayd

        if slide_type == 0:
            fill_slide_3_three_columns(slide, data)
        elif slide_type == 1:
            fill_slide_4_two_columns(slide, data)
        elif slide_type == 2:
            fill_slide_5_image_left(slide, data, image_query)
        elif slide_type == 3:
            fill_slide_6_quote(slide, data)
        elif slide_type == 4:
            fill_slide_7_image_right(slide, data, image_query)

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


# ═══════════════════════════════════════════════════════════════
# 2-SHABLON TUZILMASI (2.pptx)
# ═══════════════════════════════════════════════════════════════
#
# Slayd indekslari (0-based):
#   0 → Slayd 1: TITLE            — Muqova (sarlavha + subtitle)
#   1 → Slayd 2: TITLE            — Reja (sarlavha + subtitle)
#   2 → Slayd 3: SECTION_TITLE    — Bo'lim sarlavhasi (sarlavha + tavsif)
#   3 → Slayd 4: TWO_COLUMNS      — Ikki ustunli (sarlavha + 2 ustun)
#   4 → Slayd 5: CUSTOM_1         — Uch ustunli (sarlavha + 3 ustun)
#   5 → Slayd 6: CUSTOM_1_1       — Sarlavha + asosiy matn + qo'shimcha
#   6 → Slayd 7: CUSTOM_4_1_1_1_1 — Rasm + matn (o'ngda rasm)
#   7 → Slayd 8: TITLE_AND_BODY   — Xulosa / Thanks
#
# Takrorlash: 3-7 slaydlar (index 2-6) takrorlanadi
# ═══════════════════════════════════════════════════════════════

CONTENT_SLIDE_TEMPLATE_INDICES_2 = [2, 3, 4, 5, 6]  # 2-shablondagi 3-7 slaydlar


def build_slide_structure_2(prs, requested_content_count):
    """
    2-shablon uchun tuzilma quradi.
    Xuddi 1-shablon kabi: 3-7 slaydlar takrorlanadi, 8-slayd oxirida.
    """
    full_repeats = max(1, round(requested_content_count / 5))
    total_content_slides = full_repeats * 5

    logging.info(f"[T2] Kontent slaydlari: {requested_content_count} so'raldi, "
                 f"{full_repeats} marta takrorlanadi ({total_content_slides} ta kontent slayd)")

    extra_sets_needed = full_repeats - 1

    for set_num in range(extra_sets_needed):
        for slide_template_idx in CONTENT_SLIDE_TEMPLATE_INDICES_2:
            duplicate_slide(prs, slide_template_idx)
        logging.info(f"  [T2] {set_num + 2}-to'plam qo'shildi. Jami slaydlar: {len(prs.slides)}")

    # Xulosa slaydini (index 7) oxiriga ko'chirish
    conclusion_current_index = 7
    last_index = len(prs.slides) - 1
    move_slide(prs, conclusion_current_index, last_index)

    logging.info(f"[T2] Yakuniy tuzilma: {len(prs.slides)} ta slayd")
    return total_content_slides


# ─── 2-Shablon slayd to'ldirish funksiyalari ───────────────────

def fill_t2_slide_1_cover(slide, topic, name_surname):
    """
    2-Shablon Slayd 1 — Muqova (TITLE).
    idx=0: Sarlavha (CENTER_TITLE, 55pt, markazda)
    idx=1: Subtitle (ism-familiya yoki sana, markazda)
    """
    title_ph    = find_placeholder_by_idx(slide, 0)
    subtitle_ph = find_placeholder_by_idx(slide, 1)

    if title_ph:
        auto_shrink_text(title_ph, topic.upper(), base_font_pt=48, min_font_pt=22, bold=True)

    if subtitle_ph:
        if name_surname and name_surname.strip():
            auto_shrink_text(subtitle_ph, name_surname, base_font_pt=22, min_font_pt=14)
        else:
            # Bo'sh qoldirish — shablon matnini o'chirish
            tf = subtitle_ph.text_frame
            tf.clear()
            if tf.paragraphs:
                tf.paragraphs[0].text = ""


def fill_t2_slide_2_plan(slide, plan_data):
    """
    2-Shablon Slayd 2 — Reja (TITLE layout).
    idx=0: Sarlavha — har doim "Reja"
    idx=1: Subtitle — raqamli ro'yxat (1. 2. 3. 4.)
    """
    import re
    from pptx.enum.text import PP_ALIGN
    from pptx.oxml.ns import qn
    from lxml import etree

    title_ph = find_placeholder_by_idx(slide, 0)
    body_ph  = find_placeholder_by_idx(slide, 1)

    if title_ph:
        auto_shrink_text(title_ph, "Reja", base_font_pt=40, bold=True)

    if body_ph:
        content = plan_data.get("content", [])[:4]
        numbered = []
        for i, item in enumerate(content):
            text = re.sub(r'^[\d]+[\d\.]*\.?\s*', '', str(item)).strip()
            numbered.append(f"{i+1}. {text}")

        tf = body_ph.text_frame
        tf.clear()
        tf.word_wrap = True

        total_chars = sum(len(s) for s in numbered)
        if total_chars <= 150:
            font_pt = 22
        elif total_chars <= 280:
            font_pt = 18
        else:
            font_pt = 15

        for i, item in enumerate(numbered):
            if i == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            # Bullet o'chirish
            pPr = p._p.get_or_add_pPr()
            for tag in ['a:buChar', 'a:buAutoNum', 'a:buFont', 'a:buSzPct']:
                for el in pPr.findall(qn(tag)):
                    pPr.remove(el)
            etree.SubElement(pPr, qn('a:buNone'))
            pPr.set('marL', '0')
            pPr.set('indent', '0')
            p.alignment = PP_ALIGN.LEFT
            run = p.add_run()
            run.text = item
            run.font.size = Pt(font_pt)


def fill_t2_slide_3_section(slide, content_data):
    """
    2-Shablon Slayd 3 — Bo'lim sarlavhasi (SECTION_TITLE_AND_DESCRIPTION).
    idx=0: Sarlavha (markazda, katta)
    idx=1: Tavsif (sarlavha ostida, kichikroq)
    col1/col2/col3 yoki content ro'yxatidan matn oladi.
    """
    from pptx.enum.text import PP_ALIGN
    from pptx.oxml.ns import qn
    from lxml import etree

    title_ph = find_placeholder_by_idx(slide, 0)
    body_ph  = find_placeholder_by_idx(slide, 1)

    if title_ph:
        auto_shrink_text(title_ph, content_data.get("title", ""), base_font_pt=32, min_font_pt=18, bold=True)

    if body_ph:
        # col1/col2/col3 formatidan yoki content ro'yxatidan matn olish
        col1 = content_data.get("col1", "")
        col2 = content_data.get("col2", "")
        col3 = content_data.get("col3", "")
        if col1 or col2 or col3:
            # col1+col2+col3 ni bitta matn sifatida birlashtirish
            combined = " ".join(filter(None, [col1, col2, col3]))
            items = [combined]
        else:
            items = content_data.get("content", [])

        tf = body_ph.text_frame
        tf.clear()
        tf.word_wrap = True

        total_chars = sum(len(str(i)) for i in items[:3])
        font_pt = 18 if total_chars <= 200 else 15 if total_chars <= 400 else 12

        for idx_p, item in enumerate(items[:3]):
            if idx_p == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            pPr = p._p.get_or_add_pPr()
            for tag in ['a:buChar', 'a:buAutoNum']:
                for el in pPr.findall(qn(tag)):
                    pPr.remove(el)
            etree.SubElement(pPr, qn('a:buNone'))
            pPr.set('marL', '0')
            pPr.set('indent', '0')
            p.alignment = PP_ALIGN.LEFT
            run = p.add_run()
            run.text = str(item)
            run.font.size = Pt(font_pt)

    # Shape[4] (teskari text_box, rot=180) shablon dan o'chirilgan — hech narsa qilmasa ham bo'ladi


def fill_t2_slide_4_two_columns(slide, content_data):
    """
    2-Shablon Slayd 4 — Ikki ustunli (TITLE_AND_TWO_COLUMNS).
    idx=0: Sarlavha (yuqorida, keng)
    idx=1: Chap ustun (chapdan 2.30sm)
    idx=2: O'ng ustun (chapdan 13.34sm)
    """
    from pptx.enum.text import PP_ALIGN
    from pptx.oxml.ns import qn
    from lxml import etree

    title_ph = find_placeholder_by_idx(slide, 0)
    col1_ph  = find_placeholder_by_idx(slide, 1)
    col2_ph  = find_placeholder_by_idx(slide, 2)

    if title_ph:
        auto_shrink_text(title_ph, content_data.get("title", ""), base_font_pt=28, min_font_pt=16, bold=True)

    col1_text = content_data.get("col1", "")
    col2_text = content_data.get("col2", "")
    if not col1_text:
        items = content_data.get("content", ["", ""])
        col1_text = items[0] if len(items) > 0 else ""
        col2_text = items[1] if len(items) > 1 else ""

    def write_col(ph, text):
        if not ph or not text:
            return
        tf = ph.text_frame
        tf.clear()
        tf.word_wrap = True
        font_pt = 16 if len(text) <= 300 else 13 if len(text) <= 500 else 11
        p = tf.paragraphs[0]
        pPr = p._p.get_or_add_pPr()
        for tag in ['a:buChar', 'a:buAutoNum']:
            for el in pPr.findall(qn(tag)):
                pPr.remove(el)
        etree.SubElement(pPr, qn('a:buNone'))
        pPr.set('marL', '0')
        pPr.set('indent', '0')
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = text
        run.font.size = Pt(font_pt)

    write_col(col1_ph, col1_text)
    write_col(col2_ph, col2_text)


def fill_t2_slide_5_three_columns(slide, content_data):
    """
    2-Shablon Slayd 5 — Uch ustunli (CUSTOM_1).
    idx=0: Sarlavha (yuqorida, keng)
    idx=1: Chap ustun (placeholder, chapdan 2.01sm)
    shape[2]: O'rta ustun (TEXT_BOX, chapdan 9.38sm)
    shape[3]: O'ng ustun (TEXT_BOX, chapdan 17.02sm)
    """
    from pptx.enum.text import PP_ALIGN
    from pptx.oxml.ns import qn
    from lxml import etree

    title_ph = find_placeholder_by_idx(slide, 0)
    col1_ph  = find_placeholder_by_idx(slide, 1)
    # O'rta va o'ng ustunlarni to'g'ridan-to'g'ri shape indeksi bilan topish
    col2_ph = None
    col3_ph = None
    for shape in slide.shapes:
        if shape.is_placeholder:
            continue
        if not hasattr(shape, 'text_frame'):
            continue
        left_cm = shape.left / 914400 * 2.54 if shape.left else 0
        if 8.0 <= left_cm <= 12.0:
            col2_ph = shape
        elif 16.0 <= left_cm <= 21.0:
            col3_ph = shape

    if title_ph:
        auto_shrink_text(title_ph, content_data.get("title", ""), base_font_pt=26, min_font_pt=16, bold=True)

    col1_text = content_data.get("col1", "")
    col2_text = content_data.get("col2", "")
    col3_text = content_data.get("col3", "")
    if not col1_text:
        items = content_data.get("content", ["", "", ""])
        col1_text = items[0] if len(items) > 0 else ""
        col2_text = items[1] if len(items) > 1 else ""
        col3_text = items[2] if len(items) > 2 else ""
    # Fallback: agar col3 bo'sh bo'lsa, col1 yoki col2 dan olinsin
    if not col3_text and col2_text:
        # col2 ni ikkiga bo'lib col3 ga berish
        words = col2_text.split('. ')
        half = len(words) // 2
        if half > 0:
            col3_text = '. '.join(words[half:]).strip()
            col2_text = '. '.join(words[:half]).strip()
            if col3_text and not col3_text.endswith('.'):
                col3_text += '.'
    if not col3_text and col1_text:
        col3_text = col1_text

    def write_col(ph, text):
        if not ph:
            return
        if not text:
            text = ""
        tf = ph.text_frame
        # XML darajasida to'liq tozalash — barcha paragraflarni o'chirish
        txBody = tf._txBody
        # Barcha <a:p> elementlarini o'chirib, bitta yangi qo'shish
        for p_el in txBody.findall(qn('a:p')):
            txBody.remove(p_el)
        # Yangi paragraf qo'shish
        from lxml import etree as _etree
        new_p = _etree.SubElement(txBody, qn('a:p'))
        pPr = _etree.SubElement(new_p, qn('a:pPr'))
        _etree.SubElement(pPr, qn('a:buNone'))
        pPr.set('marL', '0')
        pPr.set('indent', '0')
        # Alignment
        pPr.set('algn', 'l')
        # Run qo'shish
        new_r = _etree.SubElement(new_p, qn('a:r'))
        rPr = _etree.SubElement(new_r, qn('a:rPr'))
        rPr.set('lang', 'uz-UZ')
        rPr.set('dirty', '0')
        font_pt = 16 if len(text) <= 200 else 13 if len(text) <= 400 else 11
        rPr.set('sz', str(font_pt * 100))
        t_el = _etree.SubElement(new_r, qn('a:t'))
        t_el.text = text
        tf.word_wrap = True

    write_col(col1_ph, col1_text)
    write_col(col2_ph, col2_text)
    write_col(col3_ph, col3_text)


def fill_t2_slide_6_text(slide, content_data):
    """
    2-Shablon Slayd 6 — Sarlavha + asosiy matn + qo'shimcha (CUSTOM_1_1).
    idx=0: Sarlavha (yuqorida)
    idx=1: Asosiy matn (o'rtada, katta)
    idx=6: Qo'shimcha matn (pastda)
    """
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.oxml.ns import qn
    from lxml import etree

    title_ph = find_placeholder_by_idx(slide, 0)
    body_ph  = find_placeholder_by_idx(slide, 1)
    extra_ph = find_placeholder_by_idx(slide, 6)

    if title_ph:
        auto_shrink_text(title_ph, content_data.get("title", ""), base_font_pt=26, min_font_pt=14, bold=True)

    if body_ph:
        items = content_data.get("content", [])
        tf = body_ph.text_frame
        tf.clear()
        tf.word_wrap = True
        # Matnni 4 paragrafga kengaytirish
        expanded = []
        for item in items[:2]:
            text = str(item)
            sentences = text.replace('! ', '!|').replace('. ', '.|').replace('? ', '?|').split('|')
            mid = max(1, len(sentences) // 2)
            part1 = ' '.join(sentences[:mid]).strip()
            part2 = ' '.join(sentences[mid:]).strip()
            if part1:
                expanded.append(part1)
            if part2:
                expanded.append(part2)

        total_chars = sum(len(s) for s in expanded)
        font_pt = 16 if total_chars <= 300 else 14 if total_chars <= 500 else 12

        for idx_p, item in enumerate(expanded):
            if idx_p == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            pPr = p._p.get_or_add_pPr()
            for tag in ['a:buChar', 'a:buAutoNum']:
                for el in pPr.findall(qn(tag)):
                    pPr.remove(el)
            etree.SubElement(pPr, qn('a:buNone'))
            pPr.set('marL', '0')
            pPr.set('indent', '0')
            p.alignment = PP_ALIGN.LEFT
            run = p.add_run()
            run.text = item
            run.font.size = Pt(font_pt)
        body_ph.text_frame.vertical_anchor = MSO_ANCHOR.TOP

    # idx=6 placeholder shablon dan o'chirilgan — hech narsa qilmasa ham bo'ladi


def fill_t2_slide_7_image(slide, content_data, image_query):
    """
    2-Shablon Slayd 7 — Rasm va matn (CUSTOM_4_1_1_1_1).
    idx=0: Sarlavha (chapda, yuqorida)
    idx=1: Matn bloki (chapda, pastroq)
    Rasm: o'ng tomonda katta ko'k to'rtburchak (GROUP shape, chapdan 14.27sm)
    """
    from pptx.util import Cm
    from pptx.enum.text import PP_ALIGN
    from pptx.oxml.ns import qn
    from lxml import etree

    title_ph = find_placeholder_by_idx(slide, 0)
    body_ph  = find_placeholder_by_idx(slide, 1)

    if title_ph:
        auto_shrink_text(title_ph, content_data.get("title", ""), base_font_pt=28, min_font_pt=14, bold=True)

    if body_ph:
        items = content_data.get("content", [])
        tf = body_ph.text_frame
        tf.clear()
        tf.word_wrap = True
        total_chars = sum(len(str(i)) for i in items[:2])
        font_pt = 16 if total_chars <= 200 else 13 if total_chars <= 400 else 11

        for idx_p, item in enumerate(items[:2]):
            if idx_p == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            pPr = p._p.get_or_add_pPr()
            for tag in ['a:buChar', 'a:buAutoNum']:
                for el in pPr.findall(qn(tag)):
                    pPr.remove(el)
            etree.SubElement(pPr, qn('a:buNone'))
            pPr.set('marL', '0')
            pPr.set('indent', '0')
            p.alignment = PP_ALIGN.LEFT
            run = p.add_run()
            run.text = str(item)
            run.font.size = Pt(font_pt)

    # Rasm: o'ng tomondagi katta GROUP shape o'rniga rasm qo'yish
    # GROUP shape koordinatalari: left=14.27sm, top=1.97sm, width=9.44sm, height=10.35sm
    query = image_query or content_data.get("image_query", content_data.get("title", "nature"))
    img_path = fetch_image(query)
    if img_path:
        try:
            from pptx.util import Cm
            left = Cm(14.27)
            top  = Cm(1.97)
            width = Cm(9.44)
            height = Cm(10.35)
            slide.shapes.add_picture(img_path, left, top, width, height)
            os.remove(img_path)
            logging.info(f"[T2] Rasm slayd 7 ga joylashtirildi.")
        except Exception as e:
            logging.error(f"[T2] Rasm joylashtirish xatolik: {e}")


def fill_t2_slide_8_conclusion(slide, conclusion_data):
    """
    2-Shablon Slayd 8 — Xulosa / Thanks (TITLE_AND_BODY).
    idx=0: Sarlavha (yuqorida, chapda)
    idx=1: Asosiy matn (katta maydon)
    """
    title_ph = find_placeholder_by_idx(slide, 0)
    body_ph  = find_placeholder_by_idx(slide, 1)

    if title_ph:
        # Xulosa sarlavhasi — mavzuga mos til bilan
        title_text = conclusion_data.get("title", "Xulosa")
        auto_shrink_text(title_ph, title_text, base_font_pt=28, min_font_pt=16, bold=True)

    if body_ph:
        set_text_list_auto(body_ph, conclusion_data.get("content", []), base_font_pt=18)


# ═══════════════════════════════════════════════════════════════
# 2-SHABLON ASOSIY FUNKSIYA
# ═══════════════════════════════════════════════════════════════

def generate_template_2_presentation(prs, topic, requested_slide_count, language,
                                      name_surname="", plan=None,
                                      content_data_list=None):
    """
    2-shablon (2.pptx) asosida taqdimot yaratadi.
    1-shablon bilan bir xil 2-bosqichli tizim bilan ishlaydi.
    """
    logging.info(f"[T2] Taqdimot yaratilmoqda: mavzu='{topic}', slaydlar={requested_slide_count}, til={language}")

    # ── 1. Shablon tuzilmasini qurish ──
    total_content_slides = build_slide_structure_2(prs, requested_slide_count)

    # ── 2. Kontent ma'lumotlarini tayyorlash ──

    # Reja
    if plan is None or not isinstance(plan, dict) or not plan.get("content"):
        plan = {"title": "Reja", "content": ["Kirish", "Asosiy qism", "Xulosa"]}

    # Kontent slaydlari
    if content_data_list is None:
        # Zaxira: har bir slayd uchun alohida GPT so'rovi
        slide_type_map = {
            0: "three_columns",
            1: "two_columns",
            2: None,
            3: None,
            4: None,
        }
        content_data_list = []
        for i in range(total_content_slides):
            stype = slide_type_map.get(i % 5, None)
            data = generate_slide_content(topic, i + 3, len(prs.slides), language, slide_type=stype)
            if not data:
                data = {"title": f"{topic} — {i+1}", "content": ["Ma'lumot"], "image_query": topic}
            content_data_list.append(data)
    else:
        while len(content_data_list) < total_content_slides:
            content_data_list.append({"title": topic, "content": ["Ma'lumot"], "image_query": topic})

    # Xulosa
    conclusion = generate_slide_content(topic, len(prs.slides), len(prs.slides), language, is_conclusion=True)
    if not conclusion:
        conclusion = {"title": "Xulosa", "content": ["Asosiy xulosalar", "Tavsiyalar"]}

    # ── 3. Slaydlarni to'ldirish ──

    # Slayd 1: Muqova
    fill_t2_slide_1_cover(prs.slides[0], topic, name_surname)

    # Slayd 2: Reja
    fill_t2_slide_2_plan(prs.slides[1], plan)

    # Kontent slaydlar (3-7 takrorlanadi)
    # 2-shablon slayd turlari (0-indexed kontent pozitsiyasi):
    # 0 → slayd 3: SECTION_TITLE (bo'lim sarlavhasi + tavsif)
    # 1 → slayd 4: TWO_COLUMNS (2 ustun)
    # 2 → slayd 5: THREE_COLUMNS (3 ustun)
    # 3 → slayd 6: TEXT (sarlavha + katta matn)
    # 4 → slayd 7: IMAGE (rasm + matn)

    for i in range(total_content_slides):
        slide_index = i + 2
        slide = prs.slides[slide_index]
        data = content_data_list[i]
        image_query = data.get("image_query", topic)
        slide_type = i % 5

        if slide_type == 0:
            fill_t2_slide_3_section(slide, data)
        elif slide_type == 1:
            fill_t2_slide_4_two_columns(slide, data)
        elif slide_type == 2:
            fill_t2_slide_5_three_columns(slide, data)
        elif slide_type == 3:
            fill_t2_slide_6_text(slide, data)
        elif slide_type == 4:
            fill_t2_slide_7_image(slide, data, image_query)

        logging.info(f"  [T2] Slayd {slide_index + 1} to'ldirildi (tur {slide_type}): {data.get('title', '')}")

    # Oxirgi slayd: Xulosa
    fill_t2_slide_8_conclusion(prs.slides[-1], conclusion)

    # ── 4. Faylni xotiraga saqlash ──
    prs_bytes = BytesIO()
    prs.save(prs_bytes)
    prs_bytes.seek(0)

    logging.info(f"[T2] Taqdimot tayyor: {len(prs.slides)} ta slayd")
    return prs_bytes


# ═══════════════════════════════════════════════════════════════
# 3-SHABLON TUZILMASI (3.pptx)
# ═══════════════════════════════════════════════════════════════
#
# Slayd indekslari (0-based):
#   0 → Slayd 1: TITLE            — Muqova (sarlavha + subtitle)
#   1 → Slayd 2: SECTION_HEADER   — Reja (idx=0 ro'yxat, idx=2 "REJA" fixed)
#   2 → Slayd 3: ONE_COLUMN_TEXT  — Bir ustunli matn
#   3 → Slayd 4: TWO_COLUMNS      — Ikki ustunli
#   4 → Slayd 5: THREE_COLUMNS    — Uch ustunli
#   5 → Slayd 6: IMAGE_LEFT       — Chapda rasm, o'ngda matn
#   6 → Slayd 7: QUOTE            — Chapda matn, o'ngda dekorativ
#   7 → Slayd 8: CONCLUSION       — Xulosa / Thanks
#
# Takrorlash: 3-7 slaydlar (index 2-6) takrorlanadi
# ═══════════════════════════════════════════════════════════════

CONTENT_SLIDE_TEMPLATE_INDICES_3 = [2, 3, 4, 5, 6]  # 3-shablondagi 3-7 slaydlar


def build_slide_structure_3(prs, requested_content_count):
    """
    3-shablon uchun tuzilma quradi.
    3-7 slaydlar takrorlanadi, 8-slayd oxirida.
    """
    full_repeats = max(1, round(requested_content_count / 5))
    total_content_slides = full_repeats * 5

    logging.info(f"[T3] Kontent slaydlari: {requested_content_count} so'raldi, "
                 f"{full_repeats} marta takrorlanadi ({total_content_slides} ta kontent slayd)")

    extra_sets_needed = full_repeats - 1

    for set_num in range(extra_sets_needed):
        for slide_template_idx in CONTENT_SLIDE_TEMPLATE_INDICES_3:
            duplicate_slide(prs, slide_template_idx)
        logging.info(f"  [T3] {set_num + 2}-to'plam qo'shildi. Jami slaydlar: {len(prs.slides)}")

    # Xulosa slaydini (index 7) oxiriga ko'chirish
    conclusion_current_index = 7
    last_index = len(prs.slides) - 1
    move_slide(prs, conclusion_current_index, last_index)

    logging.info(f"[T3] Yakuniy tuzilma: {len(prs.slides)} ta slayd")
    return total_content_slides


# ─── 3-Shablon slayd to'ldirish funksiyalari ───────────────────

def fill_t3_slide_1_cover(slide, topic, name_surname):
    """
    3-Shablon Slayd 1 — Muqova (TITLE).
    idx=0: CENTER_TITLE — asosiy sarlavha (katta, oq)
    idx=1: SUBTITLE — ism-familiya yoki sana (kichik)
    """
    title_ph    = find_placeholder_by_idx(slide, 0)
    subtitle_ph = find_placeholder_by_idx(slide, 1)

    if title_ph:
        auto_shrink_text(title_ph, topic.upper(), base_font_pt=48, min_font_pt=22, bold=False)

    if subtitle_ph:
        if name_surname and name_surname.strip():
            auto_shrink_text(subtitle_ph, name_surname, base_font_pt=20, min_font_pt=12)
        else:
            tf = subtitle_ph.text_frame
            tf.clear()
            if tf.paragraphs:
                tf.paragraphs[0].text = ""


def fill_t3_slide_2_plan(slide, plan_data):
    """
    3-Shablon Slayd 2 — Reja (SECTION_HEADER).
    idx=0: TITLE — reja ro'yxati (katta maydon, chapda)
    idx=2: TITLE — "REJA" yozuvi (o'ngda, FIXED — o'zgartirmaslik)
    """
    import re
    from pptx.enum.text import PP_ALIGN
    from pptx.oxml.ns import qn
    from lxml import etree

    body_ph = find_placeholder_by_idx(slide, 0)   # Ro'yxat maydoni
    # idx=2 ni o'zgartirmaymiz — "REJA" yozuvi fixed

    if body_ph:
        content = plan_data.get("content", [])[:5]
        numbered = []
        for i, item in enumerate(content):
            text = re.sub(r'^[\d]+[\d\.]*\.?\s*', '', str(item)).strip()
            numbered.append(f"{i+1}. {text}")

        tf = body_ph.text_frame
        tf.clear()
        tf.word_wrap = True

        total_chars = sum(len(s) for s in numbered)
        if total_chars <= 150:
            font_pt = 24
        elif total_chars <= 300:
            font_pt = 20
        else:
            font_pt = 16

        for i, item in enumerate(numbered):
            if i == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            pPr = p._p.get_or_add_pPr()
            for child in list(pPr):
                tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if tag in ('buChar', 'buAutoNum', 'buNone', 'buClr', 'buFont', 'buSzPct', 'indent', 'marL', 'algn'):
                    pPr.remove(child)
            etree.SubElement(pPr, qn('a:buNone'))
            pPr.set('marL', '0')
            pPr.set('indent', '0')
            pPr.set('algn', 'l')  # chapga tekislash
            run = p.add_run()
            run.text = item
            run.font.size = Pt(font_pt)


def fill_t3_slide_3_one_column(slide, content_data):
    """
    3-Shablon Slayd 3 — Bir ustunli matn (ONE_COLUMN_TEXT).
    idx=0: TITLE — sarlavha (yuqorida)
    idx=1: SUBTITLE — katta matn bloki (markazda)
    """
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.oxml.ns import qn
    from lxml import etree

    title_ph = find_placeholder_by_idx(slide, 0)
    body_ph  = find_placeholder_by_idx(slide, 1)

    if title_ph:
        auto_shrink_text(title_ph, content_data.get("title", ""), base_font_pt=28, min_font_pt=14, bold=True)

    if body_ph:
        from pptx.util import Inches, Emu
        from pptx.dml.color import RGBColor
        # Placeholder ni kattalashtirish: sarlavha pastidan slayd pastiga qadar
        body_ph.left   = Inches(1.35)
        body_ph.top    = Inches(1.50)
        body_ph.width  = Inches(7.21)
        body_ph.height = Inches(3.70)

        items = content_data.get("content", [])
        tf = body_ph.text_frame
        tf.clear()
        tf.word_wrap = True

        total_chars = sum(len(str(i)) for i in items[:4])
        if total_chars <= 300:
            font_pt = 18
        elif total_chars <= 600:
            font_pt = 15
        else:
            font_pt = 13

        for idx_p, item in enumerate(items[:4]):
            if idx_p == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            pPr = p._p.get_or_add_pPr()
            for child in list(pPr):
                tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if tag in ('buChar', 'buAutoNum', 'buNone', 'buClr', 'buFont', 'buSzPct', 'indent', 'marL'):
                    pPr.remove(child)
            etree.SubElement(pPr, qn('a:buNone'))
            pPr.set('marL', '0')
            pPr.set('indent', '0')
            run = p.add_run()
            run.text = str(item)
            run.font.size = Pt(font_pt)
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        body_ph.text_frame.vertical_anchor = MSO_ANCHOR.TOP


def fill_t3_slide_4_two_columns(slide, content_data):
    """
    3-Shablon Slayd 4 — Ikki ustunli (TITLE_AND_TWO_COLUMNS_1_1).
    idx=0: TITLE — sarlavha
    idx=1: SUBTITLE — o'ng ustun
    idx=2: SUBTITLE — chap ustun
    """
    from pptx.oxml.ns import qn
    from lxml import etree

    title_ph  = find_placeholder_by_idx(slide, 0)
    right_ph  = find_placeholder_by_idx(slide, 1)
    left_ph   = find_placeholder_by_idx(slide, 2)

    if title_ph:
        auto_shrink_text(title_ph, content_data.get("title", ""), base_font_pt=28, min_font_pt=14, bold=True)

    col1_text = content_data.get("col1", "")
    col2_text = content_data.get("col2", "")
    if not col1_text:
        items = content_data.get("content", ["", ""])
        col1_text = items[0] if len(items) > 0 else ""
        col2_text = items[1] if len(items) > 1 else ""

    def write_col(ph, text):
        if not ph or not text:
            return
        tf = ph.text_frame
        txBody = tf._txBody
        for p_el in txBody.findall(qn('a:p')):
            txBody.remove(p_el)
        from lxml import etree as _etree
        new_p = _etree.SubElement(txBody, qn('a:p'))
        pPr = _etree.SubElement(new_p, qn('a:pPr'))
        _etree.SubElement(pPr, qn('a:buNone'))
        pPr.set('marL', '0')
        pPr.set('indent', '0')
        pPr.set('algn', 'l')
        new_r = _etree.SubElement(new_p, qn('a:r'))
        rPr = _etree.SubElement(new_r, qn('a:rPr'))
        rPr.set('lang', 'uz-UZ')
        rPr.set('dirty', '0')
        font_pt = 16 if len(text) <= 200 else 13 if len(text) <= 400 else 11
        rPr.set('sz', str(font_pt * 100))
        t_el = _etree.SubElement(new_r, qn('a:t'))
        t_el.text = text
        tf.word_wrap = True

    write_col(left_ph, col1_text)
    write_col(right_ph, col2_text)


def fill_t3_slide_5_three_columns(slide, content_data):
    """
    3-Shablon Slayd 5 — Uch ustunli (CUSTOM_6).
    idx=0: TITLE — sarlavha
    idx=1: SUBTITLE — chap ustun
    idx=2: SUBTITLE — o'rta ustun
    idx=3: SUBTITLE — o'ng ustun
    """
    from pptx.oxml.ns import qn

    title_ph = find_placeholder_by_idx(slide, 0)
    col1_ph  = find_placeholder_by_idx(slide, 1)
    col2_ph  = find_placeholder_by_idx(slide, 2)
    col3_ph  = find_placeholder_by_idx(slide, 3)

    if title_ph:
        auto_shrink_text(title_ph, content_data.get("title", ""), base_font_pt=28, min_font_pt=14, bold=True)

    col1_text = content_data.get("col1", "")
    col2_text = content_data.get("col2", "")
    col3_text = content_data.get("col3", "")
    if not col1_text:
        items = content_data.get("content", ["", "", ""])
        col1_text = items[0] if len(items) > 0 else ""
        col2_text = items[1] if len(items) > 1 else ""
        col3_text = items[2] if len(items) > 2 else ""
    # Fallback: agar col3 bo'sh bo'lsa
    if not col3_text and col2_text:
        words = col2_text.split('. ')
        half = len(words) // 2
        if half > 0:
            col3_text = '. '.join(words[half:]).strip()
            col2_text = '. '.join(words[:half]).strip()
            if col3_text and not col3_text.endswith('.'):
                col3_text += '.'
    if not col3_text and col1_text:
        col3_text = col1_text

    def write_col(ph, text):
        if not ph or not text:
            return
        tf = ph.text_frame
        txBody = tf._txBody
        for p_el in txBody.findall(qn('a:p')):
            txBody.remove(p_el)
        from lxml import etree as _etree
        new_p = _etree.SubElement(txBody, qn('a:p'))
        pPr = _etree.SubElement(new_p, qn('a:pPr'))
        _etree.SubElement(pPr, qn('a:buNone'))
        pPr.set('marL', '0')
        pPr.set('indent', '0')
        pPr.set('algn', 'l')
        new_r = _etree.SubElement(new_p, qn('a:r'))
        rPr = _etree.SubElement(new_r, qn('a:rPr'))
        rPr.set('lang', 'uz-UZ')
        rPr.set('dirty', '0')
        font_pt = 14 if len(text) <= 200 else 12 if len(text) <= 400 else 10
        rPr.set('sz', str(font_pt * 100))
        t_el = _etree.SubElement(new_r, qn('a:t'))
        t_el.text = text
        tf.word_wrap = True

    write_col(col1_ph, col1_text)
    write_col(col2_ph, col2_text)
    write_col(col3_ph, col3_text)


def fill_t3_slide_6_image_left(slide, content_data, image_query):
    """
    3-Shablon Slayd 6 — Chapda rasm, o'ngda matn (CUSTOM).
    idx=0: TITLE — sarlavha (yuqorida, keng)
    idx=1: SUBTITLE — matn (o'ngda)
    idx=2: PICTURE — rasm placeholder (chapda, katta)
    """
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.oxml.ns import qn
    from lxml import etree

    title_ph = find_placeholder_by_idx(slide, 0)
    body_ph  = find_placeholder_by_idx(slide, 1)

    if title_ph:
        auto_shrink_text(title_ph, content_data.get("title", ""), base_font_pt=28, min_font_pt=14, bold=True)

    if body_ph:
        items = content_data.get("content", [])
        tf = body_ph.text_frame
        tf.clear()
        tf.word_wrap = True

        total_chars = sum(len(str(i)) for i in items[:3])
        if total_chars <= 250:
            font_pt = 16
        elif total_chars <= 500:
            font_pt = 13
        else:
            font_pt = 11

        for idx_p, item in enumerate(items[:3]):
            if idx_p == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            pPr = p._p.get_or_add_pPr()
            for child in list(pPr):
                tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if tag in ('buChar', 'buAutoNum', 'buNone', 'buClr', 'buFont', 'buSzPct', 'indent', 'marL'):
                    pPr.remove(child)
            etree.SubElement(pPr, qn('a:buNone'))
            pPr.set('marL', '0')
            pPr.set('indent', '0')
            run = p.add_run()
            run.text = str(item)
            run.font.size = Pt(font_pt)
        body_ph.text_frame.vertical_anchor = MSO_ANCHOR.TOP

    # Rasm placeholder (idx=2) ga rasm qo'yish
    query = image_query or content_data.get("image_query", content_data.get("title", "nature"))
    img_path = fetch_image(query)
    place_image_in_placeholder(slide, 2, img_path)


def fill_t3_slide_7_quote(slide, content_data, image_query=None):
    """
    3-Shablon Slayd 7 — Chapda matn, o'ngda rasm (CUSTOM_4_1).
    idx=0: TITLE — sarlavha (chapda, yuqorida)
    idx=1: SUBTITLE — katta matn bloki (chapda)
    O'ng tomonda GROUP shape ustiga rasm qo'yiladi.
    """
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.oxml.ns import qn
    from lxml import etree

    title_ph = find_placeholder_by_idx(slide, 0)
    body_ph  = find_placeholder_by_idx(slide, 1)

    if title_ph:
        auto_shrink_text(title_ph, content_data.get("title", ""), base_font_pt=26, min_font_pt=14, bold=True)

    if body_ph:
        items = content_data.get("content", [])
        tf = body_ph.text_frame
        tf.clear()
        tf.word_wrap = True

        total_chars = sum(len(str(i)) for i in items[:3])
        if total_chars <= 250:
            font_pt = 16
        elif total_chars <= 500:
            font_pt = 13
        else:
            font_pt = 11

        for idx_p, item in enumerate(items[:3]):
            if idx_p == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            pPr = p._p.get_or_add_pPr()
            for child in list(pPr):
                tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if tag in ('buChar', 'buAutoNum', 'buNone', 'buClr', 'buFont', 'buSzPct', 'indent', 'marL'):
                    pPr.remove(child)
            etree.SubElement(pPr, qn('a:buNone'))
            pPr.set('marL', '0')
            pPr.set('indent', '0')
            run = p.add_run()
            run.text = str(item)
            run.font.size = Pt(font_pt)
        body_ph.text_frame.vertical_anchor = MSO_ANCHOR.TOP

    # O'ng tomonga rasm qo'yish (GROUP shape o'rniga)
    query = image_query or content_data.get("image_query", content_data.get("title", "technology"))
    img_path = fetch_image(query)
    if img_path:
        from pptx.util import Inches, Emu
        # GROUP shape pozitsiyasi: left=4.46", top=1.24", width=4.39", height=2.93"
        left   = Inches(4.46)
        top    = Inches(1.24)
        width  = Inches(4.39)
        height = Inches(2.93)
        # GROUP shape ni o'chirish
        for shape in list(slide.shapes):
            if shape.shape_type == 6:  # GROUP
                sp = shape._element
                sp.getparent().remove(sp)
                break
        slide.shapes.add_picture(img_path, left, top, width, height)


def fill_t3_slide_8_conclusion(slide, conclusion_data):
    """
    3-Shablon Slayd 8 — Xulosa / Thanks (CUSTOM_11).
    idx=0: TITLE — sarlavha (chapda, yuqorida)
    TEXT_BOX shape — qo'shimcha matn (agar mavjud bo'lsa)
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN

    title_ph = find_placeholder_by_idx(slide, 0)

    if title_ph:
        title_text = conclusion_data.get("title", "Xulosa")
        auto_shrink_text(title_ph, title_text, base_font_pt=32, min_font_pt=16, bold=False)

    # TEXT_BOX shape ga xulosa matnini yozish (agar mavjud bo'lsa)
    for shape in slide.shapes:
        try:
            pf = shape.placeholder_format
            if pf:
                continue
        except Exception:
            pass
        if shape.has_text_frame and shape.shape_type == 17:  # TEXT_BOX
            items = conclusion_data.get("content", [])
            if items:
                from pptx.dml.color import RGBColor
                tf = shape.text_frame
                tf.clear()
                tf.word_wrap = True
                for i, item in enumerate(items[:3]):
                    if i == 0:
                        p = tf.paragraphs[0]
                    else:
                        p = tf.add_paragraph()
                    run = p.add_run()
                    run.text = str(item)
                    run.font.size = Pt(16)
                    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            break


# ═══════════════════════════════════════════════════════════════
# 3-SHABLON ASOSIY FUNKSIYA
# ═══════════════════════════════════════════════════════════════

def generate_template_3_presentation(prs, topic, requested_slide_count, language,
                                      name_surname="", plan=None,
                                      content_data_list=None):
    """
    3-shablon (3.pptx) asosida taqdimot yaratadi.
    1-shablon va 2-shablon bilan bir xil 2-bosqichli tizim.
    """
    logging.info(f"[T3] Taqdimot yaratilmoqda: mavzu='{topic}', slaydlar={requested_slide_count}, til={language}")

    # ── 1. Shablon tuzilmasini qurish ──
    total_content_slides = build_slide_structure_3(prs, requested_slide_count)

    # ── 2. Kontent ma'lumotlarini tayyorlash ──

    # Reja
    if plan is None or not isinstance(plan, dict) or not plan.get("content"):
        plan = {"title": "Reja", "content": ["Kirish", "Asosiy qism", "Xulosa"]}

    # Kontent slaydlari
    if content_data_list is None:
        slide_type_map = {
            0: None,            # slayd 3: bir ustunli
            1: "two_columns",   # slayd 4: ikki ustunli
            2: "three_columns", # slayd 5: uch ustunli
            3: None,            # slayd 6: rasm chapda
            4: None,            # slayd 7: matn chapda
        }
        content_data_list = []
        for i in range(total_content_slides):
            stype = slide_type_map.get(i % 5, None)
            data = generate_slide_content(topic, i + 3, len(prs.slides), language, slide_type=stype)
            if not data:
                if stype == "three_columns":
                    data = {"title": f"{topic} — {i+1}", "col1": "Birinchi ustun", "col2": "Ikkinchi ustun", "col3": "Uchinchi ustun", "image_query": topic}
                elif stype == "two_columns":
                    data = {"title": f"{topic} — {i+1}", "col1": "Birinchi ustun", "col2": "Ikkinchi ustun", "image_query": topic}
                else:
                    data = {"title": f"{topic} — {i+1}", "content": ["Asosiy ma'lumot", "Qo'shimcha tafsilotlar"], "image_query": topic}
            content_data_list.append(data)
    else:
        while len(content_data_list) < total_content_slides:
            content_data_list.append({"title": topic, "content": ["Ma'lumot"], "image_query": topic})

    # Xulosa
    conclusion = generate_slide_content(topic, len(prs.slides), len(prs.slides), language, is_conclusion=True)
    if not conclusion:
        conclusion = {"title": "Xulosa", "content": ["Asosiy xulosalar", "Tavsiyalar"]}

    # ── 3. Slaydlarni to'ldirish ──

    # Slayd 1: Muqova
    fill_t3_slide_1_cover(prs.slides[0], topic, name_surname)

    # Slayd 2: Reja
    fill_t3_slide_2_plan(prs.slides[1], plan)

    # Kontent slaydlar (3-7 takrorlanadi)
    # 3-shablon slayd turlari (0-indexed kontent pozitsiyasi):
    # 0 → slayd 3: ONE_COLUMN (bir ustunli matn)
    # 1 → slayd 4: TWO_COLUMNS (ikki ustunli)
    # 2 → slayd 5: THREE_COLUMNS (uch ustunli)
    # 3 → slayd 6: IMAGE_LEFT (chapda rasm)
    # 4 → slayd 7: QUOTE (chapda matn, o'ngda dekorativ)

    for i in range(total_content_slides):
        slide_index = i + 2
        slide = prs.slides[slide_index]
        data = content_data_list[i]
        image_query = data.get("image_query", topic)
        slide_type = i % 5

        if slide_type == 0:
            fill_t3_slide_3_one_column(slide, data)
        elif slide_type == 1:
            fill_t3_slide_4_two_columns(slide, data)
        elif slide_type == 2:
            fill_t3_slide_5_three_columns(slide, data)
        elif slide_type == 3:
            fill_t3_slide_6_image_left(slide, data, image_query)
        elif slide_type == 4:
            fill_t3_slide_7_quote(slide, data, image_query)

        logging.info(f"  [T3] Slayd {slide_index + 1} to'ldirildi (tur {slide_type}): {data.get('title', '')}")

    # Oxirgi slayd: Xulosa
    fill_t3_slide_8_conclusion(prs.slides[-1], conclusion)

    # ── 4. Faylni xotiraga saqlash ──
    prs_bytes = BytesIO()
    prs.save(prs_bytes)
    prs_bytes.seek(0)

    logging.info(f"[T3] Taqdimot tayyor: {len(prs.slides)} ta slayd")
    return prs_bytes
