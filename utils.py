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
import traceback
from PIL import Image as PILImage

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
)

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


def calc_body_font_pt(total_chars, base_pt=16, min_pt=10, max_pt=20):
    """
    Matn uzunligiga qarab shrift o'lchamini hisoblaydi.
    Matn qisqa bo'lsa kattaroq, uzun bo'lsa kichikroq shrift.
    total_chars: barcha matn belgilarining umumiy soni
    """
    if total_chars <= 150:
        return min(max_pt, base_pt + 4)   # 20pt
    elif total_chars <= 300:
        return min(max_pt, base_pt + 2)   # 18pt
    elif total_chars <= 500:
        return base_pt                    # 16pt
    elif total_chars <= 800:
        return max(min_pt, base_pt - 2)   # 14pt
    elif total_chars <= 1200:
        return max(min_pt, base_pt - 4)   # 12pt
    else:
        return max(min_pt, base_pt - 6)   # 10pt


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


def fetch_image_preview_urls(image_query, count=3):
    """
    Pixabay dan rasm URL larini qaytaradi (yuklab olmaydi).
    Foydalanuvchiga ko'rsatish uchun ishlatiladi.
    Qaytaradi: list of cdn_url yoki []
    """
    import re
    if not PIXABAY_API_KEY:
        return []
    try:
        url = (
            f"https://pixabay.com/api/"
            f"?key={PIXABAY_API_KEY}"
            f"&q={requests.utils.quote(image_query)}"
            f"&image_type=photo&orientation=horizontal"
            f"&per_page={max(count + 2, 5)}&safesearch=true"
        )
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
        results = []
        for hit in hits:
            preview_url = hit.get("previewURL", "")
            if not preview_url:
                continue
            if preview_url.lower().endswith(".jpg"):
                cdn_url = re.sub(r'_\d+\.jpg$', '_640.jpg', preview_url)
            else:
                cdn_url = preview_url
            results.append(cdn_url)
            if len(results) >= count:
                break
        return results
    except Exception as e:
        logging.error(f"fetch_image_preview_urls xatolik ({image_query}): {e}")
        return []


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


def save_user_image_to_tmp(image_bytes):
    """
    Foydalanuvchi yuborgan rasm bytes ni /tmp ga saqlaydi.
    Pillow bilan JPEG ga convert qiladi va sifatini saqlaydi.
    Qaytaradi: lokal fayl yo'li yoki None.
    """
    if not image_bytes:
        return None
    try:
        img_path = f"/tmp/user_slide_img_{random.randint(0, 999999)}.jpg"
        img = PILImage.open(BytesIO(image_bytes))
        # RGBA -> RGB (JPEG RGBA ni qo'llab-quvvatlamaydi)
        if img.mode in ('RGBA', 'P', 'LA'):
            img = img.convert('RGB')
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        img.save(img_path, 'JPEG', quality=92)
        logging.info(f"Foydalanuvchi rasmi saqlandi: {img_path}")
        return img_path
    except Exception as e:
        logging.error(f"Foydalanuvchi rasmini saqlashda xatolik: {e}")
        return None


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
    # Agar image_query fayl yo'li bo'lsa (user_images), to'g'ridan-to'g'ri ishlatish
    if image_query and os.path.isfile(image_query):
        place_image_in_placeholder(slide, 2, image_query)
    else:
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
    # Agar image_query fayl yo'li bo'lsa (user_images), to'g'ridan-to'g'ri ishlatish
    if image_query and os.path.isfile(image_query):
        place_image_in_placeholder(slide, 2, image_query)
    else:
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

# 3-shablon uchun slayd turi xaritasi
SLIDE_TYPE_NAMES_T3 = {
    0: "one_column",      # 3-slayd: bir ustunli matn
    1: "two_columns",     # 4-slayd: 2 ustun
    2: "three_columns",   # 5-slayd: 3 ustun
    3: "image_left",      # 6-slayd: chapda rasm
    4: "quote",           # 7-slayd: chapda matn
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


def generate_all_content(topic, slide_count, language, slide_titles, slide_type_names=None):
    """
    2-BOSQICH: Tasdiqlangan sarlavhalar bo'yicha barcha kontent slaydlar uchun
    matnlarni BITTA GPT so'rovida yaratadi.

    Qaytaradi: list of dicts, har biri bir kontent slayd uchun.
    """
    if slide_type_names is None:
        slide_type_names = SLIDE_TYPE_NAMES
    content_count = len(slide_titles)
    slides_info = []
    for i, title in enumerate(slide_titles):
        stype = slide_type_names.get(i % 5, "image_left")
        if stype == "one_column":
            fmt = f'{{"title": "{title}", "content": ["...", "...", "...", "..."], "image_query": "..."}}'
            desc = "4-6 ta paragraf, har biri 2-3 jumla, matn blokini to'liq to'ldirsin"
        elif stype == "three_columns":
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
        logging.error(f"generate_all_content xatolik: {type(e).__name__}: {e}")
        logging.error(traceback.format_exc())
        return None


# ═══════════════════════════════════════════════════════════════
# ASOSIY FUNKSIYA
# ═══════════════════════════════════════════════════════════════

def generate_template_1_presentation(prs, topic, requested_slide_count, language,
                                       name_surname="", plan=None,
                                       content_data_list=None, user_images=None):
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
    user_img_idx = 0  # foydalanuvchi rasmlari indeksi
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
            # Foydalanuvchi rasmi bormi?
            if user_images and user_img_idx < len(user_images):
                img_path = save_user_image_to_tmp(user_images[user_img_idx])
                user_img_idx += 1
                fill_slide_5_image_left(slide, data, img_path if img_path else image_query)
            else:
                fill_slide_5_image_left(slide, data, image_query)
        elif slide_type == 3:
            fill_slide_6_quote(slide, data)
        elif slide_type == 4:
            # Foydalanuvchi rasmi bormi?
            if user_images and user_img_idx < len(user_images):
                img_path = save_user_image_to_tmp(user_images[user_img_idx])
                user_img_idx += 1
                fill_slide_7_image_right(slide, data, img_path if img_path else image_query)
            else:
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
    from pptx.util import Cm
    # Agar image_query fayl yo'li bo'lsa (user_images), to'g'ridan-to'g'ri ishlatish
    if image_query and os.path.isfile(image_query):
        final_img_path = image_query
    else:
        query = image_query or content_data.get("image_query", content_data.get("title", "nature"))
        final_img_path = fetch_image(query)
    if final_img_path:
        try:
            left = Cm(14.27)
            top  = Cm(1.97)
            width = Cm(9.44)
            height = Cm(10.35)
            slide.shapes.add_picture(final_img_path, left, top, width, height)
            if os.path.isfile(final_img_path):
                os.remove(final_img_path)
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
                                      content_data_list=None, user_images=None):
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

    user_img_idx = 0
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
            if user_images and user_img_idx < len(user_images):
                img_path = save_user_image_to_tmp(user_images[user_img_idx])
                user_img_idx += 1
                fill_t2_slide_7_image(slide, data, img_path if img_path else image_query)
            else:
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
        # Matn uzunligiga qarab shrift o'lchamini hisoblash
        total_chars = sum(len(str(i)) for i in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=16, min_pt=10, max_pt=20)

        tf = body_ph.text_frame
        tf.clear()
        tf.word_wrap = True

        for idx_p, item in enumerate(items):
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
        font_pt = calc_body_font_pt(len(text), base_pt=15, min_pt=10, max_pt=18)
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
        font_pt = calc_body_font_pt(len(text), base_pt=13, min_pt=9, max_pt=16)
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

        total_chars = sum(len(str(i)) for i in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=17, min_pt=12, max_pt=21)

        for idx_p, item in enumerate(items):
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
    if image_query and os.path.isfile(image_query):
        place_image_in_placeholder(slide, 2, image_query)
    else:
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

        total_chars = sum(len(str(i)) for i in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=17, min_pt=12, max_pt=21)

        for idx_p, item in enumerate(items):
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
    from pptx.util import Inches
    if image_query and os.path.isfile(image_query):
        final_img_path = image_query
    else:
        query = image_query or content_data.get("image_query", content_data.get("title", "technology"))
        final_img_path = fetch_image(query)
    if final_img_path:
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
        slide.shapes.add_picture(final_img_path, left, top, width, height)
        if os.path.isfile(final_img_path):
            os.remove(final_img_path)


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
                total_chars = sum(len(str(it)) for it in items)
                font_pt = calc_body_font_pt(total_chars, base_pt=16, min_pt=11, max_pt=20)
                for i, item in enumerate(items):
                    if i == 0:
                        p = tf.paragraphs[0]
                    else:
                        p = tf.add_paragraph()
                    run = p.add_run()
                    run.text = str(item)
                    run.font.size = Pt(font_pt)
                    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            break


# ═══════════════════════════════════════════════════════════════
# 3-SHABLON ASOSIY FUNKSIYA
# ═══════════════════════════════════════════════════════════════

def generate_template_3_presentation(prs, topic, requested_slide_count, language,
                                      name_surname="", plan=None,
                                      content_data_list=None, user_images=None):
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

    user_img_idx = 0
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
            if user_images and user_img_idx < len(user_images):
                img_path = save_user_image_to_tmp(user_images[user_img_idx])
                user_img_idx += 1
                fill_t3_slide_6_image_left(slide, data, img_path if img_path else image_query)
            else:
                fill_t3_slide_6_image_left(slide, data, image_query)
        elif slide_type == 4:
            if user_images and user_img_idx < len(user_images):
                img_path = save_user_image_to_tmp(user_images[user_img_idx])
                user_img_idx += 1
                fill_t3_slide_7_quote(slide, data, img_path if img_path else image_query)
            else:
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


# ═══════════════════════════════════════════════════════════════
# 4-SHABLON YORDAMCHI FUNKSIYALAR
# ═══════════════════════════════════════════════════════════════

# 4-shablon uchun slayd turi xaritasi
SLIDE_TYPE_NAMES_T4 = {
    0: "one_column",       # 3-slayd: bir ustunli matn
    1: "three_columns",    # 4-slayd: uch ustunli
    2: "two_columns",      # 5-slayd: ikki ustunli
    3: "image_left",       # 6-slayd: chapda matn, o'ngda rasm
    4: "three_textboxes",  # 7-slayd: uch TEXT_BOX
}

# 4-shablon kontent slayd indekslari (template da 3-7 slaydlar)
CONTENT_SLIDE_TEMPLATE_INDICES_4 = [2, 3, 4, 5, 6]


def build_slide_structure_4(prs, requested_content_count):
    """
    4-shablon uchun slayd tuzilmasini quradi.
    3-shablon kabi duplicate_slide va move_slide ishlatadi.
    1-slayd: muqova, 2-slayd: reja, 3-7: kontent (5 tur), 8: xulosa
    """
    full_repeats = max(1, round(requested_content_count / 5))
    total_content_slides = full_repeats * 5

    logging.info(f"[T4] Kontent slaydlari: {requested_content_count} so'raldi, "
                 f"{full_repeats} marta takrorlanadi ({total_content_slides} ta kontent slayd)")

    extra_sets_needed = full_repeats - 1

    for set_num in range(extra_sets_needed):
        for slide_template_idx in CONTENT_SLIDE_TEMPLATE_INDICES_4:
            duplicate_slide(prs, slide_template_idx)
        logging.info(f"  [T4] {set_num + 2}-to'plam qo'shildi. Jami slaydlar: {len(prs.slides)}")

    # Xulosa slaydini (index 7) oxiriga ko'chirish
    conclusion_current_index = 7
    last_index = len(prs.slides) - 1
    move_slide(prs, conclusion_current_index, last_index)

    logging.info(f"[T4] Yakuniy tuzilma: {len(prs.slides)} ta slayd")
    return total_content_slides


def fill_t4_slide_1_cover(slide, topic, name_surname):
    """
    4-Shablon Slayd 1 — Muqova (TITLE layout).
    idx=0 CENTER_TITLE: katta sarlavha (chapda)
    idx=1 SUBTITLE: ism-familiya (pastda)
    """
    title_ph = find_placeholder_by_idx(slide, 0)
    sub_ph   = find_placeholder_by_idx(slide, 1)

    if title_ph:
        auto_shrink_text(title_ph, topic.upper(), base_font_pt=54, min_font_pt=28, bold=True)

    if sub_ph:
        tf = sub_ph.text_frame
        tf.clear()
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = name_surname or ""
        run.font.size = Pt(16)


def fill_t4_slide_2_plan(slide, plan_data):
    """
    4-Shablon Slayd 2 — Reja (BLANK_1_1_1_1_1_1 layout).
    idx=0 TITLE: "REJA" — o'zgartirmaslik
    idx=1..4 SUBTITLE: reja bandlari (4 ta)
    """
    from pptx.oxml.ns import qn
    from lxml import etree

    items = plan_data.get("content", [])

    for i in range(1, 5):
        ph = find_placeholder_by_idx(slide, i)
        if ph and (i - 1) < len(items):
            text = str(items[i - 1])
            # Raqam prefiksini olib tashlash (agar bor bo'lsa)
            import re
            text = re.sub(r'^\d+[\.\)]\s*', '', text).strip()
            tf = ph.text_frame
            txBody = tf._txBody
            for p_el in txBody.findall(qn('a:p')):
                txBody.remove(p_el)
            new_p = etree.SubElement(txBody, qn('a:p'))
            pPr = etree.SubElement(new_p, qn('a:pPr'))
            etree.SubElement(pPr, qn('a:buNone'))
            pPr.set('marL', '0')
            pPr.set('indent', '0')
            pPr.set('algn', 'l')
            new_r = etree.SubElement(new_p, qn('a:r'))
            rPr = etree.SubElement(new_r, qn('a:rPr'))
            rPr.set('lang', 'uz-UZ')
            rPr.set('dirty', '0')
            rPr.set('sz', '1600')
            t_el = etree.SubElement(new_r, qn('a:t'))
            t_el.text = text
            tf.word_wrap = True
        elif ph:
            # Bo'sh qoldirilsin
            tf = ph.text_frame
            txBody = tf._txBody
            for p_el in txBody.findall(qn('a:p')):
                txBody.remove(p_el)
            etree.SubElement(txBody, qn('a:p'))


def fill_t4_slide_3_one_column(slide, content_data):
    """
    4-Shablon Slayd 3 — Bir ustunli matn (CUSTOM_4 layout).
    idx=0 TITLE: sarlavha (chapda)
    idx=1 SUBTITLE: asosiy matn bloki (chapda)
    """
    from pptx.enum.text import MSO_ANCHOR
    from pptx.oxml.ns import qn
    from lxml import etree

    title_ph = find_placeholder_by_idx(slide, 0)
    body_ph  = find_placeholder_by_idx(slide, 1)

    if title_ph:
        auto_shrink_text(title_ph, content_data.get("title", ""), base_font_pt=24, min_font_pt=14, bold=True)

    if body_ph:
        items = content_data.get("content", [])
        total_chars = sum(len(str(i)) for i in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=15, min_pt=10, max_pt=18)

        tf = body_ph.text_frame
        tf.clear()
        tf.word_wrap = True

        for idx_p, item in enumerate(items):
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


def fill_t4_slide_4_three_columns(slide, content_data):
    """
    4-Shablon Slayd 4 — Uch ustunli (CUSTOM_6_1_1 layout).
    idx=0 TITLE: sarlavha
    idx=1 SUBTITLE: chap ustun
    idx=2 SUBTITLE: o'rta ustun
    idx=3 SUBTITLE: o'ng ustun
    """
    from pptx.oxml.ns import qn
    from lxml import etree

    title_ph = find_placeholder_by_idx(slide, 0)
    col1_ph  = find_placeholder_by_idx(slide, 1)
    col2_ph  = find_placeholder_by_idx(slide, 2)
    col3_ph  = find_placeholder_by_idx(slide, 3)

    if title_ph:
        auto_shrink_text(title_ph, content_data.get("title", ""), base_font_pt=24, min_font_pt=14, bold=True)

    col1_text = content_data.get("col1", "")
    col2_text = content_data.get("col2", "")
    col3_text = content_data.get("col3", "")
    if not col1_text:
        items = content_data.get("content", ["", "", ""])
        col1_text = items[0] if len(items) > 0 else ""
        col2_text = items[1] if len(items) > 1 else ""
        col3_text = items[2] if len(items) > 2 else ""
    if not col3_text and col2_text:
        words = col2_text.split('. ')
        half = len(words) // 2
        if half > 0:
            col3_text = '. '.join(words[half:]).strip()
            col2_text = '. '.join(words[:half]).strip()

    def write_col(ph, text):
        if not ph or not text:
            return
        tf = ph.text_frame
        txBody = tf._txBody
        for p_el in txBody.findall(qn('a:p')):
            txBody.remove(p_el)
        new_p = etree.SubElement(txBody, qn('a:p'))
        pPr = etree.SubElement(new_p, qn('a:pPr'))
        etree.SubElement(pPr, qn('a:buNone'))
        pPr.set('marL', '0')
        pPr.set('indent', '0')
        pPr.set('algn', 'l')
        new_r = etree.SubElement(new_p, qn('a:r'))
        rPr = etree.SubElement(new_r, qn('a:rPr'))
        rPr.set('lang', 'uz-UZ')
        rPr.set('dirty', '0')
        font_pt = calc_body_font_pt(len(text), base_pt=13, min_pt=9, max_pt=16)
        rPr.set('sz', str(font_pt * 100))
        t_el = etree.SubElement(new_r, qn('a:t'))
        t_el.text = text
        tf.word_wrap = True

    write_col(col1_ph, col1_text)
    write_col(col2_ph, col2_text)
    write_col(col3_ph, col3_text)


def fill_t4_slide_5_two_columns(slide, content_data):
    """
    4-Shablon Slayd 5 — Ikki ustunli (TITLE_AND_TWO_COLUMNS_1_1 layout).
    idx=0 TITLE: sarlavha
    idx=1 SUBTITLE: o'ng ustun
    idx=2 SUBTITLE: chap ustun
    """
    from pptx.oxml.ns import qn
    from lxml import etree

    title_ph  = find_placeholder_by_idx(slide, 0)
    right_ph  = find_placeholder_by_idx(slide, 1)
    left_ph   = find_placeholder_by_idx(slide, 2)

    if title_ph:
        auto_shrink_text(title_ph, content_data.get("title", ""), base_font_pt=24, min_font_pt=14, bold=True)

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
        new_p = etree.SubElement(txBody, qn('a:p'))
        pPr = etree.SubElement(new_p, qn('a:pPr'))
        etree.SubElement(pPr, qn('a:buNone'))
        pPr.set('marL', '0')
        pPr.set('indent', '0')
        pPr.set('algn', 'l')
        new_r = etree.SubElement(new_p, qn('a:r'))
        rPr = etree.SubElement(new_r, qn('a:rPr'))
        rPr.set('lang', 'uz-UZ')
        rPr.set('dirty', '0')
        font_pt = calc_body_font_pt(len(text), base_pt=15, min_pt=10, max_pt=18)
        rPr.set('sz', str(font_pt * 100))
        t_el = etree.SubElement(new_r, qn('a:t'))
        t_el.text = text
        tf.word_wrap = True

    write_col(left_ph, col1_text)
    write_col(right_ph, col2_text)


def fill_t4_slide_6_image_left(slide, content_data, image_query):
    """
    4-Shablon Slayd 6 — Chapda matn, o'ngda rasm (CUSTOM_4 layout).
    idx=0 TITLE: sarlavha
    idx=1 SUBTITLE: matn bloki (chapda)
    O'ngda katta gradient shape ustiga rasm qo'yiladi: (5.0",1.53") 5.5"x2.47"
    """
    from pptx.enum.text import MSO_ANCHOR
    from pptx.oxml.ns import qn
    from lxml import etree
    from pptx.util import Inches

    title_ph = find_placeholder_by_idx(slide, 0)
    body_ph  = find_placeholder_by_idx(slide, 1)

    if title_ph:
        auto_shrink_text(title_ph, content_data.get("title", ""), base_font_pt=24, min_font_pt=14, bold=True)

    if body_ph:
        items = content_data.get("content", [])
        total_chars = sum(len(str(i)) for i in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=15, min_pt=10, max_pt=18)

        tf = body_ph.text_frame
        tf.clear()
        tf.word_wrap = True

        for idx_p, item in enumerate(items):
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

    # O'ngdagi gradient shape ustiga rasm qo'yish
    if image_query and os.path.isfile(image_query):
        final_img_path = image_query
    else:
        query = image_query or content_data.get("image_query", content_data.get("title", "technology"))
        final_img_path = fetch_image(query)
    if final_img_path:
        left   = Inches(5.0)
        top    = Inches(1.53)
        width  = Inches(4.77)
        height = Inches(2.47)
        slide.shapes.add_picture(final_img_path, left, top, width, height)
        if os.path.isfile(final_img_path):
            os.remove(final_img_path)


def fill_t4_slide_7_three_textboxes(slide, content_data):
    """
    4-Shablon Slayd 7 — Uch TEXT_BOX (TITLE_ONLY layout).
    idx=0 TITLE: sarlavha
    TEXT_BOX 1: (0.79",1.44") 3.8"x1.36" — chap yuqori
    TEXT_BOX 2: (5.41",2.63") 3.8"x1.36" — o'ng o'rta
    TEXT_BOX 3: (0.79",4.0") 3.8"x1.2" — chap pastki
    """
    from pptx.util import Pt

    title_ph = find_placeholder_by_idx(slide, 0)

    if title_ph:
        auto_shrink_text(title_ph, content_data.get("title", ""), base_font_pt=24, min_font_pt=14, bold=True)

    # 3 ta TEXT_BOX topish (shape_type == 17)
    textboxes = []
    for shape in slide.shapes:
        if shape.shape_type == 17 and shape.has_text_frame:  # TEXT_BOX
            textboxes.append(shape)

    items = content_data.get("content", [])
    # col1/col2/col3 dan ham olish
    if not items:
        items = [
            content_data.get("col1", ""),
            content_data.get("col2", ""),
            content_data.get("col3", ""),
        ]
    items = [str(i) for i in items if i]

    for i, tb in enumerate(textboxes[:3]):
        if i < len(items):
            text = items[i]
            font_pt = calc_body_font_pt(len(text), base_pt=14, min_pt=9, max_pt=16)
            tf = tb.text_frame
            tf.clear()
            tf.word_wrap = True
            p = tf.paragraphs[0]
            run = p.add_run()
            run.text = text
            run.font.size = Pt(font_pt)


def fill_t4_slide_8_conclusion(slide, conclusion_data):
    """
    4-Shablon Slayd 8 — Xulosa (TITLE_ONLY layout).
    idx=0 TITLE: sarlavha ("Thanks!" o'rniga xulosa sarlavhasi)
    idx=4294967295 BODY: katta matn maydoni
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN

    title_ph = find_placeholder_by_idx(slide, 0)
    if title_ph:
        title_text = conclusion_data.get("title", "Xulosa")
        auto_shrink_text(title_ph, title_text, base_font_pt=32, min_font_pt=16, bold=True)

    # BODY placeholder (idx=4294967295) ga xulosa matnini yozish
    for shape in slide.shapes:
        try:
            pf = shape.placeholder_format
            if pf and pf.idx == 4294967295:
                items = conclusion_data.get("content", [])
                if items:
                    tf = shape.text_frame
                    tf.clear()
                    tf.word_wrap = True
                    total_chars = sum(len(str(it)) for it in items)
                    font_pt = calc_body_font_pt(total_chars, base_pt=16, min_pt=11, max_pt=20)
                    for i, item in enumerate(items):
                        if i == 0:
                            p = tf.paragraphs[0]
                        else:
                            p = tf.add_paragraph()
                        run = p.add_run()
                        run.text = str(item)
                        run.font.size = Pt(font_pt)
                break
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
# 4-SHABLON ASOSIY FUNKSIYA
# ═══════════════════════════════════════════════════════════════

def generate_template_4_presentation(prs, topic, requested_slide_count, language,
                                      name_surname="", plan=None,
                                      content_data_list=None, user_images=None):
    """
    4-shablon (4.pptx) asosida taqdimot yaratadi.
    """
    logging.info(f"[T4] Taqdimot yaratilmoqda: mavzu='{topic}', slaydlar={requested_slide_count}, til={language}")

    # ── 1. Shablon tuzilmasini qurish ──
    total_content_slides = build_slide_structure_4(prs, requested_slide_count)

    # ── 2. Kontent ma'lumotlarini tayyorlash ──
    if plan is None or not isinstance(plan, dict) or not plan.get("content"):
        plan = {"title": "Reja", "content": ["Kirish", "Asosiy qism", "Xulosa"]}

    if content_data_list is None:
        content_data_list = []
        for i in range(total_content_slides):
            stype_name = SLIDE_TYPE_NAMES_T4.get(i % 5, "one_column")
            if stype_name == "three_columns":
                stype = "three_columns"
            elif stype_name == "two_columns":
                stype = "two_columns"
            elif stype_name == "image_left":
                stype = "image_left"
            elif stype_name == "three_textboxes":
                stype = "three_columns"  # GPT uchun three_columns formatini ishlatamiz
            else:
                stype = None
            data = generate_slide_content(topic, i + 3, len(prs.slides), language, slide_type=stype)
            if not data:
                data = {"title": f"{topic} — {i+1}", "content": ["Asosiy ma'lumot"], "image_query": topic}
            content_data_list.append(data)
    else:
        while len(content_data_list) < total_content_slides:
            content_data_list.append({"title": topic, "content": ["Ma'lumot"], "image_query": topic})

    conclusion = generate_slide_content(topic, len(prs.slides), len(prs.slides), language, is_conclusion=True)
    if not conclusion:
        conclusion = {"title": "Xulosa", "content": ["Asosiy xulosalar", "Tavsiyalar"]}

    # ── 3. Slaydlarni to'ldirish ──
    fill_t4_slide_1_cover(prs.slides[0], topic, name_surname)
    fill_t4_slide_2_plan(prs.slides[1], plan)

    user_img_idx = 0
    for i in range(total_content_slides):
        slide_index = i + 2
        slide = prs.slides[slide_index]
        data = content_data_list[i]
        image_query = data.get("image_query", topic)
        slide_type = i % 5

        if slide_type == 0:
            fill_t4_slide_3_one_column(slide, data)
        elif slide_type == 1:
            fill_t4_slide_4_three_columns(slide, data)
        elif slide_type == 2:
            fill_t4_slide_5_two_columns(slide, data)
        elif slide_type == 3:
            if user_images and user_img_idx < len(user_images):
                img_path = save_user_image_to_tmp(user_images[user_img_idx])
                user_img_idx += 1
                fill_t4_slide_6_image_left(slide, data, img_path if img_path else image_query)
            else:
                fill_t4_slide_6_image_left(slide, data, image_query)
        elif slide_type == 4:
            fill_t4_slide_7_three_textboxes(slide, data)

        logging.info(f"  [T4] Slayd {slide_index + 1} to'ldirildi (tur {slide_type}): {data.get('title', '')}")

    fill_t4_slide_8_conclusion(prs.slides[-1], conclusion)

    # ── 4. Faylni xotiraga saqlash ──
    prs_bytes = BytesIO()
    prs.save(prs_bytes)
    prs_bytes.seek(0)

    logging.info(f"[T4] Taqdimot tayyor: {len(prs.slides)} ta slayd")
    return prs_bytes


# ═══════════════════════════════════════════════════════════════
# 5-SHABLON YORDAMCHI FUNKSIYALAR (YANGI 5.pptx ga mos)
# ═══════════════════════════════════════════════════════════════
# 5-shablon uchun slayd turi xaritasi (yangi tuzilma)
SLIDE_TYPE_NAMES_T5 = {
    0: "image_left",     # 3-slayd: rasm o'ngda, matn chapda
    1: "two_columns",    # 4-slayd: ikki ustunli (idx=2, idx=4)
    2: "two_staggered",  # 5-slayd: ikki offset blok
    3: "image_left",     # 6-slayd: rasm o'ngda, kichik sarlavha
    4: "two_columns",    # 7-slayd: ikki kvadrat blok
}
# 5-shablon kontent slayd indekslari (template da 3-7 slaydlar = index 2-6)
CONTENT_SLIDE_TEMPLATE_INDICES_5 = [2, 3, 4, 5, 6]


def build_slide_structure_5(prs, requested_content_count):
    """
    5-shablon uchun slayd tuzilmasini quradi.
    duplicate_slide va move_slide ishlatadi.
    """
    full_repeats = max(1, round(requested_content_count / 5))
    total_content_slides = full_repeats * 5
    logging.info(f"[T5] Kontent slaydlari: {requested_content_count} so'raldi, "
                 f"{full_repeats} marta takrorlanadi ({total_content_slides} ta kontent slayd)")
    extra_sets_needed = full_repeats - 1
    for set_num in range(extra_sets_needed):
        for slide_template_idx in CONTENT_SLIDE_TEMPLATE_INDICES_5:
            duplicate_slide(prs, slide_template_idx)
        logging.info(f"  [T5] {set_num + 2}-to'plam qo'shildi. Jami slaydlar: {len(prs.slides)}")
    # Xulosa slaydini (index 7) oxiriga ko'chirish
    conclusion_current_index = 7
    last_index = len(prs.slides) - 1
    move_slide(prs, conclusion_current_index, last_index)
    logging.info(f"[T5] Yakuniy tuzilma: {len(prs.slides)} ta slayd")
    return total_content_slides


def fill_t5_slide_1_cover(slide, topic, name_surname):
    """
    5-Shablon Slayd 1 — Muqova.
    idx=0: Katta sarlavha (o'ngda) — KATTA HARFDA
    idx=1: Subtitle — ism-familiya
    """
    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        if not hasattr(shape, 'placeholder_format') or not shape.placeholder_format:
            continue
        idx = shape.placeholder_format.idx
        tf = shape.text_frame
        tf.clear()
        if idx == 0:
            p = tf.paragraphs[0]
            run = p.add_run()
            run.text = topic.upper()
        elif idx == 1:
            p = tf.paragraphs[0]
            run = p.add_run()
            run.text = name_surname


def fill_t5_slide_2_plan(slide, plan_data):
    """
    5-Shablon Slayd 2 — Reja.
    idx=0: 'REJA' — o'zgartirmaslik
    idx=1: Reja bandlari ro'yxati — chapga tekislangan, raqamli, bulletsiz
    """
    from lxml import etree
    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    titles = plan_data.get("content", plan_data.get("titles", []))
    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        if not hasattr(shape, 'placeholder_format') or not shape.placeholder_format:
            continue
        idx = shape.placeholder_format.idx
        if idx == 0:
            continue  # "REJA" — o'zgartirmaslik
        if idx == 1:
            tf = shape.text_frame
            tf.word_wrap = True
            total_chars = sum(len(t) for t in titles)
            font_pt = calc_body_font_pt(total_chars, base_pt=18, min_pt=12, max_pt=22)
            # Remove all existing paragraphs from txBody
            txBody = tf._txBody
            for p_elem in txBody.findall(f'{{{ns_a}}}p'):
                txBody.remove(p_elem)
            # Add clean numbered paragraphs with buNone (no bullet)
            for title in titles:
                # title already has "1. " prefix from generate_plan_with_titles
                safe_title = title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                p_xml = (
                    f'<a:p xmlns:a="{ns_a}">' 
                    f'<a:pPr algn="l"><a:buNone/></a:pPr>'
                    f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0">'
                    f'<a:solidFill><a:srgbClr val="1A1A2E"/></a:solidFill></a:rPr>'
                    f'<a:t>{safe_title}</a:t></a:r></a:p>'
                )
                p_elem = etree.fromstring(p_xml)
                txBody.append(p_elem)


def fill_t5_slide_3_image_right(slide, content_data, image_query):
    """
    5-Shablon Slayd 3 — Rasm o'ngda, matn chapda.
    idx=0: Sarlavha (yuqorida)
    idx=1: Rasm (o'ngda, Pixabay)
    idx=2: Matn (chapda)
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
    title = content_data.get("title", "")
    items = content_data.get("content", [])
    if not items:
        items = content_data.get("col1", []) + content_data.get("col2", [])

    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        if not hasattr(shape, 'placeholder_format') or not shape.placeholder_format:
            continue
        idx = shape.placeholder_format.idx
        tf = shape.text_frame
        tf.clear()
        if idx == 0:
            p = tf.paragraphs[0]
            run = p.add_run()
            run.text = title
        elif idx == 2:
            from lxml import etree
            ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
            total_chars = sum(len(s) for s in items)
            font_pt = calc_body_font_pt(total_chars, base_pt=18, min_pt=12, max_pt=24)
            txBody = tf._txBody
            for p_elem in txBody.findall(f'{{{ns_a}}}p'):
                txBody.remove(p_elem)
            for item in items:
                safe_item = item.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                p_xml = (
                    f'<a:p xmlns:a="{ns_a}">'
                    f'<a:pPr algn="l"><a:buNone/></a:pPr>'
                    f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0">'
                    f'<a:solidFill><a:srgbClr val="1A1A2E"/></a:solidFill></a:rPr>'
                    f'<a:t>{safe_item}</a:t></a:r></a:p>'
                )
                p_elem = etree.fromstring(p_xml)
                txBody.append(p_elem)
            tf.word_wrap = True

    # Rasm qo'yish (idx=1)
    if image_query and os.path.isfile(image_query):
        place_image_in_placeholder(slide, 1, image_query)
    else:
        img_path = fetch_image(image_query)
        if img_path:
            place_image_in_placeholder(slide, 1, img_path)


def fill_t5_slide_4_two_columns(slide, content_data):
    """
    5-Shablon Slayd 4 — Ikki ustunli.
    idx=0: Sarlavha
    idx=2: Chap ustun
    idx=4: O'ng ustun
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
    title = content_data.get("title", "")
    col1 = content_data.get("col1", [])
    col2 = content_data.get("col2", [])
    # string bo'lsa, jumlalarga bo'lib list ga aylantir
    if isinstance(col1, str):
        col1 = [s.strip() for s in col1.replace('. ', '.\n').split('\n') if s.strip()]
    if isinstance(col2, str):
        col2 = [s.strip() for s in col2.replace('. ', '.\n').split('\n') if s.strip()]
    if not col1 and not col2:
        items = content_data.get("content", [])
        mid = len(items) // 2
        col1 = items[:mid]
        col2 = items[mid:]
    def write_col(tf, items, align):
        from lxml import etree
        ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
        align_val = 'r' if align == PP_ALIGN.RIGHT else 'l'
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=16, min_pt=12, max_pt=20)
        # Remove all existing paragraphs from txBody
        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)
        # Add clean paragraphs with buNone (no bullet)
        for item in items:
            safe_item = item.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="{align_val}"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0">'
                f'<a:solidFill><a:srgbClr val="1A1A2E"/></a:solidFill></a:rPr>'
                f'<a:t>{safe_item}</a:t></a:r></a:p>'
            )
            p_elem = etree.fromstring(p_xml)
            txBody.append(p_elem)
        tf.word_wrap = True
    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        if not hasattr(shape, 'placeholder_format') or not shape.placeholder_format:
            continue
        idx = shape.placeholder_format.idx
        tf = shape.text_frame
        if idx == 0:
            tf.clear()
            p = tf.paragraphs[0]
            run = p.add_run()
            run.text = title
        elif idx == 2:
            write_col(tf, col1, PP_ALIGN.RIGHT)
        elif idx == 4:
            write_col(tf, col2, PP_ALIGN.LEFT)
def fill_t5_slide_5_two_staggered(slide, content_data):
    """
    5-Shablon Slayd 5 — Ikki offset blok.
    idx=0: Sarlavha
    idx=1: Yuqori blok (chapda)
    idx=2: Pastki blok (o'ngda offset)
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
    title = content_data.get("title", "")
    items = content_data.get("content", [])
    if not items:
        items = content_data.get("col1", []) + content_data.get("col2", [])
    mid = len(items) // 2 if len(items) > 1 else 1
    block1 = items[:mid]
    block2 = items[mid:]

    def write_block(tf, items):
        from lxml import etree
        ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=18, min_pt=12, max_pt=24)
        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)
        for item in items:
            safe_item = item.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0">'
                f'<a:solidFill><a:srgbClr val="1A1A2E"/></a:solidFill></a:rPr>'
                f'<a:t>{safe_item}</a:t></a:r></a:p>'
            )
            p_elem = etree.fromstring(p_xml)
            txBody.append(p_elem)
        tf.word_wrap = True
    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        if not hasattr(shape, 'placeholder_format') or not shape.placeholder_format:
            continue
        idx = shape.placeholder_format.idx
        tf = shape.text_frame
        if idx == 0:
            tf.clear()
            p = tf.paragraphs[0]
            run = p.add_run()
            run.text = title
        elif idx == 1:
            write_block(tf, block1)
        elif idx == 2:
            write_block(tf, block2)


def fill_t5_slide_6_image_right2(slide, content_data, image_query):
    """
    5-Shablon Slayd 6 — Rasm o'ngda, kichik sarlavha chapda.
    idx=0: Sarlavha (chapda, kichik)
    idx=1: Rasm (o'ngda, Pixabay)
    idx=2: Matn (chapda)
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
    title = content_data.get("title", "")
    items = content_data.get("content", [])
    if not items:
        items = content_data.get("col1", []) + content_data.get("col2", [])

    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        if not hasattr(shape, 'placeholder_format') or not shape.placeholder_format:
            continue
        idx = shape.placeholder_format.idx
        tf = shape.text_frame
        tf.clear()
        if idx == 0:
            p = tf.paragraphs[0]
            run = p.add_run()
            run.text = title
        elif idx == 2:
            tf.word_wrap = True
            total_chars = sum(len(s) for s in items)
            font_pt = calc_body_font_pt(total_chars, base_pt=17, min_pt=12, max_pt=21)
            for j, item in enumerate(items):
                p = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
                p.alignment = PP_ALIGN.LEFT
                run = p.add_run()
                run.text = item
                run.font.size = Pt(font_pt)
                run.font.color.rgb = RGBColor(0x1A, 0x1A, 0x2E)

    # Rasm qo'yish (idx=1)
    if image_query and os.path.isfile(image_query):
        place_image_in_placeholder(slide, 1, image_query)
    else:
        img_path = fetch_image(image_query)
        if img_path:
            place_image_in_placeholder(slide, 1, img_path)


def fill_t5_slide_7_two_blocks(slide, content_data):
    """
    5-Shablon Slayd 7 — Ikki kvadrat blok.
    idx=0: Sarlavha
    idx=1: Chap blok
    idx=2: O'ng blok
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
    title = content_data.get("title", "")
    col1 = content_data.get("col1", [])
    col2 = content_data.get("col2", [])
    # string bo'lsa, jumlalarga bo'lib list ga aylantir
    if isinstance(col1, str):
        col1 = [s.strip() for s in col1.replace('. ', '.\n').split('\n') if s.strip()]
    if isinstance(col2, str):
        col2 = [s.strip() for s in col2.replace('. ', '.\n').split('\n') if s.strip()]
    if not col1 and not col2:
        items = content_data.get("content", [])
        mid = len(items) // 2
        col1 = items[:mid]
        col2 = items[mid:]
    def write_block(tf, items):
        from lxml import etree
        ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=15, min_pt=11, max_pt=18)
        # Remove all existing paragraphs from txBody
        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)
        # Add clean paragraphs with buNone (no bullet)
        for item in items:
            safe_item = item.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0">'
                f'<a:solidFill><a:srgbClr val="1A1A2E"/></a:solidFill></a:rPr>'
                f'<a:t>{safe_item}</a:t></a:r></a:p>'
            )
            p_elem = etree.fromstring(p_xml)
            txBody.append(p_elem)
        tf.word_wrap = True
    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        if not hasattr(shape, 'placeholder_format') or not shape.placeholder_format:
            continue
        idx = shape.placeholder_format.idx
        tf = shape.text_frame
        if idx == 0:
            tf.clear()
            p = tf.paragraphs[0]
            run = p.add_run()
            run.text = title
        elif idx == 1:
            write_block(tf, col1)
        elif idx == 2:
            write_block(tf, col2)
def fill_t5_slide_8_conclusion(slide, conclusion_data):
    """
    5-Shablon Slayd 8 — Xulosa.
    idx=0: 'THANKS!' — o'zgartirmaslik
    idx=1: Xulosa matni
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
    items = conclusion_data.get("content", [])
    if not items:
        items = conclusion_data.get("col1", []) + conclusion_data.get("col2", [])

    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        if not hasattr(shape, 'placeholder_format') or not shape.placeholder_format:
            continue
        idx = shape.placeholder_format.idx
        if idx == 0:
            tf = shape.text_frame
            tf.clear()
            p = tf.paragraphs[0]
            run = p.add_run()
            run.text = "XULOSA"
        if idx == 1:
            tf = shape.text_frame
            tf.clear()
            tf.word_wrap = True
            total_chars = sum(len(s) for s in items)
            font_pt = calc_body_font_pt(total_chars, base_pt=16, min_pt=11, max_pt=20)
            for j, item in enumerate(items):
                p = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
                p.alignment = PP_ALIGN.LEFT
                run = p.add_run()
                run.text = item
                run.font.size = Pt(font_pt)
                run.font.color.rgb = RGBColor(0x1A, 0x1A, 0x2E)


def generate_template_5_presentation(prs, topic, requested_slide_count, language,
                                      name_surname, plan, content_data_list, user_images=None):
    """
    5-shablon asosida to'liq prezentatsiya yaratadi.
    """
    import io
    total_content_slides = build_slide_structure_5(prs, requested_slide_count)
    plan_dict = plan if isinstance(plan, dict) else {}

    # Slayd 1 — Muqova
    fill_t5_slide_1_cover(prs.slides[0], topic, name_surname)

    # Slayd 2 — Reja
    fill_t5_slide_2_plan(prs.slides[1], plan_dict)

    # Kontent slaydlari (3-dan boshlab)
    user_img_idx = 0
    for i in range(total_content_slides):
        slide_index = i + 2
        if slide_index >= len(prs.slides) - 1:
            break
        slide = prs.slides[slide_index]
        data = content_data_list[i] if i < len(content_data_list) else {}
        image_query = data.get("image_query", topic)
        slide_type = i % 5

        if slide_type == 0:
            if user_images and user_img_idx < len(user_images):
                img_path = save_user_image_to_tmp(user_images[user_img_idx])
                user_img_idx += 1
                fill_t5_slide_3_image_right(slide, data, img_path if img_path else image_query)
            else:
                fill_t5_slide_3_image_right(slide, data, image_query)
        elif slide_type == 1:
            fill_t5_slide_4_two_columns(slide, data)
        elif slide_type == 2:
            fill_t5_slide_5_two_staggered(slide, data)
        elif slide_type == 3:
            if user_images and user_img_idx < len(user_images):
                img_path = save_user_image_to_tmp(user_images[user_img_idx])
                user_img_idx += 1
                fill_t5_slide_6_image_right2(slide, data, img_path if img_path else image_query)
            else:
                fill_t5_slide_6_image_right2(slide, data, image_query)
        elif slide_type == 4:
            fill_t5_slide_7_two_blocks(slide, data)
        logging.info(f"  [T5] Slayd {slide_index + 1} to'ldirildi (tur {slide_type}): {data.get('title', '')}")

    # Xulosa slayd — alohida GPT so'rovi bilan
    conclusion_slide = prs.slides[-1]
    conclusion_data = generate_slide_content(topic, requested_slide_count, requested_slide_count, language, is_conclusion=True)
    if not conclusion_data:
        conclusion_data = {"title": "Xulosa", "content": ["Asosiy xulosalar", "Tavsiyalar"]}
    fill_t5_slide_8_conclusion(conclusion_slide, conclusion_data)

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.read()

# ─────────────────────────────────────────────────────────────
# 6-SHABLON
# ─────────────────────────────────────────────────────────────
SLIDE_TYPE_NAMES_T6 = {
    0: "one_column",      # 3-slayd: sarlavha + matn
    1: "one_column",      # 4-slayd: sarlavha + tavsif
    2: "three_columns",   # 5-slayd: 3 ta ustun (col1, col2, col3)
    3: "two_columns",     # 6-slayd: 2 ustun
    4: "one_column",      # 7-slayd: sarlavha + matn
}
CONTENT_SLIDE_TEMPLATE_INDICES_6 = [2, 3, 4, 5, 6]

def build_slide_structure_6(prs, requested_content_count):
    """
    6-shablon uchun slayd tuzilmasini quradi.
    duplicate_slide va move_slide ishlatadi.
    """
    full_repeats = max(1, round(requested_content_count / 5))
    total_content_slides = full_repeats * 5
    logging.info(f"[T6] Kontent slaydlari: {requested_content_count} so'raldi, "
                 f"{full_repeats} marta takrorlanadi ({total_content_slides} ta kontent slayd)")
    extra_sets_needed = full_repeats - 1
    for set_num in range(extra_sets_needed):
        for slide_template_idx in CONTENT_SLIDE_TEMPLATE_INDICES_6:
            duplicate_slide(prs, slide_template_idx)
        logging.info(f"  [T6] {set_num + 2}-to'plam qo'shildi. Jami slaydlar: {len(prs.slides)}")
    
    # Xulosa slaydini (index 7) oxiriga ko'chirish
    conclusion_current_index = 7
    last_index = len(prs.slides) - 1
    move_slide(prs, conclusion_current_index, last_index)
    logging.info(f"[T6] Yakuniy tuzilma: {len(prs.slides)} ta slayd")
    return total_content_slides

def fill_t6_slide_1_cover(slide, topic, name_surname):
    """
    6-Shablon Slayd 1 — Muqova.
    Shape[1]: Sarlavha (F3F0DF rang)
    Shape[2]: Subtitle (CDD6E2 rang)
    """
    from pptx.util import Pt
    from pptx.dml.color import RGBColor
    
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.clear()
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = topic.upper()
        run.font.size = Pt(52.5)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0xF3, 0xF0, 0xDF)
        
    if len(slide.shapes) > 2 and slide.shapes[2].has_text_frame:
        tf = slide.shapes[2].text_frame
        tf.clear()
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = name_surname
        run.font.size = Pt(18)
        run.font.color.rgb = RGBColor(0xCD, 0xD6, 0xE2)

def fill_t6_slide_2_plan(slide, plan_data):
    """
    6-Shablon Slayd 2 — Reja.
    Shape[1]: "Reja:"
    Shape[2]: Reja bandlari
    """
    from lxml import etree
    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    titles = plan_data.get("content", plan_data.get("titles", []))
    
    if len(slide.shapes) > 2 and slide.shapes[2].has_text_frame:
        tf = slide.shapes[2].text_frame
        tf.word_wrap = True
        total_chars = sum(len(t) for t in titles)
        font_pt = calc_body_font_pt(total_chars, base_pt=18, min_pt=12, max_pt=22)
        
        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)
            
        for title in titles:
            safe_title = title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">' 
                f'<a:pPr algn="l"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0">'
                f'<a:solidFill><a:srgbClr val="334155"/></a:solidFill></a:rPr>'
                f'<a:t>{safe_title}</a:t></a:r></a:p>'
            )
            p_elem = etree.fromstring(p_xml)
            txBody.append(p_elem)

def fill_t6_slide_3_text(slide, content_data, image_query=None):
    """
    6-Shablon Slayd 3.
    Shape[1], Shape[2]: Rasm placeholder (o'ng tomonda)
    Shape[3]: Matn (chap tomonda)
    Shape[4]: Sarlavha
    """
    from pptx.util import Pt, Cm
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
    title = content_data.get("title", "")
    items = content_data.get("content", [])
    
    if len(slide.shapes) > 4 and slide.shapes[4].has_text_frame:
        tf = slide.shapes[4].text_frame
        tf.clear()
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = title
        run.font.size = Pt(32)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0x00, 0x50, 0x88)
        
    if len(slide.shapes) > 3 and slide.shapes[3].has_text_frame:
        tf = slide.shapes[3].text_frame
        tf.clear()
        tf.word_wrap = True
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=18, min_pt=12, max_pt=24)
        for j, item in enumerate(items):
            p = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
            p.alignment = PP_ALIGN.LEFT
            run = p.add_run()
            run.text = item
            run.font.size = Pt(font_pt)
            run.font.color.rgb = RGBColor(0x33, 0x41, 0x55)

    # Mavzu bo'yicha rasm qo'shish (Shape[1] va Shape[2] o'rniga)
    # Shape[1]: left=6.93", top=2.43", size=5.78"x4.17" => 17.60x10.59cm
    if image_query and os.path.isfile(image_query):
        final_img_path = image_query
    else:
        query = image_query or content_data.get("image_query", content_data.get("title", "presentation"))
        final_img_path = fetch_image(query)
    if final_img_path:
        try:
            left = Cm(17.60)
            top  = Cm(6.17)
            width = Cm(14.69)
            height = Cm(10.59)
            slide.shapes.add_picture(final_img_path, left, top, width, height)
            if os.path.isfile(final_img_path):
                os.remove(final_img_path)
            logging.info(f"[T6] Slayd 3 rasm joylashtirildi.")
        except Exception as e:
            logging.error(f"[T6] Slayd 3 rasm xatolik: {e}")

def fill_t6_slide_4_text(slide, content_data):
    """
    6-Shablon Slayd 4.
    Shape[1]: Sarlavha
    Shape[2]: Matn
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
    title = content_data.get("title", "")
    items = content_data.get("content", [])
    
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.clear()
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = title
        run.font.size = Pt(33.75)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0x00, 0x50, 0x88)
        
    if len(slide.shapes) > 2 and slide.shapes[2].has_text_frame:
        tf = slide.shapes[2].text_frame
        tf.clear()
        tf.word_wrap = True
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=18, min_pt=12, max_pt=24)
        for j, item in enumerate(items):
            p = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
            p.alignment = PP_ALIGN.LEFT
            run = p.add_run()
            run.text = item
            run.font.size = Pt(font_pt)
            run.font.color.rgb = RGBColor(0x33, 0x41, 0x55)

def fill_t6_slide_5_three_steps(slide, content_data):
    """
    6-Shablon Slayd 5.
    Shape[1]: 1-ustun matn (left=1.98cm)
    Shape[2]: 2-ustun matn (left=12.08cm)
    Shape[3]: 3-ustun matn (left=22.97cm)
    Shape[4]: Sarlavha
    """
    from pptx.util import Pt
    from pptx.dml.color import RGBColor
    title = content_data.get("title", "")
    
    # col1/col2/col3 formatini qo'llab-quvvatlash
    col1 = content_data.get("col1", "")
    col2 = content_data.get("col2", "")
    col3 = content_data.get("col3", "")
    
    if col1 or col2 or col3:
        # three_columns formatida kelgan
        items = [col1, col2, col3]
    else:
        # content massivi formatida kelgan - 3 ta elementga to'ldirish
        raw_items = content_data.get("content", [])
        items = []
        for idx in range(3):
            if idx < len(raw_items):
                items.append(raw_items[idx])
            elif raw_items:
                # Mavjud elementlarni takrorlash o'rniga bo'sh qoldirmaslik uchun
                # oxirgi elementni ishlatamiz
                items.append(raw_items[-1])
            else:
                items.append("")
    
    if len(slide.shapes) > 4 and slide.shapes[4].has_text_frame:
        tf = slide.shapes[4].text_frame
        tf.clear()
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = title
        run.font.size = Pt(32)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0x00, 0x50, 0x88)
        
    for i in range(3):
        shape_idx = i + 1
        if len(slide.shapes) > shape_idx and slide.shapes[shape_idx].has_text_frame:
            text = items[i] if i < len(items) else ""
            tf = slide.shapes[shape_idx].text_frame
            tf.clear()
            tf.word_wrap = True
            font_pt = calc_body_font_pt(len(text), base_pt=14, min_pt=10, max_pt=18)
            p = tf.paragraphs[0]
            run = p.add_run()
            run.text = text
            run.font.size = Pt(font_pt)
            run.font.color.rgb = RGBColor(0x33, 0x41, 0x55)

def fill_t6_slide_6_two_cols(slide, content_data):
    """
    6-Shablon Slayd 6.
    Shape[1]: 1-ustun matn (left=2.25cm, chap tomonda)
    Shape[2]: 2-ustun matn (left=18.52cm, o'ng tomonda)
    Shape[3]: Sarlavha
    Ustunlar gorizontal joylashgan, chapga tekislangan.
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
    title = content_data.get("title", "")
    
    # col1/col2 string yoki list bo'lishi mumkin
    col1_raw = content_data.get("col1", "")
    col2_raw = content_data.get("col2", "")
    
    if col1_raw or col2_raw:
        # two_columns formatida kelgan
        col1_text = col1_raw if isinstance(col1_raw, str) else "\n".join(col1_raw)
        col2_text = col2_raw if isinstance(col2_raw, str) else "\n".join(col2_raw)
    else:
        # content massivi formatida kelgan - ikki qismga bo'lish
        items = content_data.get("content", [])
        mid = max(1, len(items) // 2)
        col1_list = items[:mid]
        col2_list = items[mid:]
        col1_text = "\n".join(col1_list)
        col2_text = "\n".join(col2_list)
        
    if len(slide.shapes) > 3 and slide.shapes[3].has_text_frame:
        tf = slide.shapes[3].text_frame
        tf.clear()
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = title
        run.font.size = Pt(32)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0x00, 0x50, 0x88)
        
    for shape_idx, col_text in [(1, col1_text), (2, col2_text)]:
        if len(slide.shapes) > shape_idx and slide.shapes[shape_idx].has_text_frame:
            tf = slide.shapes[shape_idx].text_frame
            tf.clear()
            tf.word_wrap = True
            font_pt = calc_body_font_pt(len(col_text), base_pt=14, min_pt=10, max_pt=18)
            # Har bir satr uchun alohida paragraf - chapga tekislangan
            lines = col_text.split("\n") if col_text else [""]
            for j, line in enumerate(lines):
                p = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
                p.alignment = PP_ALIGN.LEFT
                run = p.add_run()
                run.text = line
                run.font.size = Pt(font_pt)
                run.font.color.rgb = RGBColor(0x33, 0x41, 0x55)

def fill_t6_slide_7_text(slide, content_data, image_query=None):
    """
    6-Shablon Slayd 7.
    Shape[0]: Fon rasm (to'liq)
    Shape[1]: Sarlavha (chap tomonda)
    Shape[2]: Chiziq
    Shape[3]: Matn (chap tomonda)
    Shape[4]: Rasm placeholder (o'ng tomonda)
    """
    from pptx.util import Pt, Cm
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
    title = content_data.get("title", "")
    items = content_data.get("content", [])
    
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.clear()
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = title
        run.font.size = Pt(32)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0x00, 0x50, 0x88)
        
    if len(slide.shapes) > 3 and slide.shapes[3].has_text_frame:
        tf = slide.shapes[3].text_frame
        tf.clear()
        tf.word_wrap = True
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=14, min_pt=10, max_pt=18)
        for j, item in enumerate(items):
            p = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
            p.alignment = PP_ALIGN.LEFT
            run = p.add_run()
            run.text = item
            run.font.size = Pt(font_pt)
            run.font.color.rgb = RGBColor(0x33, 0x41, 0x55)

    # Mavzu bo'yicha rasm qo'shish (Shape[4] o'rniga - o'ng tomonda)
    # Shape[4]: left=6.67", top=0.00", size=6.67"x7.50" => 16.93x19.05cm
    if image_query and os.path.isfile(image_query):
        final_img_path = image_query
    else:
        query = image_query or content_data.get("image_query", content_data.get("title", "presentation"))
        final_img_path = fetch_image(query)
    if final_img_path:
        try:
            left = Cm(16.93)
            top  = Cm(0.00)
            width = Cm(16.93)
            height = Cm(19.05)
            slide.shapes.add_picture(final_img_path, left, top, width, height)
            if os.path.isfile(final_img_path):
                os.remove(final_img_path)
            logging.info(f"[T6] Slayd 7 rasm joylashtirildi.")
        except Exception as e:
            logging.error(f"[T6] Slayd 7 rasm xatolik: {e}")

def fill_t6_slide_8_conclusion(slide, conclusion_data):
    """
    6-Shablon Slayd 8 — Xulosa.
    Shape[1]: "XULOSA" (katta matn, pos=1.29cm, size=31.06x4.10cm)
    Shape[2]: Xulosa matni (pos=13.12cm, size=7.62cm -> 24cm ga kengaytiriladi)
    """
    from pptx.util import Pt, Cm
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
    items = conclusion_data.get("content", [])
    if not items:
        items = conclusion_data.get("col1", []) + conclusion_data.get("col2", [])
        
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.clear()
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = "XULOSA"
        run.font.size = Pt(60)
        run.font.color.rgb = RGBColor(0xCD, 0xD6, 0xE2)
        
    if len(slide.shapes) > 2 and slide.shapes[2].has_text_frame:
        # Asosiy matn blokini 24 sm eniga kengaytirish va markazga joylashtirish
        shape2 = slide.shapes[2]
        shape2.width = Cm(24)
        # Slayd kengligi 33.87cm, markazda joylashish: left = (33.87 - 24) / 2 ≈ 4.94cm
        shape2.left = Cm(4.94)
        tf = shape2.text_frame
        tf.clear()
        tf.word_wrap = True
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=18, min_pt=12, max_pt=24)
        for j, item in enumerate(items):
            p = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
            p.alignment = PP_ALIGN.LEFT
            run = p.add_run()
            run.text = item
            run.font.size = Pt(font_pt)
            run.font.color.rgb = RGBColor(0xCD, 0xD6, 0xE2)

def generate_template_6_presentation(prs, topic, requested_slide_count, language,
                                      name_surname, plan, content_data_list, user_images=None):
    """
    6-shablon asosida to'liq prezentatsiya yaratadi.
    """
    import io
    
    total_content_slides = build_slide_structure_6(prs, requested_slide_count)
    plan_dict = plan if isinstance(plan, dict) else {}
    
    # Slayd 1 — Muqova
    fill_t6_slide_1_cover(prs.slides[0], topic, name_surname)
    
    # Slayd 2 — Reja
    fill_t6_slide_2_plan(prs.slides[1], plan_dict)
    
    # Kontent slaydlari (3-dan boshlab)
    user_img_idx = 0
    for i in range(total_content_slides):
        slide_index = i + 2
        if slide_index >= len(prs.slides) - 1:
            break
            
        slide = prs.slides[slide_index]
        data = content_data_list[i] if i < len(content_data_list) else {}
        image_query = data.get("image_query", topic)
        
        slide_type = i % 5
        if slide_type == 0:
            if user_images and user_img_idx < len(user_images):
                img_path = save_user_image_to_tmp(user_images[user_img_idx])
                user_img_idx += 1
                fill_t6_slide_3_text(slide, data, img_path if img_path else image_query)
            else:
                fill_t6_slide_3_text(slide, data)
        elif slide_type == 1:
            fill_t6_slide_4_text(slide, data)
        elif slide_type == 2:
            fill_t6_slide_5_three_steps(slide, data)
        elif slide_type == 3:
            fill_t6_slide_6_two_cols(slide, data)
        elif slide_type == 4:
            if user_images and user_img_idx < len(user_images):
                img_path = save_user_image_to_tmp(user_images[user_img_idx])
                user_img_idx += 1
                fill_t6_slide_7_text(slide, data, img_path if img_path else image_query)
            else:
                fill_t6_slide_7_text(slide, data)
            
        logging.info(f"  [T6] Slayd {slide_index + 1} to'ldirildi (tur {slide_type}): {data.get('title', '')}")
        
    # Xulosa slayd
    conclusion_slide = prs.slides[-1]
    conclusion_data = generate_slide_content(topic, requested_slide_count, requested_slide_count, language, is_conclusion=True)
    if not conclusion_data:
        conclusion_data = {"title": "Xulosa", "content": ["Asosiy xulosalar", "Tavsiyalar"]}
    fill_t6_slide_8_conclusion(conclusion_slide, conclusion_data)
    
    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.read()


# ═══════════════════════════════════════════════════════════════
# 7-SHABLON FUNKSIYALARI (7.pptx)
# ═══════════════════════════════════════════════════════════════
# Slayd tuzilmasi:
#   Slayd 1: Muqova — Shape[0]: sarlavha (o'ng), Shape[1]: muallif
#   Slayd 2: Reja — Shape[0]: sarlavha, Shape[1]: reja bandlari
#   Slayd 3: Rasm chap + matn o'ng — Shape[0]: sarlavha, Shape[1]: rasm, Shape[2]: qo'shimcha matn
#   Slayd 4: Katta matn — Shape[0]: sarlavha, Shape[1]: matn, Shape[2]: dekorativ group
#   Slayd 5: Ikki ustun — Shape[0]: sarlavha, Shape[1]: chap ustun, Shape[2]: o'ng ustun
#   Slayd 6: Sarlavha o'ngda + 2 matn — Shape[0]: sarlavha (o'ng), Shape[1]: yuqori matn, Shape[2]: pastki matn
#   Slayd 7: Rasm o'ng + matn chap — Shape[0]: sarlavha, Shape[1]: matn, Shape[2]: rasm
#   Slayd 8: Xulosa — Shape[0]: sarlavha, Shape[1]: matn

SLIDE_TYPE_NAMES_T7 = {
    0: "image_left",    # 3-slayd: rasm chap, matn o'ng
    1: "one_column",    # 4-slayd: katta matn bloki
    2: "two_columns",   # 5-slayd: ikki ustun
    3: "two_columns",   # 6-slayd: sarlavha o'ngda + 2 matn bloki
    4: "image_right",   # 7-slayd: rasm o'ng, matn chap
}
CONTENT_SLIDE_TEMPLATE_INDICES_7 = [2, 3, 4, 5, 6]


def build_slide_structure_7(prs, requested_content_count):
    """
    7-shablon uchun slayd tuzilmasini quradi.
    duplicate_slide va move_slide ishlatadi.
    """
    full_repeats = max(1, round(requested_content_count / 5))
    total_content_slides = full_repeats * 5
    logging.info(f"[T7] Kontent slaydlari: {requested_content_count} so'raldi, "
                 f"{full_repeats} marta takrorlanadi ({total_content_slides} ta kontent slayd)")
    extra_sets_needed = full_repeats - 1
    for set_num in range(extra_sets_needed):
        for slide_template_idx in CONTENT_SLIDE_TEMPLATE_INDICES_7:
            duplicate_slide(prs, slide_template_idx)
        logging.info(f"  [T7] {set_num + 2}-to'plam qo'shildi. Jami slaydlar: {len(prs.slides)}")

    # Xulosa slaydini (index 7) oxiriga ko'chirish
    conclusion_current_index = 7
    last_index = len(prs.slides) - 1
    move_slide(prs, conclusion_current_index, last_index)
    logging.info(f"[T7] Yakuniy tuzilma: {len(prs.slides)} ta slayd")
    return total_content_slides


def fill_t7_slide_1_cover(slide, topic, name_surname):
    """
    7-Shablon Slayd 1 — Muqova.
    Shape[0]: Sarlavha (o'ng tomonda, katta)
    Shape[1]: Muallif ismi (o'ng pastda)
    """
    from pptx.util import Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN

    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = topic.upper()
        total_chars = len(topic)
        font_pt = calc_body_font_pt(total_chars, base_pt=52, min_pt=28, max_pt=60)
        run.font.size = Pt(font_pt)
        run.font.bold = True

    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.clear()
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = name_surname if name_surname and name_surname.strip() else ""
        run.font.size = Pt(18)


def fill_t7_slide_2_plan(slide, plan_data):
    """
    7-Shablon Slayd 2 — Reja.
    Shape[0]: Sarlavha ("Reja")
    Shape[1]: Reja bandlari
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
    from lxml import etree

    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    titles = plan_data.get("content", plan_data.get("titles", []))

    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = "Reja"
        run.font.size = Pt(36)
        run.font.bold = True

    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        import re
        tf = slide.shapes[1].text_frame
        tf.word_wrap = True
        total_chars = sum(len(t) for t in titles)
        font_pt = calc_body_font_pt(total_chars, base_pt=20, min_pt=13, max_pt=24)

        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)

        for i, title in enumerate(titles):
            # GPT allaqachon "1. Band" formatida qaytarishi mumkin - boshidagi raqamni olib tashlaymiz
            clean_title = re.sub(r'^\d+[\.)\-]\s*', '', title.strip())
            safe_title = clean_title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0">'
                f'</a:rPr>'
                f'<a:t>{i+1}. {safe_title}</a:t></a:r></a:p>'
            )
            p_elem = etree.fromstring(p_xml)
            txBody.append(p_elem)


def fill_t7_slide_3_image_left(slide, content_data, image_query=None):
    """
    7-Shablon Slayd 3 — Rasm chap, matn o'ng.
    Shape[0]: Sarlavha (o'ng tomonda yuqori)
    Shape[1]: Rasm placeholder (chap tomonda, to'liq balandlik)
    Shape[2]: Qo'shimcha matn (o'ng pastda)
    Rasm: Shape[1] o'rniga joylashtiriladi
    """
    from pptx.util import Pt, Cm
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor

    title = content_data.get("title", "")
    items = content_data.get("content", [])

    # Shape[0]: Sarlavha
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(32)
        run.font.bold = True

    # Shape[2]: Qo'shimcha matn (o'ng pastda)
    if len(slide.shapes) > 2 and slide.shapes[2].has_text_frame:
        tf = slide.shapes[2].text_frame
        tf.clear()
        tf.word_wrap = True
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=16, min_pt=11, max_pt=20)
        for j, item in enumerate(items):
            p = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
            p.alignment = PP_ALIGN.LEFT
            run = p.add_run()
            run.text = item
            run.font.size = Pt(font_pt)

    # Rasm: Shape[1] o'rniga (chap tomonda, to'liq balandlik)
    # Shape[1]: left=0.00cm, top=-0.03cm, size=16.09x19.11cm
    if image_query and os.path.isfile(image_query):
        final_img_path = image_query
    else:
        query = image_query or content_data.get("image_query", content_data.get("title", "presentation"))
        final_img_path = fetch_image(query)
    if final_img_path:
        try:
            left = Cm(0.00)
            top = Cm(0.00)
            width = Cm(16.09)
            height = Cm(19.05)
            slide.shapes.add_picture(final_img_path, left, top, width, height)
            if os.path.isfile(final_img_path):
                os.remove(final_img_path)
            logging.info(f"[T7] Slayd 3 rasm joylashtirildi.")
        except Exception as e:
            logging.error(f"[T7] Slayd 3 rasm xatolik: {e}")


def fill_t7_slide_4_text(slide, content_data):
    """
    7-Shablon Slayd 4 — Katta matn bloki.
    Shape[0]: Sarlavha
    Shape[1]: Asosiy matn (bullet list)
    Shape[2]: Dekorativ group (o'zgartirilmaydi)
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
    from lxml import etree

    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = content_data.get("title", "")
    items = content_data.get("content", [])

    # Shape[0]: Sarlavha
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(36)
        run.font.bold = True

    # Shape[1]: Asosiy matn
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.word_wrap = True
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=18, min_pt=12, max_pt=22)

        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)

        for item in items:
            safe_item = item.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0">'
                f'</a:rPr>'
                f'<a:t>{safe_item}</a:t></a:r></a:p>'
            )
            p_elem = etree.fromstring(p_xml)
            txBody.append(p_elem)


def fill_t7_slide_5_two_cols(slide, content_data):
    """
    7-Shablon Slayd 5 — Ikki ustun.
    Shape[0]: Sarlavha
    Shape[1]: Chap ustun matn
    Shape[2]: O'ng ustun matn
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
    from lxml import etree

    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = content_data.get("title", "")
    col1_text = content_data.get("col1", "")
    col2_text = content_data.get("col2", "")

    # Agar col1/col2 bo'lmasa, content dan olamiz
    if not col1_text and not col2_text:
        items = content_data.get("content", [])
        col1_text = items[0] if len(items) > 0 else ""
        col2_text = items[1] if len(items) > 1 else ""

    # Shape[0]: Sarlavha
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(32)
        run.font.bold = True

    total_chars = len(col1_text) + len(col2_text)
    font_pt = calc_body_font_pt(total_chars, base_pt=16, min_pt=11, max_pt=20)

    # Shape[1]: Chap ustun
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.word_wrap = True
        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)
        safe_col1 = col1_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        p_xml = (
            f'<a:p xmlns:a="{ns_a}">'
            f'<a:pPr algn="l"><a:buNone/></a:pPr>'
            f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0">'
            f'</a:rPr>'
            f'<a:t>{safe_col1}</a:t></a:r></a:p>'
        )
        p_elem = etree.fromstring(p_xml)
        txBody.append(p_elem)

    # Shape[2]: O'ng ustun
    if len(slide.shapes) > 2 and slide.shapes[2].has_text_frame:
        tf = slide.shapes[2].text_frame
        tf.word_wrap = True
        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)
        safe_col2 = col2_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        p_xml = (
            f'<a:p xmlns:a="{ns_a}">'
            f'<a:pPr algn="l"><a:buNone/></a:pPr>'
            f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0">'
            f'</a:rPr>'
            f'<a:t>{safe_col2}</a:t></a:r></a:p>'
        )
        p_elem = etree.fromstring(p_xml)
        txBody.append(p_elem)


def fill_t7_slide_6_special(slide, content_data):
    """
    7-Shablon Slayd 6 — Sarlavha o'ngda, 2 matn bloki chapda.
    Shape[0]: Sarlavha (o'ng pastda)
    Shape[1]: Yuqori matn bloki (chap)
    Shape[2]: Pastki matn bloki (chap)
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
    from lxml import etree

    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = content_data.get("title", "")
    col1_text = content_data.get("col1", "")
    col2_text = content_data.get("col2", "")

    if not col1_text and not col2_text:
        items = content_data.get("content", [])
        col1_text = items[0] if len(items) > 0 else ""
        col2_text = items[1] if len(items) > 1 else ""

    # Shape[0]: Sarlavha (o'ng pastda)
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(28)
        run.font.bold = True

    total_chars = len(col1_text) + len(col2_text)
    font_pt = calc_body_font_pt(total_chars, base_pt=16, min_pt=11, max_pt=20)

    # Shape[1]: Yuqori matn
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.word_wrap = True
        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)
        safe_col1 = col1_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        p_xml = (
            f'<a:p xmlns:a="{ns_a}">'
            f'<a:pPr algn="l"><a:buNone/></a:pPr>'
            f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0">'
            f'</a:rPr>'
            f'<a:t>{safe_col1}</a:t></a:r></a:p>'
        )
        p_elem = etree.fromstring(p_xml)
        txBody.append(p_elem)

    # Shape[2]: Pastki matn
    if len(slide.shapes) > 2 and slide.shapes[2].has_text_frame:
        tf = slide.shapes[2].text_frame
        tf.word_wrap = True
        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)
        safe_col2 = col2_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        p_xml = (
            f'<a:p xmlns:a="{ns_a}">'
            f'<a:pPr algn="l"><a:buNone/></a:pPr>'
            f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0">'
            f'</a:rPr>'
            f'<a:t>{safe_col2}</a:t></a:r></a:p>'
        )
        p_elem = etree.fromstring(p_xml)
        txBody.append(p_elem)


def fill_t7_slide_7_image_right(slide, content_data, image_query=None):
    """
    7-Shablon Slayd 7 — Rasm o'ng, matn chap.
    Shape[0]: Sarlavha (chap yuqori)
    Shape[1]: Matn (chap pastda)
    Shape[2]: Rasm placeholder (o'ng tomonda, to'liq balandlik)
    Rasm: Shape[2] o'rniga joylashtiriladi
    """
    from pptx.util import Pt, Cm
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
    from lxml import etree

    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = content_data.get("title", "")
    items = content_data.get("content", [])

    # Shape[0]: Sarlavha
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(32)
        run.font.bold = True

    # Shape[1]: Matn
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.word_wrap = True
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=16, min_pt=11, max_pt=20)

        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)

        for item in items:
            safe_item = item.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0">'
                f'</a:rPr>'
                f'<a:t>{safe_item}</a:t></a:r></a:p>'
            )
            p_elem = etree.fromstring(p_xml)
            txBody.append(p_elem)

    # Rasm: Shape[2] o'rniga (o'ng tomonda, to'liq balandlik)
    # Shape[2]: left=16.93cm, top=0.00cm, size=17.00x19.05cm
    if image_query and os.path.isfile(image_query):
        final_img_path = image_query
    else:
        query = image_query or content_data.get("image_query", content_data.get("title", "presentation"))
        final_img_path = fetch_image(query)
    if final_img_path:
        try:
            left = Cm(16.93)
            top = Cm(0.00)
            width = Cm(17.00)
            height = Cm(19.05)
            slide.shapes.add_picture(final_img_path, left, top, width, height)
            if os.path.isfile(final_img_path):
                os.remove(final_img_path)
            logging.info(f"[T7] Slayd 7 rasm joylashtirildi.")
        except Exception as e:
            logging.error(f"[T7] Slayd 7 rasm xatolik: {e}")


def fill_t7_slide_8_conclusion(slide, conclusion_data):
    """
    7-Shablon Slayd 8 — Xulosa.
    Shape[0]: Sarlavha ("Xulosa" yoki "Thanks!")
    Shape[1]: Qo'shimcha matn
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
    from lxml import etree

    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = conclusion_data.get("title", "Xulosa")
    items = conclusion_data.get("content", [])

    # Shape[0]: Sarlavha
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(48)
        run.font.bold = True

    # Shape[1]: Qo'shimcha matn - 2 sm yuqoriga ko'tarish
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        from pptx.util import Cm
        shape1 = slide.shapes[1]
        # top: 11.22cm -> 9.22cm (2 sm yuqoriga)
        shape1.top = Cm(9.22)
        tf = shape1.text_frame
        tf.word_wrap = True
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=18, min_pt=12, max_pt=22)

        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)

        for item in items:
            safe_item = item.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0">'
                f'</a:rPr>'
                f'<a:t>{safe_item}</a:t></a:r></a:p>'
            )
            p_elem = etree.fromstring(p_xml)
            txBody.append(p_elem)


def generate_template_7_presentation(prs, topic, requested_slide_count, language,
                                      name_surname, plan, content_data_list, user_images=None):
    """
    7-shablon asosida to'liq prezentatsiya yaratadi.
    """
    import io

    total_content_slides = build_slide_structure_7(prs, requested_slide_count)
    plan_dict = plan if isinstance(plan, dict) else {}

    # Slayd 1 — Muqova
    fill_t7_slide_1_cover(prs.slides[0], topic, name_surname)

    # Slayd 2 — Reja
    fill_t7_slide_2_plan(prs.slides[1], plan_dict)

    # Kontent slaydlari (3-dan boshlab)
    user_img_idx = 0
    for i in range(total_content_slides):
        slide_index = i + 2
        if slide_index >= len(prs.slides) - 1:
            break

        slide = prs.slides[slide_index]
        data = content_data_list[i] if i < len(content_data_list) else {}
        image_query = data.get("image_query", topic)

        slide_type = i % 5
        if slide_type == 0:
            if user_images and user_img_idx < len(user_images):
                img_path = save_user_image_to_tmp(user_images[user_img_idx])
                user_img_idx += 1
                fill_t7_slide_3_image_left(slide, data, img_path if img_path else image_query)
            else:
                fill_t7_slide_3_image_left(slide, data)
        elif slide_type == 1:
            fill_t7_slide_4_text(slide, data)
        elif slide_type == 2:
            fill_t7_slide_5_two_cols(slide, data)
        elif slide_type == 3:
            fill_t7_slide_6_special(slide, data)
        elif slide_type == 4:
            if user_images and user_img_idx < len(user_images):
                img_path = save_user_image_to_tmp(user_images[user_img_idx])
                user_img_idx += 1
                fill_t7_slide_7_image_right(slide, data, img_path if img_path else image_query)
            else:
                fill_t7_slide_7_image_right(slide, data)

        logging.info(f"  [T7] Slayd {slide_index + 1} to'ldirildi (tur {slide_type}): {data.get('title', '')}")

    # Xulosa slayd — GPT dan xulosa matni so'rash
    conclusion_slide = prs.slides[-1]
    conclusion_data = generate_slide_content(topic, len(prs.slides), len(prs.slides), language, is_conclusion=True)
    if not conclusion_data:
        conclusion_data = {"title": "Xulosa", "content": ["Asosiy xulosalar", "Tavsiyalar"]}
    fill_t7_slide_8_conclusion(conclusion_slide, conclusion_data)

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.read()


# ═══════════════════════════════════════════════════════════════
# 8-SHABLON — "Biznes" uslubi
# ═══════════════════════════════════════════════════════════════

SLIDE_TYPE_NAMES_T8 = {
    0: "image_right",    # Slayd 3: sarlavha + matn chap + rasm o'ng
    1: "one_column",     # Slayd 4: sarlavha katta chap + matn o'ng
    2: "image_right",    # Slayd 5: sarlavha + matn past + rasm o'ng
    3: "two_columns",    # Slayd 6: sarlavha + 2 teng ustun
    4: "two_columns",    # Slayd 7: sarlavha + tor chap + keng o'ng
}

CONTENT_SLIDE_TEMPLATE_INDICES_T8 = [2, 3, 4, 5, 6]  # 0-indexed: slayd 3,4,5,6,7


def build_slide_structure_8(prs, requested_content_count):
    """
    8-shablon uchun slayd tuzilmasini yaratadi.
    Muqova(1) + Reja(1) + Kontent(N) + Xulosa(1) = jami
    5 ta kontent shablon slayd bor (index 2-6), to'liq to'plamlar sifatida takrorlanadi.
    """
    n_templates = len(CONTENT_SLIDE_TEMPLATE_INDICES_T8)  # 5
    full_repeats = max(1, round(requested_content_count / n_templates))
    total_content_slides = full_repeats * n_templates
    logging.info(f"[T8] Kontent slaydlari: {requested_content_count} so'raldi, "
                 f"{full_repeats} marta takrorlanadi ({total_content_slides} ta kontent slayd)")

    conclusion_current_index = 7  # 0-indexed: slayd 8

    # Kerakli to'plamlar soniga qarab nusxalash
    extra_sets_needed = full_repeats - 1
    for set_num in range(extra_sets_needed):
        for slide_template_idx in CONTENT_SLIDE_TEMPLATE_INDICES_T8:
            duplicate_slide(prs, slide_template_idx)
        logging.info(f"  [T8] {set_num + 2}-to'plam qo'shildi. Jami slaydlar: {len(prs.slides)}")

    last_index = len(prs.slides) - 1
    move_slide(prs, conclusion_current_index, last_index)
    logging.info(f"[T8] Yakuniy tuzilma: {len(prs.slides)} ta slayd")
    return total_content_slides


def fill_t8_slide_1_cover(slide, topic, name_surname):
    """
    8-Shablon Slayd 1 — Muqova.
    Shape[0]: Fon rasm (PICTURE placeholder)
    Shape[1]: Sarlavha (TITLE)
    Shape[2]: Ism-familiya (TEXT_BOX)
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN

    # Shape[1]: Sarlavha
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = topic
        total_chars = len(topic)
        font_pt = calc_body_font_pt(total_chars, base_pt=48, min_pt=28, max_pt=60)
        run.font.size = Pt(font_pt)
        run.font.bold = True

    # Shape[2]: Ism-familiya (TEXT_BOX)
    if len(slide.shapes) > 2 and slide.shapes[2].has_text_frame:
        tf = slide.shapes[2].text_frame
        tf.clear()
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.RIGHT
        run = p.add_run()
        run.text = name_surname if name_surname and name_surname.strip() else ""
        run.font.size = Pt(18)


def fill_t8_slide_2_plan(slide, plan_data):
    """
    8-Shablon Slayd 2 — Reja.
    Shape[0]: Sarlavha ("Reja")
    Shape[1]: Reja bandlari
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from lxml import etree

    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    titles = plan_data.get("content", plan_data.get("titles", []))

    # Shape[0]: Sarlavha
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = "Reja"
        run.font.size = Pt(32)
        run.font.bold = True

    # Shape[1]: Reja bandlari
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        import re
        tf = slide.shapes[1].text_frame
        tf.word_wrap = True
        total_chars = sum(len(t) for t in titles)
        font_pt = calc_body_font_pt(total_chars, base_pt=22, min_pt=14, max_pt=28)

        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)

        for i, title in enumerate(titles):
            # GPT allaqachon "1. Band" formatida qaytarishi mumkin - boshidagi raqamni olib tashlaymiz
            clean_title = re.sub(r'^\d+[\.)\-]\s*', '', title.strip())
            safe_title = clean_title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0">'
                f'</a:rPr>'
                f'<a:t>{i+1}. {safe_title}</a:t></a:r></a:p>'
            )
            p_elem = etree.fromstring(p_xml)
            txBody.append(p_elem)


def fill_t8_slide_3_image_right(slide, content_data, image_query=None):
    """
    8-Shablon Slayd 3 — Sarlavha + Matn chap + Rasm o'ng.
    Shape[0]: Sarlavha (TITLE) - chapda yuqori
    Shape[1]: Matn (OBJECT idx=11) - chapda pastda
    Shape[2]: Rasm (PICTURE idx=10) - o'ngda
    """
    from pptx.util import Pt, Cm
    from pptx.enum.text import PP_ALIGN
    from lxml import etree

    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = content_data.get("title", "")
    items = content_data.get("content", [])
    if isinstance(items, str):
        items = [items]

    # Shape[0]: Sarlavha
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(32)
        run.font.bold = True

    # Shape[1]: Matn (chapda pastda)
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.word_wrap = True
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=16, min_pt=11, max_pt=20)

        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)

        for item in items:
            safe_item = item.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0">'
                f'</a:rPr>'
                f'<a:t>{safe_item}</a:t></a:r></a:p>'
            )
            p_elem = etree.fromstring(p_xml)
            txBody.append(p_elem)

    # Rasm: Shape[2] o'rniga (o'ng tomonda)
    if image_query and os.path.isfile(image_query):
        final_img_path = image_query
    else:
        query = image_query or content_data.get("image_query", title)
        final_img_path = fetch_image(query)
    if final_img_path:
        try:
            left = Cm(18.0)
            top = Cm(2.56)
            width = Cm(15.87)
            height = Cm(13.97)
            slide.shapes.add_picture(final_img_path, left, top, width, height)
            if os.path.isfile(final_img_path):
                os.remove(final_img_path)
            logging.info(f"[T8] Slayd 3 rasm joylashtirildi.")
        except Exception as e:
            logging.error(f"[T8] Slayd 3 rasm xatolik: {e}")


def fill_t8_slide_4_title_left(slide, content_data):
    """
    8-Shablon Slayd 4 — Sarlavha katta chapda + Matn o'ngda.
    Shape[0]: Sarlavha (TITLE) - chapda katta
    Shape[1]: Matn (OBJECT idx=11) - o'ngda
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from lxml import etree

    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = content_data.get("title", "")
    items = content_data.get("content", [])
    if isinstance(items, str):
        items = [items]

    # Shape[0]: Sarlavha (chapda, katta)
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        total_chars = len(title)
        font_pt = calc_body_font_pt(total_chars, base_pt=40, min_pt=24, max_pt=52)
        run.font.size = Pt(font_pt)
        run.font.bold = True

    # Shape[1]: Matn (o'ngda)
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.word_wrap = True
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=16, min_pt=11, max_pt=20)

        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)

        for item in items:
            safe_item = item.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0">'
                f'</a:rPr>'
                f'<a:t>{safe_item}</a:t></a:r></a:p>'
            )
            p_elem = etree.fromstring(p_xml)
            txBody.append(p_elem)


def fill_t8_slide_5_image_right2(slide, content_data, image_query=None):
    """
    8-Shablon Slayd 5 — Sarlavha + Matn pastda + Rasm o'ng.
    Shape[0]: Sarlavha (TITLE) - chapda yuqori
    Shape[1]: Matn (OBJECT idx=11) - chapda pastda
    Shape[2]: Rasm (PICTURE idx=10) - o'ngda
    Shape[3]: Slide number
    """
    from pptx.util import Pt, Cm
    from pptx.enum.text import PP_ALIGN
    from lxml import etree

    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = content_data.get("title", "")
    items = content_data.get("content", [])
    if isinstance(items, str):
        items = [items]

    # Shape[0]: Sarlavha — 1 sm yuqoriga ko'tarish (2.50 -> 1.50)
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        slide.shapes[0].top = Cm(1.50)
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(32)
        run.font.bold = True

    # Shape[1]: Matn (chapda pastda) — 2 sm yuqoriga ko'tarish (10.63 -> 8.63)
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        slide.shapes[1].top = Cm(8.63)
        tf = slide.shapes[1].text_frame
        tf.word_wrap = True
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=16, min_pt=11, max_pt=20)

        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)

        for item in items:
            safe_item = item.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0">'
                f'</a:rPr>'
                f'<a:t>{safe_item}</a:t></a:r></a:p>'
            )
            p_elem = etree.fromstring(p_xml)
            txBody.append(p_elem)

    # Rasm: Shape[2] o'rniga (o'ng tomonda)
    if image_query and os.path.isfile(image_query):
        final_img_path = image_query
    else:
        query = image_query or content_data.get("image_query", title)
        final_img_path = fetch_image(query)
    if final_img_path:
        try:
            left = Cm(18.0)
            top = Cm(2.56)
            width = Cm(15.87)
            height = Cm(13.97)
            slide.shapes.add_picture(final_img_path, left, top, width, height)
            if os.path.isfile(final_img_path):
                os.remove(final_img_path)
            logging.info(f"[T8] Slayd 5 rasm joylashtirildi.")
        except Exception as e:
            logging.error(f"[T8] Slayd 5 rasm xatolik: {e}")


def fill_t8_slide_6_two_cols(slide, content_data):
    """
    8-Shablon Slayd 6 — Sarlavha + 2 teng ustun.
    Shape[0]: Sarlavha (TITLE) - yuqori
    Shape[1]: Chap ustun (OBJECT idx=10)
    Shape[2]: O'ng ustun (OBJECT idx=11)
    Shape[3]: Slide number
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from lxml import etree

    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = content_data.get("title", "")
    col1 = content_data.get("col1", "")
    col2 = content_data.get("col2", "")
    if isinstance(col1, list):
        col1 = " ".join(col1)
    if isinstance(col2, list):
        col2 = " ".join(col2)
    # Fallback: content dan olamiz
    if not col1 and not col2:
        items = content_data.get("content", [])
        if isinstance(items, list) and len(items) >= 2:
            mid = len(items) // 2
            col1 = " ".join(items[:mid])
            col2 = " ".join(items[mid:])
        elif isinstance(items, str):
            col1 = items
            col2 = ""

    # Shape[0]: Sarlavha
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(32)
        run.font.bold = True

    # Shape[1]: Chap ustun
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.clear()
        tf.word_wrap = True
        total_chars = len(col1)
        font_pt = calc_body_font_pt(total_chars, base_pt=16, min_pt=11, max_pt=20)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = col1
        run.font.size = Pt(font_pt)

    # Shape[2]: O'ng ustun
    if len(slide.shapes) > 2 and slide.shapes[2].has_text_frame:
        tf = slide.shapes[2].text_frame
        tf.clear()
        tf.word_wrap = True
        total_chars = len(col2)
        font_pt = calc_body_font_pt(total_chars, base_pt=16, min_pt=11, max_pt=20)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = col2
        run.font.size = Pt(font_pt)


def fill_t8_slide_7_narrow_wide(slide, content_data):
    """
    8-Shablon Slayd 7 — Sarlavha + Tor chap (kalit so'zlar) + Keng o'ng (tavsif).
    Shape[0]: Sarlavha (TITLE) - yuqori
    Shape[1]: Tor chap ustun (OBJECT idx=10) - kalit so'zlar
    Shape[2]: Keng o'ng ustun (OBJECT idx=11) - tavsif
    Shape[3]: Slide number
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from lxml import etree

    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = content_data.get("title", "")
    col1 = content_data.get("col1", "")
    col2 = content_data.get("col2", "")
    if isinstance(col1, list):
        col1 = "\n".join(col1)
    if isinstance(col2, list):
        col2 = "\n".join(col2)
    # Fallback: content dan olamiz
    if not col1 and not col2:
        items = content_data.get("content", [])
        if isinstance(items, list) and len(items) >= 2:
            # Birinchi yarmini kalit so'z sifatida, ikkinchisini tavsif sifatida
            mid = max(1, len(items) // 3)
            col1 = "\n".join(items[:mid])
            col2 = "\n".join(items[mid:])
        elif isinstance(items, str):
            col1 = items
            col2 = ""

    # Shape[0]: Sarlavha
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(32)
        run.font.bold = True

    # Shape[1]: Tor chap ustun (kalit so'zlar)
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.word_wrap = True
        lines = col1.split("\n") if col1 else []
        total_chars = len(col1)
        font_pt = calc_body_font_pt(total_chars, base_pt=18, min_pt=13, max_pt=22)

        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)

        for line in lines:
            safe_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" b="1" dirty="0">'
                f'</a:rPr>'
                f'<a:t>{safe_line}</a:t></a:r></a:p>'
            )
            p_elem = etree.fromstring(p_xml)
            txBody.append(p_elem)

    # Shape[2]: Keng o'ng ustun (tavsif)
    if len(slide.shapes) > 2 and slide.shapes[2].has_text_frame:
        tf = slide.shapes[2].text_frame
        tf.word_wrap = True
        lines = col2.split("\n") if col2 else []
        total_chars = len(col2)
        font_pt = calc_body_font_pt(total_chars, base_pt=16, min_pt=11, max_pt=20)

        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)

        for line in lines:
            safe_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0">'
                f'</a:rPr>'
                f'<a:t>{safe_line}</a:t></a:r></a:p>'
            )
            p_elem = etree.fromstring(p_xml)
            txBody.append(p_elem)


def fill_t8_slide_8_conclusion(slide, conclusion_data):
    """
    8-Shablon Slayd 8 — Xulosa.
    Shape[0]: Sarlavha (TITLE)
    Shape[1]: Xulosa matn (OBJECT idx=10)
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from lxml import etree

    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = conclusion_data.get("title", "Xulosa")
    items = conclusion_data.get("content", [])
    if isinstance(items, str):
        items = [items]

    # Shape[0]: Sarlavha
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(48)
        run.font.bold = True

    # Shape[1]: Xulosa matn
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.word_wrap = True
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=20, min_pt=13, max_pt=24)

        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)

        for item in items:
            safe_item = item.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0">'
                f'</a:rPr>'
                f'<a:t>{safe_item}</a:t></a:r></a:p>'
            )
            p_elem = etree.fromstring(p_xml)
            txBody.append(p_elem)


def generate_template_8_presentation(prs, topic, requested_slide_count, language,
                                      name_surname, plan, content_data_list, user_images=None):
    """
    8-shablon asosida to'liq prezentatsiya yaratadi.
    """
    import io

    total_content_slides = build_slide_structure_8(prs, requested_slide_count)
    plan_dict = plan if isinstance(plan, dict) else {}

    # Slayd 1 — Muqova
    fill_t8_slide_1_cover(prs.slides[0], topic, name_surname)

    # Slayd 2 — Reja
    fill_t8_slide_2_plan(prs.slides[1], plan_dict)

    # Kontent slaydlari (3-dan boshlab)
    user_img_idx = 0
    for i in range(total_content_slides):
        slide_index = i + 2
        if slide_index >= len(prs.slides) - 1:
            break

        slide = prs.slides[slide_index]
        data = content_data_list[i] if i < len(content_data_list) else {}
        image_query = data.get("image_query", topic)

        slide_type = i % 5
        if slide_type == 0:
            if user_images and user_img_idx < len(user_images):
                img_path = save_user_image_to_tmp(user_images[user_img_idx])
                user_img_idx += 1
                fill_t8_slide_3_image_right(slide, data, img_path if img_path else image_query)
            else:
                fill_t8_slide_3_image_right(slide, data)
        elif slide_type == 1:
            fill_t8_slide_4_title_left(slide, data)
        elif slide_type == 2:
            if user_images and user_img_idx < len(user_images):
                img_path = save_user_image_to_tmp(user_images[user_img_idx])
                user_img_idx += 1
                fill_t8_slide_5_image_right2(slide, data, img_path if img_path else image_query)
            else:
                fill_t8_slide_5_image_right2(slide, data)
        elif slide_type == 3:
            fill_t8_slide_6_two_cols(slide, data)
        elif slide_type == 4:
            fill_t8_slide_7_narrow_wide(slide, data)

        logging.info(f"  [T8] Slayd {slide_index + 1} to'ldirildi (tur {slide_type}): {data.get('title', '')}")

    # Xulosa slayd — GPT dan xulosa matni so'rash
    conclusion_slide = prs.slides[-1]
    conclusion_data = generate_slide_content(topic, len(prs.slides), len(prs.slides), language, is_conclusion=True)
    if not conclusion_data:
        conclusion_data = {"title": "Xulosa", "content": ["Asosiy xulosalar", "Tavsiyalar"]}
    fill_t8_slide_8_conclusion(conclusion_slide, conclusion_data)

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.read()


# ═══════════════════════════════════════════════════════════════
# TEMPLATE 9 — FUTURISTIC
# Tuzilma:
#   Slayd 1: Muqova (TITLE + SUBTITLE)
#   Slayd 2: Reja (TITLE + BODY)
#   Slayd 3: 3 ustun (3x SUBTITLE placeholder)
#   Slayd 4: Sarlavha + Rasm chap + Matn o'ng (TITLE + BODY + PICTURE)
#   Slayd 5: Sarlavha + Matn o'ng + 2 rasm (TITLE + SUBTITLE + 2xPICTURE)
#   Slayd 6: Sarlavha + Rasm o'ng + Matn chap (TITLE + SUBTITLE + PICTURE)
#   Slayd 7: Sarlavha + Matn o'ng + Rasm chap (TITLE + SUBTITLE + PICTURE)
#   Slayd 8: Xulosa (TEXT_BOX)
# ═══════════════════════════════════════════════════════════════

SLIDE_TYPE_NAMES_T9 = {
    0: "three_columns",  # Slayd 3: 3 ustun matn
    1: "image_left",     # Slayd 4: sarlavha + rasm chap + matn o'ng
    2: "two_images",     # Slayd 5: sarlavha + matn o'ng + 2 rasm
    3: "image_right",    # Slayd 6: sarlavha + rasm o'ng + matn chap
    4: "image_left2",    # Slayd 7: sarlavha + matn o'ng + rasm chap
}

CONTENT_SLIDE_TEMPLATE_INDICES_T9 = [2, 3, 4, 5, 6]  # 0-indexed: slayd 3,4,5,6,7


def build_slide_structure_9(prs, requested_content_count):
    """
    9-shablon uchun slayd tuzilmasini yaratadi.
    Muqova(1) + Reja(1) + Kontent(N) + Xulosa(1) = jami
    5 ta kontent shablon slayd bor (index 2-6), to'liq to'plamlar sifatida takrorlanadi.
    """
    n_templates = len(CONTENT_SLIDE_TEMPLATE_INDICES_T9)  # 5
    full_repeats = max(1, round(requested_content_count / n_templates))
    total_content_slides = full_repeats * n_templates
    logging.info(f"[T9] Kontent slaydlari: {requested_content_count} so'raldi, "
                 f"{full_repeats} marta takrorlanadi ({total_content_slides} ta kontent slayd)")

    conclusion_current_index = 7  # 0-indexed: slayd 8

    extra_sets_needed = full_repeats - 1
    for set_num in range(extra_sets_needed):
        for slide_template_idx in CONTENT_SLIDE_TEMPLATE_INDICES_T9:
            duplicate_slide(prs, slide_template_idx)
        logging.info(f"  [T9] {set_num + 2}-to'plam qo'shildi. Jami slaydlar: {len(prs.slides)}")

    last_index = len(prs.slides) - 1
    move_slide(prs, conclusion_current_index, last_index)
    logging.info(f"[T9] Yakuniy tuzilma: {len(prs.slides)} ta slayd")
    return total_content_slides


def fill_t9_slide_1_cover(slide, topic, name_surname):
    """
    9-Shablon Slayd 1 — Muqova.
    Shape[0]: Sarlavha (CENTER_TITLE idx=0)
    Shape[1]: Ism-familiya / Subtitle (SUBTITLE idx=1)
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN

    # Shape[0]: Sarlavha (CENTER_TITLE)
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = topic.upper() if topic else "TAQDIMOT"
        font_pt = calc_body_font_pt(len(topic), base_pt=32, min_pt=18, max_pt=40)
        run.font.size = Pt(font_pt)
        run.font.bold = True

    # Shape[1]: Ism-familiya (SUBTITLE)
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.clear()
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = name_surname if name_surname else "Taqdimot"
        run.font.size = Pt(16)


def fill_t9_slide_2_plan(slide, plan_data):
    """
    9-Shablon Slayd 2 — Reja.
    Shape[0]: Sarlavha (TITLE idx=0)
    Shape[1]: Reja matni (BODY idx=1)
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from lxml import etree

    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = plan_data.get("title", "Reja") if isinstance(plan_data, dict) else "Reja"
    items = plan_data.get("content", []) if isinstance(plan_data, dict) else []

    # Shape[0]: Sarlavha
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title.upper()
        run.font.size = Pt(28)
        run.font.bold = True

    # Shape[1]: Reja ro'yxati
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.word_wrap = True
        total_chars = sum(len(str(s)) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=18, min_pt=12, max_pt=22)

        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)

        for idx, item in enumerate(items):
            # Agar item allaqachon "1. ..." yoki "1.1 ..." formatida bo'lsa, raqamni olib tashlaymiz
            import re as _re
            clean_item = _re.sub(r'^\d+\.\s*\d*\.?\s*', '', str(item)).strip()
            safe_item = clean_item.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" b="1" dirty="0"/>'
                f'<a:t>{idx+1}. {safe_item}</a:t></a:r></a:p>'
            )
            txBody.append(etree.fromstring(p_xml))


def fill_t9_slide_3_three_cols(slide, content_data):
    """
    9-Shablon Slayd 3 — 3 ustun.
    Shape[0]: O'rta ustun (SUBTITLE idx=1)
    Shape[1]: O'ng ustun (SUBTITLE idx=3)
    Shape[2]: Chap ustun (SUBTITLE idx=5)
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from lxml import etree

    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = content_data.get("title", "")

    # GPT col1/col2/col3 formatida qaytarsa — to'g'ridan-to'g'ri ishlatamiz
    col1_raw = content_data.get("col1", "")
    col2_raw = content_data.get("col2", "")
    col3_raw = content_data.get("col3", "")

    if col1_raw or col2_raw or col3_raw:
        # col1/col2/col3 mavjud — ularni list sifatida ishlatamiz
        def split_to_sentences(text):
            """Matnni jumlalarga bo'lish"""
            import re
            if not text:
                return []
            # Jumlalarga bo'lish
            sentences = re.split(r'(?<=[.!?])\s+', str(text).strip())
            return [s.strip() for s in sentences if s.strip()]

        col1_items = split_to_sentences(col1_raw) or [str(col1_raw)]
        col2_items = split_to_sentences(col2_raw) or [str(col2_raw)]
        col3_items = split_to_sentences(col3_raw) or [str(col3_raw)]
    else:
        # content list formatida — teng 3 ga bo'lamiz
        items = content_data.get("content", [])
        if isinstance(items, str):
            items = [items]
        n = len(items)
        if n == 0:
            # Matn yo'q — sarlavhani 3 ga bo'lib yozamiz
            words = title.split() if title else ["—"]
            third = max(1, len(words) // 3)
            items = [
                " ".join(words[:third]) or "—",
                " ".join(words[third:2*third]) or "—",
                " ".join(words[2*third:]) or "—",
            ]
            n = 3
        elif n == 1:
            words = str(items[0]).split()
            third = max(1, len(words) // 3)
            items = [
                " ".join(words[:third]) or str(items[0]),
                " ".join(words[third:2*third]) or str(items[0]),
                " ".join(words[2*third:]) or str(items[0]),
            ]
            n = 3
        elif n == 2:
            items = [items[0], items[1], items[0]]
            n = 3
        base = n // 3
        rem = n % 3
        sizes = [base + (1 if i < rem else 0) for i in range(3)]
        col1_items = items[:sizes[0]]
        col2_items = items[sizes[0]:sizes[0]+sizes[1]]
        col3_items = items[sizes[0]+sizes[1]:]

    def write_col(shape, col_items, header=""):
        if shape is None or not shape.has_text_frame:
            return
        tf = shape.text_frame
        tf.word_wrap = True
        all_items = ([header] if header else []) + list(col_items)
        total_chars = sum(len(s) for s in all_items) if all_items else 10
        font_pt = calc_body_font_pt(total_chars, base_pt=14, min_pt=10, max_pt=18)

        txBody = tf._txBody
        # lstStyle tozalash (shablon indent ni olib tashlash)
        for lst in txBody.findall(f'{{{ns_a}}}lstStyle'):
            lst.clear()
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)

        if header:
            safe_h = header.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l" marL="0" indent="0"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100+200)}" b="1" dirty="0"/>'
                f'<a:t>{safe_h}</a:t></a:r></a:p>'
            )
            txBody.append(etree.fromstring(p_xml))

        for item in col_items:
            safe_item = str(item).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l" marL="0" indent="0"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0"/>'
                f'<a:t>{safe_item}</a:t></a:r></a:p>'
            )
            txBody.append(etree.fromstring(p_xml))

    # Sarlavha TextBox qo'shish (yuqori qismga, 3 ustundan yuqorida)
    if title:
        from pptx.util import Cm, Pt as _Pt
        from pptx.dml.color import RGBColor
        txBox = slide.shapes.add_textbox(Cm(2.91), Cm(0.5), Cm(19.58), Cm(2.5))
        tf_title = txBox.text_frame
        tf_title.word_wrap = True
        p_title = tf_title.paragraphs[0]
        p_title.alignment = PP_ALIGN.LEFT
        run_title = p_title.add_run()
        run_title.text = title
        run_title.font.size = _Pt(28)
        run_title.font.bold = True
        run_title.font.color.rgb = RGBColor(0xFF, 0xA5, 0x00)  # To'q sariq rang (shablon rangiga mos)

    # Shablon: Shape[2]=chap(idx=5), Shape[0]=o'rta(idx=1), Shape[1]=o'ng(idx=3)
    write_col(slide.shapes[2] if len(slide.shapes) > 2 else None, col1_items)
    write_col(slide.shapes[0] if len(slide.shapes) > 0 else None, col2_items)
    write_col(slide.shapes[1] if len(slide.shapes) > 1 else None, col3_items)


def fill_t9_slide_4_image_left(slide, content_data, image_query=None):
    """
    9-Shablon Slayd 4 — Sarlavha + Rasm chap + Matn o'ng.
    Shape[0]: Sarlavha (TITLE idx=0) — yuqori chap
    Shape[1]: Matn (BODY idx=4294967295) — o'ng
    Shape[2]: Rasm (PICTURE) — chap
    """
    from pptx.util import Pt, Cm
    from pptx.enum.text import PP_ALIGN
    from lxml import etree

    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = content_data.get("title", "")
    items = content_data.get("content", [])
    if isinstance(items, str):
        items = [items]

    # Shape[0]: Sarlavha
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(28)
        run.font.bold = True

    # Shape[1]: Matn (o'ng) - indent=0, marL=0 bilan tekis
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.word_wrap = True
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=14, min_pt=10, max_pt=18)

        txBody = tf._txBody
        # lstStyle ni ham tozalash (shablon indent ni olib tashlash)
        for lst in txBody.findall(f'{{{ns_a}}}lstStyle'):
            lst.clear()
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)

        for item in items:
            safe_item = str(item).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l" marL="0" indent="0"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0"/>'
                f'<a:t>{safe_item}</a:t></a:r></a:p>'
            )
            txBody.append(etree.fromstring(p_xml))

    # Shape[2]: Rasm (chap tomonda)
    if image_query and os.path.isfile(image_query):
        final_img_path = image_query
    else:
        query = image_query or content_data.get("image_query", title)
        final_img_path = fetch_image(query)
    if final_img_path:
        try:
            left = Cm(2.48)
            top = Cm(4.60)
            width = Cm(13.32)
            height = Cm(8.24)
            slide.shapes.add_picture(final_img_path, left, top, width, height)
            if os.path.isfile(final_img_path):
                os.remove(final_img_path)
            logging.info(f"[T9] Slayd 4 rasm joylashtirildi.")
        except Exception as e:
            logging.error(f"[T9] Slayd 4 rasm xatolik: {e}")


def fill_t9_slide_5_two_images(slide, content_data, image_query=None):
    """
    9-Shablon Slayd 5 — Sarlavha + Matn o'ng + 2 rasm.
    Shape[0]: Sarlavha (TITLE idx=0)
    Shape[1]: Matn (SUBTITLE idx=1) — o'ng
    Shape[2]: Katta rasm (PICTURE) — o'rta
    Shape[3]: Kichik rasm (PICTURE) — chap past
    """
    from pptx.util import Pt, Cm
    from pptx.enum.text import PP_ALIGN
    from lxml import etree

    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = content_data.get("title", "")
    items = content_data.get("content", [])
    if isinstance(items, str):
        items = [items]

    # Shape[0]: Sarlavha
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(28)
        run.font.bold = True

    # Shape[1]: Matn (o'ng) - indent=0, marL=0 bilan tekis
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.word_wrap = True
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=14, min_pt=10, max_pt=18)

        txBody = tf._txBody
        for lst in txBody.findall(f'{{{ns_a}}}lstStyle'):
            lst.clear()
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)

        for item in items:
            safe_item = str(item).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l" marL="0" indent="0"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0"/>'
                f'<a:t>{safe_item}</a:t></a:r></a:p>'
            )
            txBody.append(etree.fromstring(p_xml))

    # Rasm 1 (katta, o'rta — Shape[2])
    if image_query and os.path.isfile(image_query):
        final_img_path = image_query
    else:
        query = image_query or content_data.get("image_query", title)
        final_img_path = fetch_image(query)
    if final_img_path:
        try:
            left = Cm(7.91)
            top = Cm(3.41)
            width = Cm(5.88)
            height = Cm(9.73)
            slide.shapes.add_picture(final_img_path, left, top, width, height)
            if os.path.isfile(final_img_path):
                os.remove(final_img_path)
            logging.info(f"[T9] Slayd 5 katta rasm joylashtirildi.")
        except Exception as e:
            logging.error(f"[T9] Slayd 5 katta rasm xatolik: {e}")

    # Rasm 2 (kichik, chap past — Shape[3])
    img2_path = fetch_image(query if 'query' in dir() else title)
    if img2_path:
        try:
            left2 = Cm(3.40)
            top2 = Cm(6.87)
            width2 = Cm(3.07)
            height2 = Cm(5.47)
            slide.shapes.add_picture(img2_path, left2, top2, width2, height2)
            if os.path.isfile(img2_path):
                os.remove(img2_path)
            logging.info(f"[T9] Slayd 5 kichik rasm joylashtirildi.")
        except Exception as e:
            logging.error(f"[T9] Slayd 5 kichik rasm xatolik: {e}")


def fill_t9_slide_6_image_right(slide, content_data, image_query=None):
    """
    9-Shablon Slayd 6 — Sarlavha + Rasm o'ng + Matn chap.
    Shape[0]: Rasm (PICTURE) — o'ng
    Shape[1]: Sarlavha (TITLE idx=0)
    Shape[2]: Matn (SUBTITLE idx=1) — chap
    """
    from pptx.util import Pt, Cm
    from pptx.enum.text import PP_ALIGN
    from lxml import etree

    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = content_data.get("title", "")
    items = content_data.get("content", [])
    if isinstance(items, str):
        items = [items]

    # Shape[1]: Sarlavha
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(28)
        run.font.bold = True

    # Shape[2]: Matn (chap) - sarlavhadan pastga tushiriladi, indent=0
    if len(slide.shapes) > 2 and slide.shapes[2].has_text_frame:
        from pptx.util import Cm as _Cm
        slide.shapes[2].top = _Cm(4.0)
        slide.shapes[2].height = _Cm(8.5)
        tf = slide.shapes[2].text_frame
        tf.word_wrap = True
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=14, min_pt=10, max_pt=18)

        txBody = tf._txBody
        for lst in txBody.findall(f'{{{ns_a}}}lstStyle'):
            lst.clear()
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)

        for item in items:
            safe_item = str(item).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l" marL="0" indent="0"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0"/>'
                f'<a:t>{safe_item}</a:t></a:r></a:p>'
            )
            txBody.append(etree.fromstring(p_xml))

    # Shape[0]: Rasm (o'ng tomonda)
    if image_query and os.path.isfile(image_query):
        final_img_path = image_query
    else:
        query = image_query or content_data.get("image_query", title)
        final_img_path = fetch_image(query)
    if final_img_path:
        try:
            left = Cm(14.01)
            top = Cm(3.68)
            width = Cm(5.48)
            height = Cm(7.22)
            slide.shapes.add_picture(final_img_path, left, top, width, height)
            if os.path.isfile(final_img_path):
                os.remove(final_img_path)
            logging.info(f"[T9] Slayd 6 rasm joylashtirildi.")
        except Exception as e:
            logging.error(f"[T9] Slayd 6 rasm xatolik: {e}")


def fill_t9_slide_7_image_left2(slide, content_data, image_query=None):
    """
    9-Shablon Slayd 7 — Sarlavha + Matn o'ng + Rasm chap.
    Shape[0]: Matn (SUBTITLE idx=1) — o'ng
    Shape[1]: Sarlavha (TITLE idx=0)
    Shape[2]: Rasm (PICTURE) — chap
    """
    from pptx.util import Pt, Cm
    from pptx.enum.text import PP_ALIGN
    from lxml import etree

    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = content_data.get("title", "")
    items = content_data.get("content", [])
    if isinstance(items, str):
        items = [items]

    # Shape[1]: Sarlavha
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(28)
        run.font.bold = True

    # Shape[0]: Matn (o'ng) - chapga tekislangan, indent=0
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.word_wrap = True
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=14, min_pt=10, max_pt=18)

        txBody = tf._txBody
        for lst in txBody.findall(f'{{{ns_a}}}lstStyle'):
            lst.clear()
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)

        for item in items:
            safe_item = str(item).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l" marL="0" indent="0"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0"/>'
                f'<a:t>{safe_item}</a:t></a:r></a:p>'
            )
            txBody.append(etree.fromstring(p_xml))

    # Shape[2]: Rasm (chap)
    if image_query and os.path.isfile(image_query):
        final_img_path = image_query
    else:
        query = image_query or content_data.get("image_query", title)
        final_img_path = fetch_image(query)
    if final_img_path:
        try:
            left = Cm(3.39)
            top = Cm(4.69)
            width = Cm(9.22)
            height = Cm(5.59)
            slide.shapes.add_picture(final_img_path, left, top, width, height)
            if os.path.isfile(final_img_path):
                os.remove(final_img_path)
            logging.info(f"[T9] Slayd 7 rasm joylashtirildi.")
        except Exception as e:
            logging.error(f"[T9] Slayd 7 rasm xatolik: {e}")


def fill_t9_slide_8_conclusion(slide, content_data):
    """
    9-Shablon Oxirgi slayd — har doim "E'TIBORINGIZ UCHUN RAHMAT!" bilan tugaydi.
    Shape[0]: TEXT_BOX — xulosa matni
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN

    # Oxirgi slayd har doim shu matn bilan tugaydi
    text = "E'TIBORINGIZ UCHUN RAHMAT!"

    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = text
        run.font.size = Pt(32)
        run.font.bold = True


def generate_template_9_presentation(prs, topic, requested_slide_count, language,
                                      name_surname, plan, content_data_list, user_images=None):
    """
    9-shablon asosida to'liq prezentatsiya yaratadi.
    """
    import io

    total_content_slides = build_slide_structure_9(prs, requested_slide_count)
    plan_dict = plan if isinstance(plan, dict) else {}

    # Slayd 1 — Muqova
    fill_t9_slide_1_cover(prs.slides[0], topic, name_surname)

    # Slayd 2 — Reja
    fill_t9_slide_2_plan(prs.slides[1], plan_dict)

    # Kontent slaydlari (3-dan boshlab)
    user_img_idx = 0
    for i in range(total_content_slides):
        slide_index = i + 2
        if slide_index >= len(prs.slides) - 1:
            break

        slide = prs.slides[slide_index]
        data = content_data_list[i] if i < len(content_data_list) else {}
        image_query = data.get("image_query", topic)

        slide_type = i % 5
        has_image = slide_type in [1, 2, 3, 4]  # Rasm ishlatadigan slayd turlari

        if has_image:
            if user_images and user_img_idx < len(user_images):
                img_path = save_user_image_to_tmp(user_images[user_img_idx])
                user_img_idx += 1
                img_arg = img_path if img_path else image_query
            else:
                img_arg = image_query
        else:
            img_arg = None

        if slide_type == 0:
            fill_t9_slide_3_three_cols(slide, data)
        elif slide_type == 1:
            fill_t9_slide_4_image_left(slide, data, img_arg)
        elif slide_type == 2:
            fill_t9_slide_5_two_images(slide, data, img_arg)
        elif slide_type == 3:
            fill_t9_slide_6_image_right(slide, data, img_arg)
        elif slide_type == 4:
            fill_t9_slide_7_image_left2(slide, data, img_arg)

        logging.info(f"  [T9] Slayd {slide_index + 1} to'ldirildi (tur {slide_type}): {data.get('title', '')}")

    # Xulosa slayd
    conclusion_slide = prs.slides[-1]
    conclusion_data = generate_slide_content(topic, len(prs.slides), len(prs.slides), language, is_conclusion=True)
    if not conclusion_data:
        conclusion_data = {"title": "Xulosa", "content": ["Asosiy xulosalar", "Tavsiyalar"]}
    fill_t9_slide_8_conclusion(conclusion_slide, conclusion_data)

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.read()


# ═══════════════════════════════════════════════════════════════
# 10-SHABLON FUNKSIYALARI (10.pptx)
# ═══════════════════════════════════════════════════════════════
# Slayd tuzilmasi:
#   Slayd 1: TITLE         — Muqova (sarlavha + subtitle)
#   Slayd 2: TITLE_AND_BODY — Reja
#   Slayd 3: CUSTOM_10     — Sarlavha + Matn (o'ng) + Rasm (chap, to'liq)
#   Slayd 4: CUSTOM_2      — Sarlavha (chap) + 2 matn bloki (o'ng yuqori/quyi)
#   Slayd 5: CUSTOM_17     — Sarlavha + Rasm (chap) + Matn (o'ng)
#   Slayd 6: CUSTOM_18     — Sarlavha + Kichik rasm (chap) + Katta matn (o'ng)
#   Slayd 7: CUSTOM_19     — Sarlavha + Matn (chap) + Rasm (o'ng)
#   Slayd 8: Title and text 7 — Xulosa: "E'TIBORINGIZ UCHUN RAHMAT!"
# ═══════════════════════════════════════════════════════════════

SLIDE_TYPE_NAMES_T10 = {
    0: "image_left",    # Slayd 3: sarlavha + matn o'ng + rasm chap (to'liq)
    1: "two_columns",   # Slayd 4: sarlavha chap + 2 matn bloki o'ng
    2: "image_left",    # Slayd 5: sarlavha + rasm chap + matn o'ng
    3: "image_left",    # Slayd 6: sarlavha + kichik rasm chap + katta matn o'ng
    4: "image_right",   # Slayd 7: sarlavha + matn chap + rasm o'ng
}

CONTENT_SLIDE_TEMPLATE_INDICES_T10 = [2, 3, 4, 5, 6]  # 0-indexed: slayd 3,4,5,6,7


def build_slide_structure_10(prs, requested_content_count):
    """
    10-shablon uchun slayd tuzilmasini yaratadi.
    Muqova(1) + Reja(1) + Kontent(N) + Xulosa(1) = jami
    5 ta kontent shablon slayd bor (index 2-6), to'liq to'plamlar sifatida takrorlanadi.
    """
    n_templates = len(CONTENT_SLIDE_TEMPLATE_INDICES_T10)  # 5
    full_repeats = max(1, round(requested_content_count / n_templates))
    total_content_slides = full_repeats * n_templates
    logging.info(f"[T10] Kontent slaydlari: {requested_content_count} so'raldi, "
                 f"{full_repeats} marta takrorlanadi ({total_content_slides} ta kontent slayd)")

    conclusion_current_index = 7  # 0-indexed: slayd 8

    extra_sets_needed = full_repeats - 1
    for set_num in range(extra_sets_needed):
        for slide_template_idx in CONTENT_SLIDE_TEMPLATE_INDICES_T10:
            duplicate_slide(prs, slide_template_idx)
        logging.info(f"  [T10] {set_num + 2}-to'plam qo'shildi. Jami slaydlar: {len(prs.slides)}")

    last_index = len(prs.slides) - 1
    move_slide(prs, conclusion_current_index, last_index)
    logging.info(f"[T10] Yakuniy tuzilma: {len(prs.slides)} ta slayd")
    return total_content_slides


def fill_t10_slide_1_cover(slide, topic, name_surname):
    """
    10-Shablon Slayd 1 — Muqova.
    Shape[0]: Sarlavha (TITLE idx=0)
    Shape[1]: Subtitle (SUBTITLE idx=1)
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN

    # Shape[0]: Sarlavha
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = topic.upper() if topic else "TAQDIMOT"
        font_pt = calc_body_font_pt(len(topic), base_pt=36, min_pt=20, max_pt=44)
        run.font.size = Pt(font_pt)
        run.font.bold = True

    # Shape[1]: Ism-familiya
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.clear()
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = name_surname if name_surname else ""
        run.font.size = Pt(16)


def fill_t10_slide_2_plan(slide, plan_data):
    """
    10-Shablon Slayd 2 — Reja.
    Shape[0]: Sarlavha (CENTER_TITLE idx=0)
    Shape[1]: Reja matni (SUBTITLE idx=1)
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from lxml import etree

    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = plan_data.get("title", "Reja") if isinstance(plan_data, dict) else "Reja"
    items = plan_data.get("content", []) if isinstance(plan_data, dict) else []

    # Shape[0]: Sarlavha
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = "REJA"
        run.font.size = Pt(28)
        run.font.bold = True

    # Shape[1]: Reja ro'yxati
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.word_wrap = True
        total_chars = sum(len(str(s)) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=18, min_pt=12, max_pt=22)

        txBody = tf._txBody
        for lst in txBody.findall(f'{{{ns_a}}}lstStyle'):
            lst.clear()
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)

        import re as _re
        for idx, item in enumerate(items):
            clean_item = _re.sub(r'^\d+\.\s*\d*\.?\s*', '', str(item)).strip()
            safe_item = clean_item.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l" marL="0" indent="0"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" b="1" dirty="0"/>'
                f'<a:t>{idx+1}. {safe_item}</a:t></a:r></a:p>'
            )
            txBody.append(etree.fromstring(p_xml))


def fill_t10_slide_3_image_full_left(slide, content_data, image_query=None):
    """
    10-Shablon Slayd 3 (CUSTOM_10) — Sarlavha + Matn (o'ng) + Rasm (chap, to'liq balandlik).
    Shape[0]: Sarlavha (CENTER_TITLE idx=0) — o'ng yuqori
    Shape[1]: Matn (SUBTITLE idx=1) — o'ng
    Shape[2]: Rasm (PICTURE) — chap, to'liq balandlik
    """
    from pptx.util import Pt, Cm
    from pptx.enum.text import PP_ALIGN
    from lxml import etree

    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = content_data.get("title", "")
    items = content_data.get("content", [])
    if isinstance(items, str):
        items = [items]

    # Shape[0]: Sarlavha (o'ng yuqori)
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(26)
        run.font.bold = True

    # Shape[1]: Matn (o'ng)
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.word_wrap = True
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=14, min_pt=10, max_pt=18)

        txBody = tf._txBody
        for lst in txBody.findall(f'{{{ns_a}}}lstStyle'):
            lst.clear()
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)

        for item in items:
            safe_item = str(item).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l" marL="0" indent="0"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0"/>'
                f'<a:t>{safe_item}</a:t></a:r></a:p>'
            )
            txBody.append(etree.fromstring(p_xml))

    # Shape[2]: Rasm (chap, to'liq balandlik: left=-0.67cm, top=0.49cm, w=14.50cm, h=13.17cm)
    # Eski PICTURE shape larni o'chirish
    from pptx.enum.shapes import MSO_SHAPE_TYPE as _MSO
    pic_shapes = [s for s in slide.shapes if s.shape_type == _MSO.PICTURE]
    for ps in pic_shapes:
        sp = ps._element
        sp.getparent().remove(sp)
    if image_query and os.path.isfile(image_query):
        final_img_path = image_query
    else:
        query = image_query or content_data.get("image_query", title)
        final_img_path = fetch_image(query)
    if final_img_path:
        try:
            # Rasm o'ng chegarasi = matn chap chegarasi bilan bir chiziqda, 1 sm chapga surilgan
            # left = 1.8002 - 1.0 = 0.8002 cm
            left = Cm(0.8002)
            top = Cm(0.4943)
            width = Cm(8.0)
            height = Cm(13.17)
            slide.shapes.add_picture(final_img_path, left, top, width, height)
            if os.path.isfile(final_img_path):
                os.remove(final_img_path)
            logging.info(f"[T10] Slayd 3 rasm joylashtirildi.")
        except Exception as e:
            logging.error(f"[T10] Slayd 3 rasm xatolik: {e}")


def fill_t10_slide_4_two_cols(slide, content_data, image_query=None):
    """
    10-Shablon Slayd 4 (CUSTOM_2) — Sarlavha (chap markazda) + 2 matn bloki (o'ng yuqori/quyi).
    Shape[0]: Sarlavha (CENTER_TITLE idx=0) — chap, vertikal markazda
    Shape[1]: Yuqori matn bloki (SUBTITLE idx=1) — o'ng yuqori
    Shape[2]: Quyi matn bloki (SUBTITLE idx=2) — o'ng quyi
    """
    from pptx.util import Pt, Cm
    from pptx.enum.text import PP_ALIGN
    from lxml import etree

    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = content_data.get("title", "")
    col1 = content_data.get("col1", "")
    col2 = content_data.get("col2", "")
    # col1/col2 yo'q bo'lsa content dan olamiz
    items = content_data.get("content", [])
    if isinstance(items, str):
        items = [items]
    if not col1 and items:
        col1 = items[0] if len(items) > 0 else ""
    if not col2 and items:
        col2 = items[1] if len(items) > 1 else items[0] if items else ""

    # Shape[0]: Sarlavha (chap, vertikal markazda)
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(22)
        run.font.bold = True

    def write_text_block(shape, text):
        if shape is None or not shape.has_text_frame:
            return
        tf = shape.text_frame
        tf.word_wrap = True
        font_pt = calc_body_font_pt(len(str(text)), base_pt=14, min_pt=10, max_pt=16)
        txBody = tf._txBody
        for lst in txBody.findall(f'{{{ns_a}}}lstStyle'):
            lst.clear()
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)
        # Jumlalarga bo'lish
        import re as _re
        sentences = _re.split(r'(?<=[.!?])\s+', str(text).strip())
        for sentence in sentences:
            if not sentence.strip():
                continue
            safe = sentence.strip().replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l" marL="0" indent="0"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0"/>'
                f'<a:t>{safe}</a:t></a:r></a:p>'
            )
            txBody.append(etree.fromstring(p_xml))

    # Shape[1]: Yuqori matn bloki
    if len(slide.shapes) > 1:
        write_text_block(slide.shapes[1], col1)

    # Shape[2]: Quyi matn bloki
    if len(slide.shapes) > 2:
        write_text_block(slide.shapes[2], col2)


def fill_t10_slide_5_image_left(slide, content_data, image_query=None):
    """
    10-Shablon Slayd 5 (CUSTOM_17) — Sarlavha + Rasm (chap) + Matn (o'ng).
    Shape[0]: Rasm (PICTURE) — chap: left=3.27cm, top=2.80cm, w=6.92cm, h=9.19cm
    Shape[1]: Sarlavha (CENTER_TITLE idx=0) — yuqori
    Shape[2]: Matn (TEXT_BOX) — o'ng: left=12.96cm, top=3.93cm, w=10.30cm, h=9.10cm
    """
    from pptx.util import Pt, Cm
    from pptx.enum.text import PP_ALIGN
    from lxml import etree

    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = content_data.get("title", "")
    items = content_data.get("content", [])
    if isinstance(items, str):
        items = [items]

    # Shape[1]: Sarlavha
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(26)
        run.font.bold = True

    # Shape[2]: Matn (o'ng)
    if len(slide.shapes) > 2 and slide.shapes[2].has_text_frame:
        tf = slide.shapes[2].text_frame
        tf.word_wrap = True
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=14, min_pt=10, max_pt=18)

        txBody = tf._txBody
        for lst in txBody.findall(f'{{{ns_a}}}lstStyle'):
            lst.clear()
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)

        for item in items:
            safe_item = str(item).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l" marL="0" indent="0"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0"/>'
                f'<a:t>{safe_item}</a:t></a:r></a:p>'
            )
            txBody.append(etree.fromstring(p_xml))

    # Shape[0]: Rasm (chap: left=1.27cm, top=2.80cm, w=10.30cm, h=9.19cm - landscape)
    # Eski PICTURE shape larni o'chirish
    from pptx.enum.shapes import MSO_SHAPE_TYPE as _MSO
    pic_shapes = [s for s in slide.shapes if s.shape_type == _MSO.PICTURE]
    for ps in pic_shapes:
        sp = ps._element
        sp.getparent().remove(sp)
    if image_query and os.path.isfile(image_query):
        final_img_path = image_query
    else:
        query = image_query or content_data.get("image_query", title)
        final_img_path = fetch_image(query)
    if final_img_path:
        try:
            left = Cm(3.2663)
            top = Cm(2.7973)
            width = Cm(6.9250)
            height = Cm(9.1867)
            slide.shapes.add_picture(final_img_path, left, top, width, height)
            if os.path.isfile(final_img_path):
                os.remove(final_img_path)
            logging.info(f"[T10] Slayd 5 rasm joylashtirildi.")
        except Exception as e:
            logging.error(f"[T10] Slayd 5 rasm xatolik: {e}")


def fill_t10_slide_6_small_image_left(slide, content_data, image_query=None):
    """
    10-Shablon Slayd 6 (CUSTOM_18) — Sarlavha + Kichik rasm (chap) + Katta matn (o'ng).
    Shape[0]: Sarlavha (CENTER_TITLE idx=0) — yuqori
    Shape[1]: Kichik rasm (PICTURE) — chap: left=2.66cm, top=3.98cm, w=3.61cm, h=7.36cm
    Shape[2]: Katta matn (TEXT_BOX) — o'ng: left=8.46cm, top=3.34cm, w=13.28cm, h=9.28cm
    """
    from pptx.util import Pt, Cm
    from pptx.enum.text import PP_ALIGN
    from lxml import etree

    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = content_data.get("title", "")
    items = content_data.get("content", [])
    if isinstance(items, str):
        items = [items]

    # Shape[0]: Sarlavha
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(26)
        run.font.bold = True

    # Shape[2]: Katta matn (o'ng)
    if len(slide.shapes) > 2 and slide.shapes[2].has_text_frame:
        tf = slide.shapes[2].text_frame
        tf.word_wrap = True
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=14, min_pt=10, max_pt=18)

        txBody = tf._txBody
        for lst in txBody.findall(f'{{{ns_a}}}lstStyle'):
            lst.clear()
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)

        for item in items:
            safe_item = str(item).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l" marL="0" indent="0"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0"/>'
                f'<a:t>{safe_item}</a:t></a:r></a:p>'
            )
            txBody.append(etree.fromstring(p_xml))

    # Shape[1]: Rasm (chap: left=1.27cm, top=3.34cm, w=6.50cm, h=9.28cm - landscape uchun kengaytirilgan)
    # Eski PICTURE shape larni o'chirish
    from pptx.enum.shapes import MSO_SHAPE_TYPE as _MSO
    pic_shapes = [s for s in slide.shapes if s.shape_type == _MSO.PICTURE]
    for ps in pic_shapes:
        sp = ps._element
        sp.getparent().remove(sp)
    if image_query and os.path.isfile(image_query):
        final_img_path = image_query
    else:
        query = image_query or content_data.get("image_query", title)
        final_img_path = fetch_image(query)
    if final_img_path:
        try:
            left = Cm(2.6635)
            top = Cm(3.9813)
            width = Cm(3.6117)
            height = Cm(7.3583)
            slide.shapes.add_picture(final_img_path, left, top, width, height)
            if os.path.isfile(final_img_path):
                os.remove(final_img_path)
            logging.info(f"[T10] Slayd 6 rasm joylashtirildi.")
        except Exception as e:
            logging.error(f"[T10] Slayd 6 rasm xatolik: {e}")


def fill_t10_slide_7_image_right(slide, content_data, image_query=None):
    """
    10-Shablon Slayd 7 (CUSTOM_19) — Sarlavha + Matn (o'ng) + Rasm (chap).
    Shape[0]: Sarlavha (CENTER_TITLE idx=0) — yuqori
    Shape[1]: Matn (TEXT_BOX) — o'ng: left=12.70cm, top=3.39cm, w=9.88cm, h=9.22cm
    Shape[2]: Rasm (PICTURE) — chap: left=1.79cm, top=3.90cm, w=8.77cm, h=5.46cm
    """
    from pptx.util import Pt, Cm
    from pptx.enum.text import PP_ALIGN
    from lxml import etree

    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = content_data.get("title", "")
    items = content_data.get("content", [])
    if isinstance(items, str):
        items = [items]

    # Shape[0]: Sarlavha
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(26)
        run.font.bold = True

    # Shape[1]: Matn (o'ng tomonda - shablonda left=12.70)
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.word_wrap = True
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=14, min_pt=10, max_pt=18)

        txBody = tf._txBody
        for lst in txBody.findall(f'{{{ns_a}}}lstStyle'):
            lst.clear()
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)

        for item in items:
            safe_item = str(item).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l" marL="0" indent="0"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0"/>'
                f'<a:t>{safe_item}</a:t></a:r></a:p>'
            )
            txBody.append(etree.fromstring(p_xml))

    # Shape[2]: Rasm (chap tomonda: left=1.79cm, top=3.39cm, w=9.88cm, h=9.22cm)
    # Eski PICTURE shape larni o'chirish
    from pptx.enum.shapes import MSO_SHAPE_TYPE as _MSO
    pic_shapes = [s for s in slide.shapes if s.shape_type == _MSO.PICTURE]
    for ps in pic_shapes:
        sp = ps._element
        sp.getparent().remove(sp)
    if image_query and os.path.isfile(image_query):
        final_img_path = image_query
    else:
        query = image_query or content_data.get("image_query", title)
        final_img_path = fetch_image(query)
    if final_img_path:
        try:
            left = Cm(1.7895)
            top = Cm(3.9003)
            width = Cm(8.7675)
            height = Cm(5.4633)
            slide.shapes.add_picture(final_img_path, left, top, width, height)
            if os.path.isfile(final_img_path):
                os.remove(final_img_path)
            logging.info(f"[T10] Slayd 7 rasm joylashtirildi.")
        except Exception as e:
            logging.error(f"[T10] Slayd 7 rasm xatolik: {e}")


def fill_t10_slide_8_conclusion(slide, content_data):
    """
    10-Shablon Oxirgi slayd — har doim "E'TIBORINGIZ UCHUN RAHMAT!" bilan tugaydi.
    Shape[0]: CENTER_TITLE idx=0
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN

    text = "E'TIBORINGIZ UCHUN RAHMAT!"

    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = text
        run.font.size = Pt(32)
        run.font.bold = True


def generate_template_10_presentation(prs, topic, requested_slide_count, language,
                                       name_surname, plan, content_data_list, user_images=None):
    """
    10-shablon asosida to'liq prezentatsiya yaratadi.
    """
    import io

    total_content_slides = build_slide_structure_10(prs, requested_slide_count)
    plan_dict = plan if isinstance(plan, dict) else {}

    # Slayd 1 — Muqova
    fill_t10_slide_1_cover(prs.slides[0], topic, name_surname)

    # Slayd 2 — Reja
    fill_t10_slide_2_plan(prs.slides[1], plan_dict)

    # Kontent slaydlari (3-dan boshlab)
    user_img_idx = 0
    for i in range(total_content_slides):
        slide_index = i + 2
        if slide_index >= len(prs.slides) - 1:
            break

        slide = prs.slides[slide_index]
        data = content_data_list[i] if i < len(content_data_list) else {}
        image_query = data.get("image_query", topic)

        slide_type = i % 5
        has_image = slide_type in [0, 1, 2, 3, 4]  # Barcha slayd turlari rasm ishlatadi

        if has_image:
            if user_images and user_img_idx < len(user_images):
                img_path = save_user_image_to_tmp(user_images[user_img_idx])
                user_img_idx += 1
                img_arg = img_path if img_path else image_query
            else:
                img_arg = image_query
        else:
            img_arg = None

        if slide_type == 0:
            fill_t10_slide_3_image_full_left(slide, data, img_arg)
        elif slide_type == 1:
            fill_t10_slide_4_two_cols(slide, data, img_arg)
        elif slide_type == 2:
            fill_t10_slide_5_image_left(slide, data, img_arg)
        elif slide_type == 3:
            fill_t10_slide_6_small_image_left(slide, data, img_arg)
        elif slide_type == 4:
            fill_t10_slide_7_image_right(slide, data, img_arg)

        logging.info(f"  [T10] Slayd {slide_index + 1} to'ldirildi (tur {slide_type}): {data.get('title', '')}")

    # Xulosa slayd
    conclusion_slide = prs.slides[-1]
    fill_t10_slide_8_conclusion(conclusion_slide, {})

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.read()


# ═══════════════════════════════════════════════════════════════════════
# 11-SHABLON (Technology Consulting) FUNKSIYALARI
# ═══════════════════════════════════════════════════════════════════════

SLIDE_TYPE_NAMES_T11 = {
    0: "image_left",    # Slayd 4: sarlavha + rasm chap + 2 matn bloki o'ng
    1: "image_right",   # Slayd 5: sarlavha + quote chap + rasm o'ng
    2: "two_columns",   # Slayd 6: sarlavha + matn o'ng (dekorativ rasm fonda)
    3: "four_blocks",   # Slayd 7: sarlavha + 4 ta matn bloki (infografika)
    4: "image_left",    # Slayd 3: sarlavha + 2 ta matn bloki (reja uslubi)
}

CONTENT_SLIDE_TEMPLATE_INDICES_T11 = [2, 3, 4, 5, 6]  # 0-indexed: slayd 3,4,5,6,7


def build_slide_structure_11(prs, requested_content_count):
    """
    11-shablon uchun slayd tuzilmasini yaratadi.
    Muqova(1) + Reja(1) + Kontent(N) + Xulosa(1) = jami
    5 ta kontent shablon slayd bor (index 2-6), to'liq to'plamlar sifatida takrorlanadi.
    """
    n_templates = len(CONTENT_SLIDE_TEMPLATE_INDICES_T11)  # 5
    full_repeats = max(1, round(requested_content_count / n_templates))
    total_content_slides = full_repeats * n_templates
    logging.info(f"[T11] Kontent slaydlari: {requested_content_count} so'raldi, "
                 f"{full_repeats} marta takrorlanadi ({total_content_slides} ta kontent slayd)")
    conclusion_current_index = 7  # 0-indexed: slayd 8
    extra_sets_needed = full_repeats - 1
    for set_num in range(extra_sets_needed):
        for slide_template_idx in CONTENT_SLIDE_TEMPLATE_INDICES_T11:
            duplicate_slide(prs, slide_template_idx)
        logging.info(f"  [T11] {set_num + 2}-to'plam qo'shildi. Jami slaydlar: {len(prs.slides)}")
    last_index = len(prs.slides) - 1
    move_slide(prs, conclusion_current_index, last_index)
    logging.info(f"[T11] Yakuniy tuzilma: {len(prs.slides)} ta slayd")
    return total_content_slides


def fill_t11_slide_1_cover(slide, topic, name_surname):
    """
    11-Shablon Slayd 1 — Muqova.
    Shape[0]: Sarlavha (CENTER_TITLE idx=0) — o'ng yuqori
    Shape[1]: Subtitle (SUBTITLE idx=1) — o'ng pastki
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.RIGHT
        run = p.add_run()
        run.text = topic.upper() if topic else "TAQDIMOT"
        font_pt = calc_body_font_pt(len(topic), base_pt=32, min_pt=18, max_pt=40)
        run.font.size = Pt(font_pt)
        run.font.bold = True
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.clear()
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.RIGHT
        run = p.add_run()
        run.text = name_surname if name_surname else ""
        run.font.size = Pt(14)
def fill_t11_slide_2_plan(slide, plan_data):
    """
    11-Shablon Slayd 2 — Reja.
    Shape[0]: Sarlavha (TITLE idx=0)
    Shape[1]: Matn (BODY idx=1)
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from lxml import etree
    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = plan_data.get("title", "REJA")
    items = plan_data.get("content", [])
    if isinstance(items, str):
        items = [items]
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = title.upper() if title else "REJA"
        run.font.size = Pt(28)
        run.font.bold = True
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.word_wrap = True
        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)
        import re as _re
        for idx, item in enumerate(items, 1):
            # item ichida allaqachon raqam bor bo'lsa (masalan "1.1. ...") — tozalash
            item_str = str(item).strip()
            # "1.1." yoki "1." kabi boshlanishni olib tashlash
            item_str = _re.sub(r'^\d+[\d\.]*\.?\s*', '', item_str).strip()
            safe_item = item_str.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l" marL="342900" indent="-342900"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="1600" b="1" dirty="0"/>'
                f'<a:t>{idx}. {safe_item}</a:t></a:r></a:p>'
            )
            txBody.append(etree.fromstring(p_xml))
def fill_t11_slide_3_two_text(slide, content_data, image_query=None):
    """
    11-Shablon Slayd 3 (CUSTOM) — Sarlavha + 2 ta matn bloki (o'ng tekislash).
    Shape[0]: Sarlavha (TITLE idx=0): left=1.0583, top=0.8667, w=23.0928, h=1.6000
    Shape[1]: Matn blok 1 (SUBTITLE idx=2): left=4.6228, top=2.1464, w=9.8944, h=4.0725
    Shape[2]: Matn blok 2 (SUBTITLE idx=8): left=2.1476, top=7.8317, w=9.7393, h=4.7411
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from lxml import etree
    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = content_data.get("title", "")
    items = content_data.get("content", [])
    if isinstance(items, str):
        items = [items]
    # Sarlavha
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(24)
        run.font.bold = True
    # Matn blok 1 (yuqori) va 2 (pastki) — ikkalasi ham chap tekislash
    half = max(1, len(items) // 2)
    items1 = items[:half]
    items2 = items[half:]
    for shape_idx, item_list in [(1, items1), (2, items2)]:
        if len(slide.shapes) > shape_idx and slide.shapes[shape_idx].has_text_frame:
            tf = slide.shapes[shape_idx].text_frame
            tf.word_wrap = True
            total_chars = sum(len(s) for s in item_list)
            font_pt = calc_body_font_pt(total_chars, base_pt=13, min_pt=10, max_pt=16)
            txBody = tf._txBody
            for lst in txBody.findall(f'{{{ns_a}}}lstStyle'):
                lst.clear()
            for p_elem in txBody.findall(f'{{{ns_a}}}p'):
                txBody.remove(p_elem)
            for item in item_list:
                safe_item = str(item).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                p_xml = (
                    f'<a:p xmlns:a="{ns_a}">'
                    f'<a:pPr algn="l" marL="0" indent="0"><a:buNone/></a:pPr>'
                    f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0"/>'
                    f'<a:t>{safe_item}</a:t></a:r></a:p>'
                )
                txBody.append(etree.fromstring(p_xml))


def fill_t11_slide_4_image_left(slide, content_data, image_query=None):
    """
    11-Shablon Slayd 4 (TITLE_ONLY) — Sarlavha + Rasm chap + 2 matn bloki o'ng.
    Shape[0]: PICTURE: left=3.1502, top=3.8740, w=11.4259, h=7.7496
    Shape[1]: Sarlavha (TITLE idx=0): left=2.7672, top=0.9398, w=20.4439, h=1.5908
    Shape[2]: Matn o'ng pastki: left=15.1097, top=8.6434, w=7.6450, h=3.5975
    Shape[3]: Matn o'ng yuqori: left=15.1097, top=3.8740, w=7.6450, h=3.4261
    Shape[4]: Izoh pastki: left=3.4925, top=11.3438, w=10.5500, h=1.4617
    """
    from pptx.util import Pt, Cm
    from pptx.enum.text import PP_ALIGN
    from lxml import etree
    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = content_data.get("title", "")
    items = content_data.get("content", [])
    if isinstance(items, str):
        items = [items]
    # Sarlavha (Shape[1])
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(24)
        run.font.bold = True
    # Matn o'ng yuqori (Shape[3])
    half = max(1, len(items) // 2)
    items1 = items[:half]
    items2 = items[half:]
    for shape_idx, item_list in [(3, items1), (2, items2)]:
        if len(slide.shapes) > shape_idx and slide.shapes[shape_idx].has_text_frame:
            tf = slide.shapes[shape_idx].text_frame
            tf.word_wrap = True
            total_chars = sum(len(s) for s in item_list)
            font_pt = calc_body_font_pt(total_chars, base_pt=12, min_pt=9, max_pt=15)
            txBody = tf._txBody
            for lst in txBody.findall(f'{{{ns_a}}}lstStyle'):
                lst.clear()
            for p_elem in txBody.findall(f'{{{ns_a}}}p'):
                txBody.remove(p_elem)
            for item in item_list:
                safe_item = str(item).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                p_xml = (
                    f'<a:p xmlns:a="{ns_a}">'
                    f'<a:pPr algn="l" marL="0" indent="0"><a:buNone/></a:pPr>'
                    f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0"/>'
                    f'<a:t>{safe_item}</a:t></a:r></a:p>'
                )
                txBody.append(etree.fromstring(p_xml))
    # Izoh (Shape[4]) - bo'sh qilish
    if len(slide.shapes) > 4 and slide.shapes[4].has_text_frame:
        tf = slide.shapes[4].text_frame
        tf.clear()
    # Eski PICTURE shape larni o'chirish va yangi rasm qo'shish
    from pptx.enum.shapes import MSO_SHAPE_TYPE as _MSO
    pic_shapes = [s for s in slide.shapes if s.shape_type == _MSO.PICTURE]
    for ps in pic_shapes:
        sp = ps._element
        sp.getparent().remove(sp)
    if image_query and os.path.isfile(image_query):
        final_img_path = image_query
    else:
        query = image_query or content_data.get("image_query", title)
        final_img_path = fetch_image(query)
    if final_img_path:
        try:
            left = Cm(3.1502)
            top = Cm(3.8740)
            width = Cm(11.4259)
            height = Cm(7.7496)
            slide.shapes.add_picture(final_img_path, left, top, width, height)
            if os.path.isfile(final_img_path):
                os.remove(final_img_path)
            logging.info(f"[T11] Slayd 4 rasm joylashtirildi.")
        except Exception as e:
            logging.error(f"[T11] Slayd 4 rasm xatolik: {e}")


def fill_t11_slide_5_quote_image(slide, content_data, image_query=None):
    """
    11-Shablon Slayd 5 (ONE_COLUMN_TEXT) — Sarlavha + Quote chap + Rasm o'ng.
    Shape[0]: Sarlavha (TITLE idx=0): left=2.9861, top=1.9812, w=10.4369, h=1.1175
    Shape[1]: Quote/Matn (SUBTITLE idx=1): left=2.2140, top=4.8941, w=10.2588, h=6.5668
    Shape[2]: PICTURE: left=13.1851, top=1.6425, w=10.4369, h=10.4648
    """
    from pptx.util import Pt, Cm
    from pptx.enum.text import PP_ALIGN
    from lxml import etree
    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = content_data.get("title", "")
    items = content_data.get("content", [])
    if isinstance(items, str):
        items = [items]
    # col1/col2 formatidan ham matn olish (two_columns formatida kelsa)
    if not items:
        col1 = content_data.get("col1", "")
        col2 = content_data.get("col2", "")
        if col1 or col2:
            items = [x for x in [col1, col2] if x]
    # Sarlavha (Shape[0])
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(22)
        run.font.bold = True
    # Matn/Quote (Shape[1]) - placeholder idx=1
    # Barcha placeholder larni ko'rib chiqib, idx=1 ni topish
    target_shape = None
    for s in slide.shapes:
        if s.is_placeholder and s.placeholder_format.idx == 1 and s.has_text_frame:
            target_shape = s
            break
    if target_shape is None and len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        target_shape = slide.shapes[1]
    if target_shape is not None:
        tf = target_shape.text_frame
        tf.word_wrap = True
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=14, min_pt=10, max_pt=18)
        txBody = tf._txBody
        for lst in txBody.findall(f'{{{ns_a}}}lstStyle'):
            lst.clear()
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)
        for item in items:
            safe_item = str(item).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l" marL="0" indent="0"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0"/>'
                f'<a:t>{safe_item}</a:t></a:r></a:p>'
            )
            txBody.append(etree.fromstring(p_xml))
    # Eski PICTURE shape larni o'chirish va yangi rasm qo'shish (Shape[2])
    from pptx.enum.shapes import MSO_SHAPE_TYPE as _MSO
    pic_shapes = [s for s in slide.shapes if s.shape_type == _MSO.PICTURE]
    for ps in pic_shapes:
        sp = ps._element
        sp.getparent().remove(sp)
    if image_query and os.path.isfile(image_query):
        final_img_path = image_query
    else:
        query = image_query or content_data.get("image_query", title)
        final_img_path = fetch_image(query)
    if final_img_path:
        try:
            left = Cm(13.1851)
            top = Cm(1.6425)
            width = Cm(10.4369)
            height = Cm(10.4648)
            slide.shapes.add_picture(final_img_path, left, top, width, height)
            if os.path.isfile(final_img_path):
                os.remove(final_img_path)
            logging.info(f"[T11] Slayd 5 rasm joylashtirildi.")
        except Exception as e:
            logging.error(f"[T11] Slayd 5 rasm xatolik: {e}")


def fill_t11_slide_6_title_body(slide, content_data, image_query=None):
    """
    11-Shablon Slayd 6 (CUSTOM_10) — Sarlavha + Matn o'ng (dekorativ rasm fonda).
    Shape[0]: Sarlavha (TITLE idx=0): left=3.5306, top=0.9398, w=18.3642, h=1.5242
    Shape[1]: Matn (SUBTITLE idx=1): left=13.0302, top=4.1426, w=9.8808, h=7.3783
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from lxml import etree
    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = content_data.get("title", "")
    items = content_data.get("content", [])
    if isinstance(items, str):
        items = [items]
    # col1/col2 formatidan ham matn olish (two_columns formatida kelsa)
    if not items:
        col1 = content_data.get("col1", "")
        col2 = content_data.get("col2", "")
        if col1 or col2:
            items = [x for x in [col1, col2] if x]
    # Sarlavha (Shape[0])
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(26)
        run.font.bold = True
    # Matn (Shape[1])
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.word_wrap = True
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=14, min_pt=10, max_pt=18)
        txBody = tf._txBody
        for lst in txBody.findall(f'{{{ns_a}}}lstStyle'):
            lst.clear()
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)
        for item in items:
            safe_item = str(item).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l" marL="0" indent="0"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0"/>'
                f'<a:t>{safe_item}</a:t></a:r></a:p>'
            )
            txBody.append(etree.fromstring(p_xml))


def fill_t11_slide_7_four_blocks(slide, content_data, image_query=None):
    """
    11-Shablon Slayd 7 (CUSTOM_15) — Sarlavha + 2 ta matn bloki (chap va o'ng).
    Faqat 2 ta matn bloki ishlatiladi: chap va o'ng.
    Bo'sh 2 ta blok (pastki) o'chiriladi, matn joylashgan 2 ta blok 3sm pastga siljiydi.
    Shape[0]: Sarlavha (TITLE idx=0): left=1.0372, top=1.4637, w=23.5797, h=1.5908
    Shape[1]: Blok 1 chap (SUBTITLE idx=2): left=2.2733, top=4.5665 -> 7.5665, w=6.3651, h=3.1115
    Shape[2]: Blok 2 chap pastki (SUBTITLE idx=3): O'CHIRILADI
    Shape[3]: Blok 3 o'ng (SUBTITLE idx=5): left=17.0245, top=4.5665 -> 7.5665, w=6.3651, h=3.1115
    Shape[4]: Blok 4 o'ng pastki (SUBTITLE idx=7): O'CHIRILADI
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from lxml import etree
    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    title = content_data.get("title", "")
    items = content_data.get("content", [])
    if isinstance(items, str):
        items = [items]
    # Sarlavha (Shape[0])
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = title
        run.font.size = Pt(26)
        run.font.bold = True
    from pptx.util import Cm, Emu
    # Pastki 2 ta blokni (Shape[2] idx=3 va Shape[4] idx=7) o'chirish
    # Placeholder idx=3 va idx=7 ni topib o'chirish
    shapes_to_remove = []
    for s in slide.shapes:
        if s.is_placeholder and s.placeholder_format.idx in [3, 7]:
            shapes_to_remove.append(s)
    for s in shapes_to_remove:
        sp = s._element
        sp.getparent().remove(sp)
    # Yuqori 2 ta blokni (idx=2 va idx=5) 3sm pastga siljitish
    # va matn yozish
    # Chap blok (idx=2) va o'ng blok (idx=5)
    shift_emu = int(3.0 * 914400 / 2.54)  # 3sm EMU ga
    left_items = items[:max(1, len(items)//2)] if items else []
    right_items = items[max(1, len(items)//2):] if len(items) > 1 else []
    for s in slide.shapes:
        if not s.is_placeholder:
            continue
        ph_idx = s.placeholder_format.idx
        if ph_idx == 2:  # Chap yuqori blok
            # 3sm pastga siljitish
            s.top = s.top + shift_emu
            # Matn yozish
            if s.has_text_frame:
                tf = s.text_frame
                tf.word_wrap = True
                total_chars = sum(len(x) for x in left_items)
                font_pt = calc_body_font_pt(total_chars, base_pt=13, min_pt=10, max_pt=16)
                txBody = tf._txBody
                for lst in txBody.findall(f'{{{ns_a}}}lstStyle'):
                    lst.clear()
                for p_elem in txBody.findall(f'{{{ns_a}}}p'):
                    txBody.remove(p_elem)
                for item in left_items:
                    safe_item = str(item).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    p_xml = (
                        f'<a:p xmlns:a="{ns_a}">'
                        f'<a:pPr algn="l" marL="0" indent="0"><a:buNone/></a:pPr>'
                        f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0"/>'
                        f'<a:t>{safe_item}</a:t></a:r></a:p>'
                    )
                    txBody.append(etree.fromstring(p_xml))
        elif ph_idx == 5:  # O'ng yuqori blok
            # 3sm pastga siljitish
            s.top = s.top + shift_emu
            # Matn yozish
            if s.has_text_frame:
                tf = s.text_frame
                tf.word_wrap = True
                total_chars = sum(len(x) for x in right_items)
                font_pt = calc_body_font_pt(total_chars, base_pt=13, min_pt=10, max_pt=16)
                txBody = tf._txBody
                for lst in txBody.findall(f'{{{ns_a}}}lstStyle'):
                    lst.clear()
                for p_elem in txBody.findall(f'{{{ns_a}}}p'):
                    txBody.remove(p_elem)
                for item in right_items:
                    safe_item = str(item).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    p_xml = (
                        f'<a:p xmlns:a="{ns_a}">'
                        f'<a:pPr algn="l" marL="0" indent="0"><a:buNone/></a:pPr>'
                        f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" dirty="0"/>'
                        f'<a:t>{safe_item}</a:t></a:r></a:p>'
                    )
                    txBody.append(etree.fromstring(p_xml))


def fill_t11_slide_8_conclusion(slide, content_data):
    """
    11-Shablon Oxirgi slayd — "E'TIBORINGIZ UCHUN RAHMAT!" bilan tugaydi.
    Shape[0]: Sarlavha (TITLE idx=0): left=5.6698, top=5.0333, w=13.7417, h=3.8463
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.clear()
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = "E'TIBORINGIZ UCHUN RAHMAT!"
        run.font.size = Pt(32)
        run.font.bold = True


def generate_template_11_presentation(prs, topic, requested_slide_count, language,
                                       name_surname, plan, content_data_list, user_images=None):
    """
    11-shablon asosida to'liq prezentatsiya yaratadi.
    """
    import io
    total_content_slides = build_slide_structure_11(prs, requested_slide_count)
    plan_dict = plan if isinstance(plan, dict) else {}
    # Slayd 1 — Muqova
    fill_t11_slide_1_cover(prs.slides[0], topic, name_surname)
    # Slayd 2 — Reja
    fill_t11_slide_2_plan(prs.slides[1], plan_dict)
    # Kontent slaydlari (3-dan boshlab)
    user_img_idx = 0
    # Slayd turlari: 0=slayd3(two_text), 1=slayd4(image_left), 2=slayd5(quote+image),
    #                3=slayd6(title+body), 4=slayd7(four_blocks)
    IMAGE_SLIDE_TYPES = [1, 2]  # Faqat slayd4 va slayd5 da rasm bor
    for i in range(total_content_slides):
        slide_index = i + 2
        if slide_index >= len(prs.slides) - 1:
            break
        slide = prs.slides[slide_index]
        data = content_data_list[i] if i < len(content_data_list) else {}
        image_query = data.get("image_query", topic)
        slide_type = i % 5
        has_image = slide_type in IMAGE_SLIDE_TYPES
        if has_image:
            if user_images and user_img_idx < len(user_images):
                img_path = save_user_image_to_tmp(user_images[user_img_idx])
                user_img_idx += 1
                img_arg = img_path if img_path else image_query
            else:
                img_arg = image_query
        else:
            img_arg = None
        if slide_type == 0:
            fill_t11_slide_3_two_text(slide, data, img_arg)
        elif slide_type == 1:
            fill_t11_slide_4_image_left(slide, data, img_arg)
        elif slide_type == 2:
            fill_t11_slide_5_quote_image(slide, data, img_arg)
        elif slide_type == 3:
            fill_t11_slide_6_title_body(slide, data, img_arg)
        elif slide_type == 4:
            fill_t11_slide_7_four_blocks(slide, data, img_arg)
        logging.info(f"  [T11] Slayd {slide_index + 1} to'ldirildi (tur {slide_type}): {data.get('title', '')}")
    # Xulosa slayd
    conclusion_slide = prs.slides[-1]
    fill_t11_slide_8_conclusion(conclusion_slide, {})
    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.read()


# ============================================================
# 12-SHABLON (AESTHETIC / BOTANICAL)
# ============================================================

SLIDE_TYPE_NAMES_T12 = {
    0: "one_column",      # Slayd 3: sarlavha + bitta katta matn bloki (chap), dekor o'ng
    1: "image_left",      # Slayd 4: sarlavha + rasm chap (freeform), matn o'ng
    2: "two_columns",     # Slayd 5: sarlavha + 2 ta ustun matni
    3: "three_columns",   # Slayd 6: sarlavha + 3 ta ustun matni
    4: "image_right",     # Slayd 7: sarlavha + matn chap, rasm o'ng (freeform)
}
CONTENT_SLIDE_TEMPLATE_INDICES_T12 = [2, 3, 4, 5, 6]  # 0-indexed: slayd 3,4,5,6,7


def build_slide_structure_12(prs, requested_content_count):
    """
    12-shablon uchun slayd tuzilmasini yaratadi.
    Muqova(1) + Reja(1) + Kontent(N) + Xulosa(1) = jami
    5 ta kontent shablon slayd bor (index 2-6), to'liq to'plamlar sifatida takrorlanadi.
    """
    n_templates = len(CONTENT_SLIDE_TEMPLATE_INDICES_T12)  # 5
    full_repeats = max(1, round(requested_content_count / n_templates))
    total_content_slides = full_repeats * n_templates
    logging.info(f"[T12] Kontent slaydlari: {requested_content_count} so'raldi, "
                 f"{full_repeats} marta takrorlanadi ({total_content_slides} ta kontent slayd)")
    conclusion_current_index = 7  # 0-indexed: slayd 8
    extra_sets_needed = full_repeats - 1
    for set_num in range(extra_sets_needed):
        for slide_template_idx in CONTENT_SLIDE_TEMPLATE_INDICES_T12:
            duplicate_slide(prs, slide_template_idx)
        logging.info(f"  [T12] {set_num + 2}-to'plam qo'shildi. Jami slaydlar: {len(prs.slides)}")
    last_index = len(prs.slides) - 1
    move_slide(prs, conclusion_current_index, last_index)
    logging.info(f"[T12] Yakuniy tuzilma: {len(prs.slides)} ta slayd")
    return total_content_slides


def fill_t12_slide_1_cover(slide, topic, name_surname):
    """
    12-Shablon Slayd 1 — Muqova.
    Shape[0]: Sarlavha (TextBox 9): left=4.8683, top=4.1275, w=39.5817, h=2.5648
    Shape[1]: Ism-familiya (TextBox 11): left=15.4517, top=23.6008, w=20.1083, h=3.9683
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from lxml import etree
    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'

    # Sarlavha (Shape[0])
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.word_wrap = True
        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)
        title_text = topic.upper() if topic else "TAQDIMOT"
        font_pt = calc_body_font_pt(len(title_text), base_pt=36, min_pt=22, max_pt=48)
        safe_t = title_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        p_xml = (
            f'<a:p xmlns:a="{ns_a}">'
            f'<a:pPr algn="ctr"><a:buNone/></a:pPr>'
            f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" b="0" dirty="0"/>'
            f'<a:t>{safe_t}</a:t></a:r></a:p>'
        )
        txBody.append(etree.fromstring(p_xml))

    # Ism-familiya (Shape[1])
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.word_wrap = True
        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)
        name_text = name_surname if name_surname else ""
        safe_n = name_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        p_xml = (
            f'<a:p xmlns:a="{ns_a}">'
            f'<a:pPr algn="ctr"><a:buNone/></a:pPr>'
            f'<a:r><a:rPr lang="uz-UZ" sz="1600" b="1" dirty="0"/>'
            f'<a:t>{safe_n}</a:t></a:r></a:p>'
        )
        txBody.append(etree.fromstring(p_xml))


def fill_t12_slide_2_plan(slide, plan_dict):
    """
    12-Shablon Slayd 2 — Reja.
    Shape[0]: 'REJA' sarlavhasi (TextBox 7): left=13.2582, top=3.7379, w=23.2461, h=3.1273
    Shape[1]: Reja matni (TextBox 8): left=12.5349, top=11.2022, w=28.5284, h=8.2690
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from lxml import etree
    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'

    # Sarlavha (Shape[0]) - "REJA" deb qoladi
    # Shape[1] - reja ro'yxati
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.word_wrap = True
        txBody = tf._txBody
        for lst in txBody.findall(f'{{{ns_a}}}lstStyle'):
            lst.clear()
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)

        items = []
        if isinstance(plan_dict, dict):
            for k, v in plan_dict.items():
                items.append(str(v) if v else str(k))
        elif isinstance(plan_dict, list):
            items = [str(x) for x in plan_dict]

        # Raqamlarni tozalab, faqat "1." "2." formatda yozish
        import re
        clean_items = []
        for item in items:
            cleaned = re.sub(r'^\s*[\d]+[\.\:\)]+\s*[\d]*[\.\:\)]*\s*', '', str(item)).strip()
            if cleaned:
                clean_items.append(cleaned)

        font_pt = calc_body_font_pt(sum(len(x) for x in clean_items), base_pt=18, min_pt=12, max_pt=22)
        for idx, item in enumerate(clean_items):
            safe_item = item.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l" marL="457200" indent="-457200"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" b="1" dirty="0"/>'
                f'<a:t>{idx+1}. {safe_item}</a:t></a:r></a:p>'
            )
            txBody.append(etree.fromstring(p_xml))


def fill_t12_slide_3_text_left(slide, content_data, image_query=None):
    """
    12-Shablon Slayd 3 — Sarlavha + Matn chap, Dekor o'ng.
    Shape[0]: Freeform 6 (dekor, saqlanadi): left=31.54, top=4.53, w=13.61, h=19.62
    Shape[1]: Asosiy matn (TextBox 7): left=3.6287, top=8.7081, w=22.4063, h=8.8589
    Shape[2]: Sarlavha (TextBox 8): left=4.2333, top=2.4342, w=27.3067, h=2.0518
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from lxml import etree
    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'

    title = content_data.get("title", "")
    items = content_data.get("content", [])
    if isinstance(items, str):
        items = [items]
    if not items:
        col1 = content_data.get("col1", "")
        col2 = content_data.get("col2", "")
        items = [x for x in [col1, col2] if x]

    # Sarlavha (Shape[2])
    if len(slide.shapes) > 2 and slide.shapes[2].has_text_frame:
        tf = slide.shapes[2].text_frame
        tf.word_wrap = True
        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)
        safe_t = title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        p_xml = (
            f'<a:p xmlns:a="{ns_a}">'
            f'<a:pPr algn="l"><a:buNone/></a:pPr>'
            f'<a:r><a:rPr lang="uz-UZ" sz="2800" b="0" dirty="0"/>'
            f'<a:t>{safe_t.upper()}</a:t></a:r></a:p>'
        )
        txBody.append(etree.fromstring(p_xml))

    # Asosiy matn (Shape[1])
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.word_wrap = True
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=16, min_pt=11, max_pt=20)
        txBody = tf._txBody
        for lst in txBody.findall(f'{{{ns_a}}}lstStyle'):
            lst.clear()
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)
        for item in items:
            safe_item = str(item).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l" marL="0" indent="0"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" b="1" dirty="0"/>'
                f'<a:t>{safe_item}</a:t></a:r></a:p>'
            )
            txBody.append(etree.fromstring(p_xml))


def fill_t12_slide_4_image_left(slide, content_data, image_query=None):
    """
    12-Shablon Slayd 4 — Rasm chap (freeform joyi), Sarlavha + Matn o'ng.
    Shape[0]: Matn (TextBox 4): left=20.8298, top=8.7842, w=21.7713, h=8.2820
    Shape[1]: Sarlavha (TextBox 7): left=20.8298, top=1.7992, w=28.7497, h=2.7839
    Shape[2]: Freeform 7 (rasm joyi): left=2.4466, top=4.5255, w=14.6104, h=21.0707
    """
    from pptx.util import Pt, Cm
    from pptx.enum.text import PP_ALIGN
    from lxml import etree
    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'

    title = content_data.get("title", "")
    items = content_data.get("content", [])
    if isinstance(items, str):
        items = [items]
    if not items:
        col1 = content_data.get("col1", "")
        col2 = content_data.get("col2", "")
        items = [x for x in [col1, col2] if x]

    # Sarlavha (Shape[1])
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.word_wrap = True
        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)
        safe_t = title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        p_xml = (
            f'<a:p xmlns:a="{ns_a}">'
            f'<a:pPr algn="l"><a:buNone/></a:pPr>'
            f'<a:r><a:rPr lang="uz-UZ" sz="2800" b="0" dirty="0"/>'
            f'<a:t>{safe_t.upper()}</a:t></a:r></a:p>'
        )
        txBody.append(etree.fromstring(p_xml))

    # Asosiy matn (Shape[0])
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.word_wrap = True
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=16, min_pt=11, max_pt=20)
        txBody = tf._txBody
        for lst in txBody.findall(f'{{{ns_a}}}lstStyle'):
            lst.clear()
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)
        for item in items:
            safe_item = str(item).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l" marL="0" indent="0"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" b="1" dirty="0"/>'
                f'<a:t>{safe_item}</a:t></a:r></a:p>'
            )
            txBody.append(etree.fromstring(p_xml))

    # Rasm (Shape[2] — freeform joyi o'chirib, rasm qo'yish)
    if image_query:
        img_data = fetch_image(image_query) if isinstance(image_query, str) and not image_query.endswith(('.jpg', '.jpeg', '.png', '.webp')) else None
        if img_data is None and isinstance(image_query, str) and image_query.endswith(('.jpg', '.jpeg', '.png', '.webp')):
            try:
                with open(image_query, 'rb') as f:
                    img_data = f.read()
            except Exception:
                img_data = None
        if img_data:
            try:
                from pptx.util import Cm
                import io as _io
                # Freeform ni o'chirish
                freeform_shape = slide.shapes[2]
                left = freeform_shape.left
                top = freeform_shape.top
                width = freeform_shape.width
                height = freeform_shape.height
                sp = freeform_shape._element
                sp.getparent().remove(sp)
                # Yangi rasm qo'shish
                img_stream = _io.BytesIO(img_data)
                slide.shapes.add_picture(img_stream, left, top, width, height)
            except Exception as e:
                logging.warning(f"[T12] Slayd 4 rasm qo'shishda xatolik: {e}")


def fill_t12_slide_5_two_columns(slide, content_data, image_query=None):
    """
    12-Shablon Slayd 5 — Sarlavha + 2 ta ustun matni.
    Shape[0]: Sarlavha (TextBox 4): left=1.4817, top=2.0108, w=47.6250, h=3.0537
    Shape[1]: Chap ustun (TextBox 9): left=5.7150, top=9.9564, w=17.3567, h=14.4911
    Shape[2]: O'ng ustun (TextBox 10): left=27.1445, top=9.9564, w=17.3567, h=14.4911
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from lxml import etree
    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'

    title = content_data.get("title", "")
    col1 = content_data.get("col1", "")
    col2 = content_data.get("col2", "")
    # content formatidan ham olish
    if not col1 and not col2:
        items = content_data.get("content", [])
        if isinstance(items, list) and len(items) >= 2:
            col1 = items[0]
            col2 = items[1]
        elif isinstance(items, list) and len(items) == 1:
            col1 = items[0]
        elif isinstance(items, str):
            col1 = items

    # Sarlavha (Shape[0])
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.word_wrap = True
        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)
        safe_t = title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        p_xml = (
            f'<a:p xmlns:a="{ns_a}">'
            f'<a:pPr algn="ctr"><a:buNone/></a:pPr>'
            f'<a:r><a:rPr lang="uz-UZ" sz="3600" b="0" dirty="0"/>'
            f'<a:t>{safe_t.upper()}</a:t></a:r></a:p>'
        )
        txBody.append(etree.fromstring(p_xml))

    def write_col(shape, text):
        if not shape.has_text_frame:
            return
        tf = shape.text_frame
        tf.word_wrap = True
        font_pt = calc_body_font_pt(len(str(text)), base_pt=16, min_pt=11, max_pt=20)
        txBody = tf._txBody
        for lst in txBody.findall(f'{{{ns_a}}}lstStyle'):
            lst.clear()
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)
        safe_text = str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        p_xml = (
            f'<a:p xmlns:a="{ns_a}">'
            f'<a:pPr algn="ctr" marL="0" indent="0"><a:buNone/></a:pPr>'
            f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" b="1" dirty="0"/>'
            f'<a:t>{safe_text}</a:t></a:r></a:p>'
        )
        txBody.append(etree.fromstring(p_xml))

    if len(slide.shapes) > 1:
        write_col(slide.shapes[1], col1)
    if len(slide.shapes) > 2:
        write_col(slide.shapes[2], col2)


def fill_t12_slide_6_three_columns(slide, content_data, image_query=None):
    """
    12-Shablon Slayd 6 — Sarlavha + 3 ta ustun matni.
    Shape[0]: Sarlavha (TextBox 3): left=2.3283, top=2.0108, w=46.1306, h=3.0537
    Shape[1]: Chap ustun (TextBox 7): left=2.3410, top=10.8201, w=13.7583, h=13.8391
    Shape[2]: Markaz ustun (TextBox 8): left=18.5272, top=10.8201, w=13.7583, h=13.8391
    Shape[3]: O'ng ustun (TextBox 9): left=34.7133, top=10.8201, w=13.7583, h=13.8391
    """
    from pptx.util import Pt
    from pptx.enum.text import PP_ALIGN
    from lxml import etree
    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'

    title = content_data.get("title", "")
    col1 = content_data.get("col1", "")
    col2 = content_data.get("col2", "")
    col3 = content_data.get("col3", "")
    # content formatidan ham olish
    if not col1 and not col2 and not col3:
        items = content_data.get("content", [])
        if isinstance(items, list):
            if len(items) >= 3:
                col1, col2, col3 = items[0], items[1], items[2]
            elif len(items) == 2:
                col1, col2 = items[0], items[1]
            elif len(items) == 1:
                col1 = items[0]
        elif isinstance(items, str):
            col1 = items

    # Sarlavha (Shape[0])
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.word_wrap = True
        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)
        safe_t = title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        p_xml = (
            f'<a:p xmlns:a="{ns_a}">'
            f'<a:pPr algn="ctr"><a:buNone/></a:pPr>'
            f'<a:r><a:rPr lang="uz-UZ" sz="3600" b="0" dirty="0"/>'
            f'<a:t>{safe_t.upper()}</a:t></a:r></a:p>'
        )
        txBody.append(etree.fromstring(p_xml))

    def write_col(shape, text):
        if not shape.has_text_frame:
            return
        tf = shape.text_frame
        tf.word_wrap = True
        font_pt = calc_body_font_pt(len(str(text)), base_pt=14, min_pt=10, max_pt=18)
        txBody = tf._txBody
        for lst in txBody.findall(f'{{{ns_a}}}lstStyle'):
            lst.clear()
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)
        safe_text = str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        p_xml = (
            f'<a:p xmlns:a="{ns_a}">'
            f'<a:pPr algn="ctr" marL="0" indent="0"><a:buNone/></a:pPr>'
            f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" b="1" dirty="0"/>'
            f'<a:t>{safe_text}</a:t></a:r></a:p>'
        )
        txBody.append(etree.fromstring(p_xml))

    if len(slide.shapes) > 1:
        write_col(slide.shapes[1], col1)
    if len(slide.shapes) > 2:
        write_col(slide.shapes[2], col2)
    if len(slide.shapes) > 3:
        write_col(slide.shapes[3], col3)


def fill_t12_slide_7_image_right(slide, content_data, image_query=None):
    """
    12-Shablon Slayd 7 — Sarlavha + Matn chap, Rasm o'ng (freeform joyi).
    Shape[0]: Asosiy matn (TextBox 8): left=3.1536, top=9.1234, w=32.1115, h=4.1142
    Shape[1]: Sarlavha (TextBox 13): left=1.8748, top=1.8032, w=38.5536, h=3.0537
    Shape[2]: Freeform 10 (rasm joyi): left=35.6092, top=8.4048, w=13.1186, h=18.9191
    """
    from pptx.util import Pt, Cm
    from pptx.enum.text import PP_ALIGN
    from lxml import etree
    ns_a = 'http://schemas.openxmlformats.org/drawingml/2006/main'

    title = content_data.get("title", "")
    items = content_data.get("content", [])
    if isinstance(items, str):
        items = [items]
    if not items:
        col1 = content_data.get("col1", "")
        col2 = content_data.get("col2", "")
        items = [x for x in [col1, col2] if x]

    # Sarlavha (Shape[1])
    if len(slide.shapes) > 1 and slide.shapes[1].has_text_frame:
        tf = slide.shapes[1].text_frame
        tf.word_wrap = True
        txBody = tf._txBody
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)
        safe_t = title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        p_xml = (
            f'<a:p xmlns:a="{ns_a}">'
            f'<a:pPr algn="l"><a:buNone/></a:pPr>'
            f'<a:r><a:rPr lang="uz-UZ" sz="2800" b="0" dirty="0"/>'
            f'<a:t>{safe_t.upper()}</a:t></a:r></a:p>'
        )
        txBody.append(etree.fromstring(p_xml))

    # Asosiy matn (Shape[0])
    if len(slide.shapes) > 0 and slide.shapes[0].has_text_frame:
        tf = slide.shapes[0].text_frame
        tf.word_wrap = True
        total_chars = sum(len(s) for s in items)
        font_pt = calc_body_font_pt(total_chars, base_pt=16, min_pt=11, max_pt=20)
        txBody = tf._txBody
        for lst in txBody.findall(f'{{{ns_a}}}lstStyle'):
            lst.clear()
        for p_elem in txBody.findall(f'{{{ns_a}}}p'):
            txBody.remove(p_elem)
        for item in items:
            safe_item = str(item).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            p_xml = (
                f'<a:p xmlns:a="{ns_a}">'
                f'<a:pPr algn="l" marL="0" indent="0"><a:buNone/></a:pPr>'
                f'<a:r><a:rPr lang="uz-UZ" sz="{int(font_pt*100)}" b="1" dirty="0"/>'
                f'<a:t>{safe_item}</a:t></a:r></a:p>'
            )
            txBody.append(etree.fromstring(p_xml))

    # Rasm (Shape[2] — freeform joyi o'chirib, rasm qo'yish)
    if image_query:
        img_data = fetch_image(image_query) if isinstance(image_query, str) and not image_query.endswith(('.jpg', '.jpeg', '.png', '.webp')) else None
        if img_data is None and isinstance(image_query, str) and image_query.endswith(('.jpg', '.jpeg', '.png', '.webp')):
            try:
                with open(image_query, 'rb') as f:
                    img_data = f.read()
            except Exception:
                img_data = None
        if img_data:
            try:
                import io as _io
                freeform_shape = slide.shapes[2]
                left = freeform_shape.left
                top = freeform_shape.top
                width = freeform_shape.width
                height = freeform_shape.height
                sp = freeform_shape._element
                sp.getparent().remove(sp)
                img_stream = _io.BytesIO(img_data)
                slide.shapes.add_picture(img_stream, left, top, width, height)
            except Exception as e:
                logging.warning(f"[T12] Slayd 7 rasm qo'shishda xatolik: {e}")


def fill_t12_slide_8_conclusion(slide, content_data):
    """
    12-Shablon Slayd 8 — Xulosa.
    Shape[0]: Markaziy matn (TextBox 9): left=7.3293, top=9.4342, w=36.1414, h=6.8395
    """
    # Xulosa slaydida matn o'zgarmaydi - shablon matni saqlanadi
    pass


def generate_template_12_presentation(prs, topic, requested_slide_count, language,
                                       name_surname, plan, content_data_list, user_images=None):
    """
    12-shablon asosida to'liq prezentatsiya yaratadi.
    """
    import io
    total_content_slides = build_slide_structure_12(prs, requested_slide_count)
    plan_dict = plan if isinstance(plan, dict) else {}
    # Slayd 1 — Muqova
    fill_t12_slide_1_cover(prs.slides[0], topic, name_surname)
    # Slayd 2 — Reja
    fill_t12_slide_2_plan(prs.slides[1], plan_dict)
    # Kontent slaydlari (3-dan boshlab)
    user_img_idx = 0
    # Rasm ishlatadigan slayd turlari: 1=slayd4(image_left), 4=slayd7(image_right)
    IMAGE_SLIDE_TYPES = [1, 4]
    for i in range(total_content_slides):
        slide_index = i + 2
        if slide_index >= len(prs.slides) - 1:
            break
        slide = prs.slides[slide_index]
        data = content_data_list[i] if i < len(content_data_list) else {}
        image_query = data.get("image_query", topic)
        slide_type = i % 5
        has_image = slide_type in IMAGE_SLIDE_TYPES
        if has_image:
            if user_images and user_img_idx < len(user_images):
                img_path = save_user_image_to_tmp(user_images[user_img_idx])
                user_img_idx += 1
                img_arg = img_path if img_path else image_query
            else:
                img_arg = image_query
        else:
            img_arg = None
        if slide_type == 0:
            fill_t12_slide_3_text_left(slide, data, img_arg)
        elif slide_type == 1:
            fill_t12_slide_4_image_left(slide, data, img_arg)
        elif slide_type == 2:
            fill_t12_slide_5_two_columns(slide, data, img_arg)
        elif slide_type == 3:
            fill_t12_slide_6_three_columns(slide, data, img_arg)
        elif slide_type == 4:
            fill_t12_slide_7_image_right(slide, data, img_arg)
        logging.info(f"  [T12] Slayd {slide_index + 1} to'ldirildi (tur {slide_type}): {data.get('title', '')}")
    # Xulosa slayd
    conclusion_slide = prs.slides[-1]
    fill_t12_slide_8_conclusion(conclusion_slide, {})
    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.read()
