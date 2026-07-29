import json
import logging
import os
import asyncio
from io import BytesIO
import random
import db
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes, ConversationHandler
from utils import (
    generate_presentation,
    generate_template_1_presentation,
    generate_template_2_presentation,
    generate_template_3_presentation,
    generate_template_4_presentation,
    generate_template_5_presentation,
    generate_template_6_presentation,
    generate_template_7_presentation,
    generate_template_8_presentation,
    generate_template_9_presentation,
    generate_template_10_presentation,
    generate_template_11_presentation,
    generate_template_12_presentation,
    generate_template_13_presentation,
    generate_template_14_presentation,
    generate_template_15_presentation,
    generate_template_16_presentation,
    generate_template_17_presentation,
    generate_template_18_presentation,
    generate_template_19_presentation,
    generate_template_20_presentation,
    generate_template_21_presentation,
    generate_template_22_presentation,
    generate_template_23_presentation,
    generate_template_24_presentation,
    generate_template_25_presentation,
    generate_template_26_presentation,
    generate_template_27_presentation,
    generate_template_28_presentation,
    generate_template_29_presentation,
    generate_template_30_presentation,
    generate_template_31_presentation,
    generate_template_32_presentation,
    generate_template_33_presentation,
    generate_plan_with_titles,
    generate_all_content,
    fetch_image_preview_urls,
    save_user_image_to_tmp,
    SLIDE_TYPE_NAMES,
    SLIDE_TYPE_NAMES_T3,
    SLIDE_TYPE_NAMES_T4,
    SLIDE_TYPE_NAMES_T5,
    SLIDE_TYPE_NAMES_T6,
    SLIDE_TYPE_NAMES_T7,
    SLIDE_TYPE_NAMES_T8,
    SLIDE_TYPE_NAMES_T9,
    SLIDE_TYPE_NAMES_T10,
    SLIDE_TYPE_NAMES_T11,
    SLIDE_TYPE_NAMES_T12,
    SLIDE_TYPE_NAMES_T13,
    SLIDE_TYPE_NAMES_T14,
    SLIDE_TYPE_NAMES_T15,
    SLIDE_TYPE_NAMES_T16,
    SLIDE_TYPE_NAMES_T17,
    SLIDE_TYPE_NAMES_T18,
    SLIDE_TYPE_NAMES_T19,
    SLIDE_TYPE_NAMES_T20,
    SLIDE_TYPE_NAMES_T21,
    SLIDE_TYPE_NAMES_T22,
    SLIDE_TYPE_NAMES_T23,
    SLIDE_TYPE_NAMES_T24,
    SLIDE_TYPE_NAMES_T25,
    SLIDE_TYPE_NAMES_T26,
    SLIDE_TYPE_NAMES_T27,
    SLIDE_TYPE_NAMES_T28,
    SLIDE_TYPE_NAMES_T29,
    SLIDE_TYPE_NAMES_T30,
    SLIDE_TYPE_NAMES_T31,
    SLIDE_TYPE_NAMES_T32,
    SLIDE_TYPE_NAMES_T33,
)
from mustaqil_ish_utils import generate_mustaqil_ish
from loyiha_ishi_utils import generate_loyiha_ishi
from infografika_utils import generate_infografika, generate_infografika_hd
from maqola_utils import generate_maqola
from kurs_ishi_utils import generate_kurs_ishi
from tezis_utils import generate_tezis
from glossary_utils import generate_glossary, GLOSSARY_SIZES
from test_utils import generate_test
from crossword_utils import generate_crossword, CROSSWORD_PRICES
from annotatsiya_utils import generate_annotation, ANNOTATSIYA_PRICE, ANNOTATSIYA_TYPES, LANG_LABELS as AN_LANG_LABELS
from taqriz_utils import generate_taqriz, TAQRIZ_PRICE, TAQRIZ_TYPES, LANG_LABELS as TQ_LANG_LABELS
from ai_utils import get_ai_response, AI_FREE_LIMIT, AI_PRICE_PER_MSG
from db import get_ai_daily_count, increment_ai_daily_count
from insho_utils import generate_insho, INSHO_PRICES, INSHO_TYPES, INSHO_TYPE_LABELS
from hujjat_utils import (
    generate_cv_full,
    generate_cv, generate_motivation, generate_table, generate_mindmap,
    HUJJAT_PRICES, LANG_LABELS as HJ_LANG_LABELS
)
from pptx import Presentation

# ─────────────────────────────────────────────
# Admin va narx sozlamalari
# ─────────────────────────────────────────────
ADMIN_IDS = {6813160650}
ADMIN_USERNAME = "Slidego_adminbot"  # Admin telegram username (@ belgisisiz)
ARCHIVE_CHANNEL = -1003599976854  # Arxiv kanal ID
REQUIRED_CHANNEL = "@slidego"  # Majburiy obuna kanali
CARD_NUMBER = "9860 1606 3105 8700"  # Abramatova Madina
SERVICE_PRICES = {
    "slayd":        3000,
    "mustaqil_ish": 3000,
    "referat":      3000,
    "loyiha_ishi":  3000,
    "infografika":      1500,
    "infografika_hd":   3000,
    "maqola":           3000,
    "tezis":            2000,
    "glossary_small":   1000,
    "glossary_medium":  2000,
    "glossary_large":   3000,
    "test_10":          1000,
    "test_20":          2000,
    "test_30":          2000,
    "test_50":          3000,
    # Krossvord
    "krossvord_10":     1000,
    "krossvord_15":     2000,
    "krossvord_20":     2000,
    # Insho / Esse
    "insho_1":          1000,
    # Hujjat & Dizayn
    "rezyume":          3000,
    "motivatsion":      2000,
    "jadval":           2000,
    "mindmap":          2000,
    "insho_2":          2000,
    "insho_3":          2000,
    "insho_5":          3000,
    "kurs_ishi":        12000,
    "bmi":              20000,
    "arxivlash":        1000,
    "pdf_convert":      1500,
}
MIN_TOPUP = 3000

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Suhbat holatlari — Balans to'ldirish
# ─────────────────────────────────────────────
(
    TOPUP_AMOUNT,     # 40
    TOPUP_SCREENSHOT, # 41
) = range(40, 42)

# ─────────────────────────────────────────────
# Suhbat holatlari — Slayd yaratish
# ─────────────────────────────────────────────
(    LANGUAGE_SELECTION,  # 0 — til tanlash
    TOPIC,               # 1 — mavzu kiritish
    NAME_SURNAME,        # 2 — ism-familiya
    SLIDE_COUNT,         # 3 — slayd soni
    PLAN_CONFIRMATION,   # 4 — reja tasdiqlash
    TEMPLATE_SELECT,     # 5 — shablon tanlash
    IMAGE_SOURCE_SELECT, # 6 — rasm manbai tanlash (o'z rasmlari yoki avtomatik)
    USER_IMAGE_COLLECT,  # 7 — foydalanuvchi rasmlarini qabul qilish
) = range(8)

# ─────────────────────────────────────────────
# Suhbat holatlari — Mustaqil ish
# ─────────────────────────────────────────────
(
    MI_LANGUAGE,         # 10
    MI_TOPIC,            # 11
    MI_NAME_SURNAME,     # 12
    MI_PAGE_COUNT,       # 13
    MI_UNIVERSITY,       # 14
    MI_TEACHER,          # 15
) = range(10, 16)

# ─────────────────────────────────────────────
# Suhbat holatlari — Referat
# ─────────────────────────────────────────────
(
    RF_LANGUAGE,         # 20
    RF_TOPIC,            # 21
    RF_NAME_SURNAME,     # 22
    RF_PAGE_COUNT,       # 23
    RF_UNIVERSITY,       # 24
    RF_TEACHER,          # 25
) = range(20, 26)

# ─────────────────────────────────────────────
# Suhbat holatlari — Loyiha ishi
# ─────────────────────────────────────────────
(
    LI_LANGUAGE,         # 30
    LI_TOPIC,            # 31
    LI_NAME_SURNAME,     # 32
    LI_PAGE_COUNT,       # 33
    LI_UNIVERSITY,       # 34
    LI_SUBJECT,          # 35
    LI_TEACHER,          # 36
) = range(30, 37)
# ─────────────────────────────────────────────
# Suhbat holatlari — Infografika
# ─────────────────────────────────────────────
(
    IG_LANGUAGE,         # 50
    IG_TYPE,             # 51
    IG_COLOR,            # 52
    IG_QUALITY,          # 53  (Oddiy/HD tanlash)
    IG_TOPIC,            # 54
) = range(50, 55)

# ─────────────────────────────────────────────
# Suhbat holatlari — Maqola
# ─────────────────────────────────────────────
(
    MQ_LANGUAGE,         # 60
    MQ_TYPE,             # 61
    MQ_PAGE_COUNT,       # 62
    MQ_TOPIC,            # 63
    MQ_NAME_SURNAME,     # 64
    MQ_UNIVERSITY,       # 65
) = range(60, 66)

# ─────────────────────────────────────────────
# Suhbat holatlari — Kurs ishi / BMI
# ─────────────────────────────────────────────
(
    KI_TYPE,             # 70 — kurs ishi yoki BMI
    KI_LANGUAGE,         # 71
    KI_TOPIC,            # 72
    KI_NAME_SURNAME,     # 73
    KI_PAGE_COUNT,       # 74
    KI_UNIVERSITY,       # 75
    KI_FACULTY,          # 76
    KI_TEACHER,          # 77
    KI_SUBJECT,          # 78
    KI_EDIT_TOPIC,       # 79
) = range(70, 80)

# ─────────────────────────────────────────────
# Suhbat holatlari — Tezis
# ─────────────────────────────────────────────
(
    TZ_TYPE,             # 80 — tezis turi
    TZ_LANGUAGE,         # 81
    TZ_PAGE_COUNT,       # 82
    TZ_TOPIC,            # 83
    TZ_NAME_SURNAME,     # 84
    TZ_INSTITUTION,      # 85
) = range(80, 86)

# ─────────────────────────────────────────────
# Suhbat holatlari — Glossary
# ─────────────────────────────────────────────
(
    GL_LANGUAGE,         # 90
    GL_SIZE,             # 91
    GL_TOPIC,            # 92
    GL_AUTHOR,           # 93
) = range(90, 94)

# ─────────────────────────────────────────────
# Suhbat holatlari — Test tuzish
# ─────────────────────────────────────────────
(
    TS_LANGUAGE,         # 95
    TS_COUNT,            # 96
    TS_TOPIC,            # 97
    TS_AUTHOR,           # 98
) = range(95, 99)

# ─────────────────────────────────────────────
# Suhbat holatlari — Krossvord
# ─────────────────────────────────────────────
(
    KR_LANGUAGE,         # 100
    KR_COUNT,            # 101
    KR_TOPIC,            # 102
    KR_AUTHOR,           # 103
) = range(100, 104)
# ─────────────────────────────────────────────
# Suhbat holatlari — Insho / Esse
# ─────────────────────────────────────────────
(
    IN_TYPE,             # 105
    IN_LANGUAGE,         # 106
    IN_PAGE_COUNT,       # 107
    IN_TOPIC,            # 108
    IN_NAME_SURNAME,     # 109
    IN_INSTITUTION,      # 110
) = range(105, 111)
# ─────────────────────────────────────────────
# Suhbat holatlari — Hujjat & Dizayn
# ─────────────────────────────────────────────
(
    HJ_MENU,             # 111
    HJ_LANG,             # 112
    HJ_INPUT1,           # 113
    HJ_INPUT2,           # 114
    HJ_INPUT3,           # 115
) = range(111, 116)
# ─────────────────────────────────────────────
# Suhbat holatlari — Annotatsiya
# ─────────────────────────────────────────────
(
    AN_LANGUAGE,         # 120
    AN_TYPE,             # 121
    AN_TITLE,            # 122
    AN_AUTHOR,           # 123
) = range(120, 124)
# ─────────────────────────────────────────────
# Suhbat holatlari — Taqriz
# ─────────────────────────────────────────────
(
    TQ_LANGUAGE,         # 125
    TQ_TYPE,             # 126
    TQ_TITLE,            # 127
    TQ_AUTHOR,           # 128
    TQ_REVIEWER,         # 129
    TQ_SUMMARY,          # 130
) = range(125, 131)
# ─────────────────────────────────────────────
(
    AI_CHAT,             # 131
) = range(131, 132)
# ─────────────────────────────────────────────
# Suhbat holatlari — Rezyume (yangi, to'liq)
# ─────────────────────────────────────────────
(
    CV_LANG,             # 140
    CV_FULLNAME,         # 141
    CV_EMAIL,            # 142
    CV_PHONE,            # 143
    CV_LOCATION,         # 144
    CV_LINKS,            # 145
    CV_PHOTO,            # 146
    CV_TITLE,            # 147
    CV_REGION,           # 148
    CV_SUMMARY,          # 149
    CV_EXPERIENCE,       # 150
    CV_PROJECTS,         # 151
    CV_EDUCATION,        # 152
    CV_CERTIFICATIONS,   # 153
    CV_SKILLS,           # 154
    CV_TONE,             # 155
    CV_LENGTH,           # 156
) = range(140, 157)
# ─────────────────────────────────────────────
# Suhbat holatlari — Arxivlash
# ─────────────────────────────────────────────
(
    ARX_RECEIVE,         # 160 — fayllarni qabul qilish
) = range(160, 161)
# ─────────────────────────────────────────────
# Suhbat holatlari — PDF Konvertatsiya
# ─────────────────────────────────────────────
(
    PDF_RECEIVE,         # 165 — fayl qabul qilish
) = range(165, 166)
# ─────────────────────────────────────────────
# Til nomlari
# ─────────────────────────────────────────────
LANGUAGE_NAMES = {
    "uz":  "O'zbek tili",
    "en":  "Ingliz tili",
    "ru":  "Rus tili",
    "ko":  "Kores tili",
    "zh":  "Xitoy tili",
    "de":  "Nemis tili",
    "kaa": "Qoraqalpoq tili",
    "tk":  "Turkman tili",
    "tg":  "Tojik tili",
}

# ─────────────────────────────────────────────
# Klaviaturalar
# ─────────────────────────────────────────────

def get_main_menu_keyboard():
    keyboard = [
        [KeyboardButton("🪄 Slayd yaratish ✨"), KeyboardButton("📄 Mustaqil ish ✨")],
        [KeyboardButton("📁 Loyiha ishi ✨"),    KeyboardButton("📊 Infografika ✨")],
        [KeyboardButton("🤖 AI yordamchi 💬"), KeyboardButton("📰 Maqola ✨")],
        [KeyboardButton("🎓 Kurs ishi / BMI 📝"),    KeyboardButton("📚 Referat ✨")],
        [KeyboardButton("📜 Tezis ✨"),         KeyboardButton("💡 Glossary ✨")],
        [KeyboardButton("🧩 Krossvord ✨"),     KeyboardButton("🔠 Test tuzish")],
        [KeyboardButton("✍️ Insho / Esse ✨"),    KeyboardButton("📂 Hujjat & Dizayn ✨")],
        [KeyboardButton("📋 Annotatsiya ✨"),       KeyboardButton("📝 Taqriz ✨")],
        [KeyboardButton("📦 Ziplash/Arxivlash 🗜️"),  KeyboardButton("📄 PDF Konvertatsiya 🔄")],
        [KeyboardButton("💰 Balans")],
        [KeyboardButton("🔗 Referral")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_language_keyboard():
    keyboard = [
        [InlineKeyboardButton("O'zbek tili",  callback_data="lang_uz"),
         InlineKeyboardButton("Ingliz tili",  callback_data="lang_en")],
        [InlineKeyboardButton("Rus tili",     callback_data="lang_ru"),
         InlineKeyboardButton("Kores tili",   callback_data="lang_ko")],
        [InlineKeyboardButton("Xitoy tili",   callback_data="lang_zh"),
         InlineKeyboardButton("Nemis tili",   callback_data="lang_de")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_mi_language_keyboard():
    """Mustaqil ish uchun til tanlash klaviaturasi."""
    keyboard = [
        [InlineKeyboardButton("O'zbek tili",  callback_data="mi_lang_uz"),
         InlineKeyboardButton("Ingliz tili",  callback_data="mi_lang_en")],
        [InlineKeyboardButton("Rus tili",     callback_data="mi_lang_ru"),
         InlineKeyboardButton("Kores tili",   callback_data="mi_lang_ko")],
        [InlineKeyboardButton("Xitoy tili",   callback_data="mi_lang_zh"),
         InlineKeyboardButton("Nemis tili",   callback_data="mi_lang_de")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_rf_language_keyboard():
    """Referat uchun til tanlash klaviaturasi."""
    keyboard = [
        [InlineKeyboardButton("O'zbek tili",  callback_data="rf_lang_uz"),
         InlineKeyboardButton("Ingliz tili",  callback_data="rf_lang_en")],
        [InlineKeyboardButton("Rus tili",     callback_data="rf_lang_ru"),
         InlineKeyboardButton("Kores tili",   callback_data="rf_lang_ko")],
        [InlineKeyboardButton("Xitoy tili",   callback_data="rf_lang_zh"),
         InlineKeyboardButton("Nemis tili",   callback_data="rf_lang_de")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_rf_page_count_keyboard():
    """Referat uchun sahifa soni tanlash klaviaturasi."""
    keyboard = [
        [InlineKeyboardButton("5",  callback_data="rf_pages_5"),
         InlineKeyboardButton("10", callback_data="rf_pages_10"),
         InlineKeyboardButton("12", callback_data="rf_pages_12")],
        [InlineKeyboardButton("15", callback_data="rf_pages_15"),
         InlineKeyboardButton("18", callback_data="rf_pages_18"),
         InlineKeyboardButton("20", callback_data="rf_pages_20")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_li_language_keyboard():
    """Loyiha ishi uchun til tanlash klaviaturasi."""
    keyboard = [
        [InlineKeyboardButton("O'zbek tili",  callback_data="li_lang_uz"),
         InlineKeyboardButton("Ingliz tili",  callback_data="li_lang_en")],
        [InlineKeyboardButton("Rus tili",     callback_data="li_lang_ru"),
         InlineKeyboardButton("Kores tili",   callback_data="li_lang_ko")],
        [InlineKeyboardButton("Xitoy tili",   callback_data="li_lang_zh"),
         InlineKeyboardButton("Nemis tili",   callback_data="li_lang_de")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_li_page_count_keyboard():
    """Loyiha ishi uchun sahifa soni tanlash klaviaturasi."""
    keyboard = [
        [InlineKeyboardButton("5 sahifa",  callback_data="li_pages_5"),
         InlineKeyboardButton("10 sahifa", callback_data="li_pages_10"),
         InlineKeyboardButton("15 sahifa", callback_data="li_pages_15")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_slide_count_keyboard():
    keyboard = [
        [InlineKeyboardButton("5",  callback_data="slide_count_5"),
         InlineKeyboardButton("10", callback_data="slide_count_10"),
         InlineKeyboardButton("15", callback_data="slide_count_15")],
        [InlineKeyboardButton("20", callback_data="slide_count_20"),
         InlineKeyboardButton("25", callback_data="slide_count_25"),
         InlineKeyboardButton("30", callback_data="slide_count_30")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_mi_page_count_keyboard():
    """Mustaqil ish uchun sahifa soni tanlash klaviaturasi."""
    keyboard = [
        [InlineKeyboardButton("5",  callback_data="mi_pages_5"),
         InlineKeyboardButton("10", callback_data="mi_pages_10"),
         InlineKeyboardButton("12", callback_data="mi_pages_12")],
        [InlineKeyboardButton("15", callback_data="mi_pages_15"),
         InlineKeyboardButton("18", callback_data="mi_pages_18"),
         InlineKeyboardButton("20", callback_data="mi_pages_20")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_plan_confirmation_keyboard():
    keyboard = [
        [InlineKeyboardButton("✅ Tasdiqlash",   callback_data="plan_confirm_yes"),
         InlineKeyboardButton("🔄 Qayta tuzish", callback_data="plan_confirm_no")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ─────────────────────────────────────────────
# Yordamchi: Markdown maxsus belgilarni escape qilish
# ─────────────────────────────────────────────
def esc_md(text) -> str:
    """Markdown v1 uchun maxsus belgilarni escape qiladi."""
    if not text:
        return str(text) if text is not None else ""
    text = str(text)
    for ch in ['_', '*', '[', ']', '`']:
        text = text.replace(ch, f'\\{ch}')
    return text

# ─────────────────────────────────────────────
# Yordamchi: reja matnini chiroyli formatlash
# ─────────────────────────────────────────────

def format_plan_message(topic, slide_count, language_name, plan_items):
    """Foydalanuvchiga ko'rsatiladigan reja xabarini formatlaydi."""
    import re
    clean_lines = []
    for idx, item in enumerate(plan_items):
        text = re.sub(r'^[\d]+[\d\.]*\.?\s*', '', str(item)).strip()
        clean_lines.append(f"{idx+1}. {esc_md(text)}")
    plan_lines = "\n".join(clean_lines)
    return (
        f"📋 *Reja tayyor!*\n\n"
        f"📌 *Mavzu:* {esc_md(topic)}\n"
        f"🌐 *Til:* {esc_md(language_name)}\n"
        f"📊 *Slaydlar soni:* {slide_count}\n\n"
        f"*Reja:*\n{plan_lines}\n\n"
        f"_Ushbu reja asosida slaydlar sarlavhalari ham tayyor. "
        f"Tasdiqlasangiz, kontent yaratila boshlaydi._"
    )

# ─────────────────────────────────────────────
# Yordamchi: Arxiv kanalga yuborish
# ─────────────────────────────────────────────

async def archive_send_document(
    bot,
    user,
    service_name: str,
    topic: str,
    language: str,
    page_count,
    price: int,
    document_bytes,
    filename: str,
):
    """Yaratilgan hujjatni arxiv kanalga yuboradi."""
    try:
        from datetime import datetime
        from io import BytesIO
        full_name = (user.full_name or '').strip() or 'Nomsiz'
        username_str = f"@{user.username}" if user.username else "username yo'q"
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        caption = (
            f"📥 Yangi fayl arxivlandi!\n\n"
            f"👤 Foydalanuvchi: {full_name} ({username_str})\n"
            f"🆔 ID: {user.id}\n"
            f"📋 Xizmat: {service_name}\n"
            f"📝 Mavzu: {topic}\n"
            f"🌐 Til: {language}\n"
            f"📄 Sahifalar: {page_count}\n"
            f"💰 Narx: {price:,} so'm\n"
            f"📅 Sana: {now}"
        )
        # bytes yoki BytesIO dan yangi BytesIO nusxa yaratish
        if isinstance(document_bytes, (bytes, bytearray)):
            archive_doc = BytesIO(document_bytes)
        elif hasattr(document_bytes, 'getvalue'):
            archive_doc = BytesIO(document_bytes.getvalue())
        elif hasattr(document_bytes, 'seek'):
            document_bytes.seek(0)
            archive_doc = BytesIO(document_bytes.read())
        else:
            archive_doc = document_bytes
        archive_doc.seek(0)
        await bot.send_document(
            chat_id=ARCHIVE_CHANNEL,
            document=archive_doc,
            filename=filename,
            caption=caption
        )
    except Exception as e:
        logger.warning(f"Arxiv kanalga yuborishda xatolik: {e}", exc_info=True)

async def archive_send_photo(
    bot,
    user,
    service_name: str,
    topic: str,
    language: str,
    price: int,
    photo_path: str,
):
    """Yaratilgan rasmni (infografika) arxiv kanalga yuboradi."""
    try:
        from datetime import datetime
        full_name = (user.full_name or '').strip() or 'Nomsiz'
        username_str = f"@{user.username}" if user.username else "username yo'q"
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        caption = (
            f"📥 Yangi fayl arxivlandi!\n\n"
            f"👤 Foydalanuvchi: {full_name} ({username_str})\n"
            f"🆔 ID: {user.id}\n"
            f"📋 Xizmat: {service_name}\n"
            f"📝 Mavzu: {topic}\n"
            f"🌐 Til: {language}\n"
            f"💰 Narx: {price:,} so'm\n"
            f"📅 Sana: {now}"
        )
        with open(photo_path, "rb") as f:
            await bot.send_photo(
                chat_id=ARCHIVE_CHANNEL,
                photo=f,
                caption=caption
            )
    except Exception as e:
        logger.warning(f"Arxiv kanalga rasm yuborishda xatolik: {e}")

# ─────────────────────────────────────────────
# Majburiy obuna tekshiruvi
# ─────────────────────────────────────────────

# Obuna holati cache: {user_id: (is_subscribed, timestamp)}
_subscription_cache: dict = {}
SUBSCRIPTION_CACHE_TTL = 600  # 10 daqiqa (soniyada)

async def check_subscription(bot, user_id: int, force: bool = False) -> bool:
    """Foydalanuvchi REQUIRED_CHANNEL ga a'zo ekanligini tekshiradi.
    Natija 10 daqiqa cache da saqlanadi."""
    import time
    now = time.time()

    # Cache dan tekshirish (force=True bo'lsa cache o'tkazib yuboriladi)
    if not force and user_id in _subscription_cache:
        cached_result, cached_time = _subscription_cache[user_id]
        if now - cached_time < SUBSCRIPTION_CACHE_TTL:
            return cached_result

    # API ga so'rov yuborish
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        result = member.status in ("member", "administrator", "creator")
    except Exception as e:
        logger.warning(f"Obuna tekshirishda xatolik: {e}")
        # Xatolikda eski cache natijasini qaytarish (agar mavjud bo'lsa)
        if user_id in _subscription_cache:
            return _subscription_cache[user_id][0]
        return True  # Xatolikda botdan foydalanishga ruxsat berish

    # Cache ga saqlash
    _subscription_cache[user_id] = (result, now)
    return result

def get_subscription_keyboard():
    """Kanalga a'zo bo'lish tugmasi."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Kanalga a'zo bo'lish", url="https://t.me/slidego")],
        [InlineKeyboardButton("✅ A'zo bo'ldim, tekshir", callback_data="check_sub")],
    ])

# ─────────────────────────────────────────────
# Handlerlar — Umumiy
# ─────────────────────────────────────────────


# Barcha menyu tugmalarini ushlovchi filter — conversation ichida menyu bosilganda state handlerlar ishlamasin
MENU_REGEX = (
    r"^(🪄 Slayd yaratish ✨|📄 Mustaqil ish ✨|📚 Referat ✨|📁 Loyiha ishi ✨|"
    r"📊 Infografika ✨|💰 Balans|🔗 Referral|🤖 AI yordamchi 💬|📰 Maqola ✨|"
    r"🎓 Kurs ishi / BMI 📝|📜 Tezis ✨|💡 Glossary ✨|🔠 Test tuzish|"
    r"🧩 Krossvord ✨|✍️ Insho / Esse ✨|📂 Hujjat & Dizayn ✨|"
    r"📋 Annotatsiya ✨|📝 Taqriz ✨|📦 Ziplash/Arxivlash 🗜️|📄 PDF Konvertatsiya 🔄|"
    r"💳 Balans to'ldirish|⬅️ Orqaga)$"
)
MENU_FILTER = filters.Regex(MENU_REGEX)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Botni ishga tushiradi va asosiy menyu ko'rsatadi."""
    context.user_data.clear()
    user = update.effective_user

    # Kanalga obuna tekshiruvi
    is_subscribed = await check_subscription(context.bot, user.id)
    if not is_subscribed:
        await update.message.reply_text(
            f"Salom, {user.first_name}! 👋\n\n"
            f"Botdan foydalanish uchun avval kanalimizga a'zo bo'lishingiz kerak:\n"
            f"📢 @slidego\n\n"
            f"A'zo bo'lgandan so'ng \"✅ A'zo bo'ldim, tekshir\" tugmasini bosing:",
            reply_markup=get_subscription_keyboard()
        )
        return LANGUAGE_SELECTION

    # Referral tekshirish
    ref_by = None
    args = context.args
    if args and args[0].startswith("ref_"):
        ref_code = args[0][4:]
        referrer = await asyncio.to_thread(db.get_user_by_ref_code, ref_code)
        if referrer and referrer['user_id'] != user.id:
            ref_by = referrer['user_id']
    user_row = await asyncio.to_thread(db.get_or_create_user, user.id, user.username, user.full_name, ref_by)

    # Yangi foydalanuvchiga bir martalik xush kelibsiz bonusi
    bonus_given = await asyncio.to_thread(db.give_welcome_bonus, user.id, 4000)

    if bonus_given:
        # Yangi foydalanuvchi — taklif qiluvchiga 3000 so'm bonus
        if ref_by:
            await asyncio.to_thread(db.add_balance, ref_by, 2000)
            logger.info(f"Referral bonus: {ref_by} ga 2000 so'm berildi (yangi user: {user.id})")
            try:
                await context.bot.send_message(
                    chat_id=ref_by,
                    text=f"🎉 Siz taklif qilgan do'stingiz botga qo'shildi!\n"
                         f"💰 Balansingizga 2,000 so'm bonus qo'shildi."
                )
            except Exception as e:
                logger.error(f"Referral bonus xabari yuborishda xatolik: {e}")

        await update.message.reply_text(
            f"Assalomu alaykum, {user.first_name}! 👋\n\n"
            f"🎁 Xush kelibsiz bonusi: 4,000 so'm balansingizga qo'shildi!\n"
            f"Bu bonus faqat bir marta beriladi.\n\n"
            f"Quyidagi xizmatlardan birini tanlang:",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            f"Assalomu alaykum, {user.first_name}! 👋\n\nBotga xush kelibsiz! Quyidagi xizmatlardan birini tanlang:",
            reply_markup=get_main_menu_keyboard()
        )
    return LANGUAGE_SELECTION

async def handle_main_menu_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asosiy menyu tugmasini qayta ishlaydi."""
    text = update.message.text
    user = update.effective_user
    await asyncio.to_thread(db.get_or_create_user, user.id, user.username, user.full_name)

    # Kanalga obuna tekshiruvi
    is_subscribed = await check_subscription(context.bot, user.id)
    if not is_subscribed:
        await update.message.reply_text(
            f"Botdan foydalanish uchun avval kanalimizga a'zo bo'lishingiz kerak:\n"
            f"📢 @slidego\n\n"
            f"A'zo bo'lgandan so'ng \"✅ A'zo bo'ldim, tekshir\" tugmasini bosing:",
            reply_markup=get_subscription_keyboard()
        )
        return LANGUAGE_SELECTION
    # Balans sahifasiga kirish uchun topup state ni tozalamaymiz
    # Faqat boshqa xizmatga o'tganda tozalaymiz
    balans_tugmalari = {"💰 Balans", "🔗 Referral", "💳 Balans to'ldirish", "⬅️ Orqaga"}
    if text not in balans_tugmalari:
        _set_topup_state(context, user.id, None)

    if text == "🪄 Slayd yaratish ✨":
        context.user_data.clear()
        context.user_data["mode"] = "slayd"
        await update.message.reply_text(
            "Qaysi tilda slayd yaratmoqchisiz?",
            reply_markup=get_language_keyboard()
        )
        return LANGUAGE_SELECTION

    elif text == "📄 Mustaqil ish ✨":
        context.user_data.clear()
        context.user_data["mode"] = "mustaqil_ish"
        await update.message.reply_text(
            "📄 *Mustaqil ish* bo'limiga xush kelibsiz!\n\nQaysi tilda yozmoqchisiz?",
            reply_markup=get_mi_language_keyboard(),
            parse_mode="Markdown"
        )
        return MI_LANGUAGE

    elif text == "📁 Loyiha ishi ✨":
        context.user_data.clear()
        context.user_data["mode"] = "loyiha_ishi"
        await update.message.reply_text(
            "📁 *Loyiha ishi* bo'limiga xush kelibsiz!\n\nQaysi tilda yozmoqchisiz?",
            reply_markup=get_li_language_keyboard(),
            parse_mode="Markdown"
        )
        return LI_LANGUAGE

    elif text == "📊 Infografika ✨":
        context.user_data.clear()
        context.user_data["mode"] = "infografika"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🇺🇿 O'zbek tili",  callback_data="ig_lang_uz"),
             InlineKeyboardButton("🇬🇧 Ingliz tili",  callback_data="ig_lang_en")],
            [InlineKeyboardButton("🇷🇺 Rus tili",     callback_data="ig_lang_ru"),
             InlineKeyboardButton("🇩🇪 Nemis tili",   callback_data="ig_lang_de")],
        ])
        await update.message.reply_text(
            "📊 *Infografika* bo'limiga xush kelibsiz!\n\nQaysi tilda infografika yaratmoqchisiz?",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return IG_LANGUAGE
    elif text == "📚 Referat ✨":
        context.user_data.clear()
        context.user_data["mode"] = "referat"
        await update.message.reply_text(
            "📚 *Referat* bo'limiga xush kelibsiz!\n\nQaysi tilda yozmoqchisiz?",
            reply_markup=get_rf_language_keyboard(),
            parse_mode="Markdown"
        )
        return RF_LANGUAGE

    elif text == "🤖 AI yordamchi 💬":
        context.user_data.clear()
        context.user_data["mode"] = "ai_chat"
        context.user_data["ai_history"] = []
        # Kunlik limit tekshirish
        daily_count = await asyncio.to_thread(get_ai_daily_count, user.id)
        remaining = max(0, AI_FREE_LIMIT - daily_count)
        if remaining > 0:
            status_text = f"🎁 Bugun {remaining} ta bepul savol qoldi"
        else:
            status_text = f"💳 Har savol: {AI_PRICE_PER_MSG:,} so'm"
        await update.message.reply_text(
            f"🤖 *AI Yordamchi*\n\n"
            f"Men professional akademik yordamchiman.\n"
            f"Har qanday savol, tushuntirish, tahlil uchun yordamga tayyorman.\n\n"
            f"{status_text}\n\n"
            f"📌 *Savolingizni batafsil yozing* — bu sizga aniq va professional javob olishga yordam beradi.\n\n"
            f"*Misol savollar:*\n"
            f"• \'Kurs ishi kirish qismini qanday yozaman?\' \n"
            f"• \'Mitoz va meyoz farqi nima?\'\n"
            f"• \'Python da list va tuple qachon ishlatiladi?\'\n\n"
            f"✏️ Savolingizni yozing:",
            parse_mode="Markdown"
        )
        return AI_CHAT

    elif text == "📰 Maqola ✨":
        context.user_data.clear()
        context.user_data["mode"] = "maqola"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("O'zbek tili",  callback_data="mq_lang_uz"),
             InlineKeyboardButton("Ingliz tili",  callback_data="mq_lang_en")],
            [InlineKeyboardButton("Rus tili",     callback_data="mq_lang_ru"),
             InlineKeyboardButton("Kores tili",   callback_data="mq_lang_ko")],
            [InlineKeyboardButton("Xitoy tili",   callback_data="mq_lang_zh"),
             InlineKeyboardButton("Nemis tili",   callback_data="mq_lang_de")],
        ])
        await update.message.reply_text(
            "📰 *Maqola* bo'limiga xush kelibsiz!\n\nQaysi tilda maqola yozmoqchisiz?",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return MQ_LANGUAGE

    elif text == "🎓 Kurs ishi / BMI 📝":
        context.user_data.clear()
        context.user_data["mode"] = "kurs_ishi"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📚 Kurs ishi", callback_data="ki_type_kurs_ishi")],
            [InlineKeyboardButton("🎓 Bitiruv malakaviy ishi (BMI)", callback_data="ki_type_bmi")],
        ])
        await update.message.reply_text(
            "🎓 *Kurs ishi / Bitiruv malakaviy ishi*\n\n"
            "📚 *Kurs ishi:*\n"
            "\u2022 20 sahifa \u2192 12 000 so'm\n"
            "\u2022 25 sahifa \u2192 14 000 so'm\n"
            "\u2022 35 sahifa \u2192 16 000 so'm\n"
            "\u2022 45 sahifa \u2192 20 000 so'm\n\n"
            "🎓 *Bitiruv malakaviy ishi (BMI):*\n"
            "\u2022 50 sahifa \u2192 20 000 so'm\n"
            "\u2022 70 sahifa \u2192 30 000 so'm\n"
            "\u2022 100 sahifa \u2192 45 000 so'm\n\n"
            "Qaysi turni tanlaysiz?",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return KI_TYPE

    elif text == "🧩 Krossvord ✨":
        context.user_data.clear()
        context.user_data["mode"] = "krossvord"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🇺🇿 O'zbek tili",  callback_data="kr_lang_uz"),
             InlineKeyboardButton("🇬🇧 Ingliz tili",  callback_data="kr_lang_en")],
            [InlineKeyboardButton("🇷🇺 Rus tili",     callback_data="kr_lang_ru"),
             InlineKeyboardButton("🇰🇷 Kores tili",   callback_data="kr_lang_ko")],
            [InlineKeyboardButton("🇨🇳 Xitoy tili",   callback_data="kr_lang_zh"),
             InlineKeyboardButton("🇩🇪 Nemis tili",   callback_data="kr_lang_de")],
        ])
        await update.message.reply_text(
            "🧩 *Krossvord yaratish*\n\n"
            "Mavzu bo'yicha professional krossvord yaratiladi.\n"
            "Natijada 2 ta fayl yuboriladi:\n"
            "• 📝 *Bo'sh to'r* (o'quvchi uchun)\n"
            "• ✅ *Javobli to'r* (o'qituvchi uchun)\n\n"
            "Narxlar:\n"
            "• 10 ta so'z → 1 000 so'm\n"
            "• 15 ta so'z → 2 000 so'm\n"
            "• 20 ta so'z → 2 000 so'm\n\n"
            "Qaysi tilda krossvord yaratmoqchisiz?",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return KR_LANGUAGE
    elif text == "🔠 Test tuzish":
        context.user_data.clear()
        context.user_data["mode"] = "test"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🇺🇿 O'zbek tili",  callback_data="ts_lang_uz"),
             InlineKeyboardButton("🇬🇧 Ingliz tili",  callback_data="ts_lang_en")],
            [InlineKeyboardButton("🇷🇺 Rus tili",     callback_data="ts_lang_ru"),
             InlineKeyboardButton("🇰🇷 Kores tili",   callback_data="ts_lang_ko")],
            [InlineKeyboardButton("🇨🇳 Xitoy tili",   callback_data="ts_lang_zh"),
             InlineKeyboardButton("🇩🇪 Nemis tili",   callback_data="ts_lang_de")],
        ])
        await update.message.reply_text(
            "🔠 *Test tuzish*\n\n"
            "Mavzu bo'yicha A/B/C/D formatida test yaratiladi.\n"
            "Natijada 2 ta fayl yuboriladi:\n"
            "• 📝 *Savol varaqasi* (imtihon uchun)\n"
            "• ✅ *Javoblar varaqasi* (o'qituvchi uchun)\n\n"
            "Narxlar:\n"
            "• 10 ta savol → 1 000 so'm\n"
            "• 20 ta savol → 2 000 so'm\n"
            "• 30 ta savol → 2 000 so'm\n"
            "• 50 ta savol → 3 000 so'm\n\n"
            "Qaysi tilda test yaratmoqchisiz?",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return TS_LANGUAGE

    elif text == "💡 Glossary ✨":
        context.user_data.clear()
        context.user_data["mode"] = "glossary"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🇺🇿 O'zbek tili",  callback_data="gl_lang_uz"),
             InlineKeyboardButton("🇬🇧 Ingliz tili",  callback_data="gl_lang_en")],
            [InlineKeyboardButton("🇷🇺 Rus tili",     callback_data="gl_lang_ru"),
             InlineKeyboardButton("🇰🇷 Kores tili",   callback_data="gl_lang_ko")],
            [InlineKeyboardButton("🇨🇳 Xitoy tili",   callback_data="gl_lang_zh"),
             InlineKeyboardButton("🇩🇪 Nemis tili",   callback_data="gl_lang_de")],
        ])
        await update.message.reply_text(
            "💡 *Glossary (Atamalar lug'ati)*\n\n"
            "Mavzu bo'yicha atamalar va ta'riflari bilan professional lug'at yaratiladi.\n\n"
            "Narxlar:\n"
            "\u2022 Kichik (15 ta atama) \u2192 1 000 so'm\n"
            "\u2022 O'rta (30 ta atama) \u2192 2 000 so'm\n"
            "\u2022 Katta (50 ta atama) \u2192 3 000 so'm\n\n"
            "Qaysi tilda glossary yaratmoqchisiz?",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return GL_LANGUAGE

    elif text == "📜 Tezis ✨":
        context.user_data.clear()
        context.user_data["mode"] = "tezis"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Konferensiya tezisi", callback_data="tz_type_konferensiya")],
            [InlineKeyboardButton("🏆 Olimpiada tezisi", callback_data="tz_type_olimpiada")],
            [InlineKeyboardButton("📚 Seminar tezisi", callback_data="tz_type_seminar")],
            [InlineKeyboardButton("🎓 Dissertatsiya tezisi", callback_data="tz_type_dissertatsiya")],
        ])
        await update.message.reply_text(
            "📜 *Tezis yaratish*\n\n"
            "Tezis turi va narxlari:\n"
            "\u2022 1 sahifa \u2192 2 000 so'm\n"
            "\u2022 2 sahifa \u2192 2 000 so'm\n"
            "\u2022 3 sahifa \u2192 2 000 so'm\n"
            "\u2022 5 sahifa \u2192 2 000 so'm\n\n"
            "Qaysi turdagi tezis kerak?",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return TZ_TYPE

    elif text == "✍️ Insho / Esse ✨":
        context.user_data.clear()
        context.user_data["mode"] = "insho"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✍️ Erkin insho",       callback_data="in_type_erkin")],
            [InlineKeyboardButton("🔍 Tahliliy esse",     callback_data="in_type_tahliliy")],
            [InlineKeyboardButton("💡 Argumentativ esse", callback_data="in_type_argumentativ")],
            [InlineKeyboardButton("📖 Tavsifiy insho",    callback_data="in_type_tavsifiy")],
            [InlineKeyboardButton("⚖️ Muqoyasali esse",   callback_data="in_type_muqoyasali")],
        ])
        await update.message.reply_text(
            "✍️ *Insho / Esse yozish*\n\n"
            "Akademik va professional uslubda insho yoziladi.\n\n"
            "Narxlar:\n"
            "• 1 sahifa → 1 000 so'm\n"
            "• 2 sahifa → 2 000 so'm\n"
            "• 3 sahifa → 2 000 so'm\n"
            "• 5 sahifa → 3 000 so'm\n\n"
            "Insho turini tanlang:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return IN_TYPE
    elif text == "📂 Hujjat & Dizayn ✨":
        context.user_data.clear()
        context.user_data["mode"] = "hujjat"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📄 Rezyume / CV",       callback_data="hj_rezyume")],
            [InlineKeyboardButton("📜 Motivatsion xat",    callback_data="hj_motivatsion")],
            [InlineKeyboardButton("📊 Jadval & Diagramma", callback_data="hj_jadval")],
            [InlineKeyboardButton("🗺️ Kontsept xarita",    callback_data="hj_mindmap")],
        ])
        await update.message.reply_text(
            "📂 *Hujjat & Dizayn xizmatlari*\n\n"
            "• 📄 Rezyume / CV — 3 000 so'm\n"
            "• 📜 Motivatsion xat — 2 000 so'm\n"
            "• 📊 Jadval & Diagramma — 2 000 so'm\n"
            "• 🗺️ Kontsept xarita — 2 000 so'm\n\n"
            "Xizmatni tanlang:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return HJ_MENU
    elif text == "📋 Annotatsiya ✨":
        context.user_data.clear()
        context.user_data["mode"] = "annotatsiya"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🇺🇿 O'zbek",  callback_data="an_lang_uz"),
             InlineKeyboardButton("🇷🇺 Rus",     callback_data="an_lang_ru")],
            [InlineKeyboardButton("🇬🇧 Ingliz",  callback_data="an_lang_en"),
             InlineKeyboardButton("🇰🇷 Kores",   callback_data="an_lang_ko")],
            [InlineKeyboardButton("🇨🇳 Xitoy",   callback_data="an_lang_zh"),
             InlineKeyboardButton("🇩🇪 Nemis",   callback_data="an_lang_de")],
        ])
        await update.message.reply_text(
            "📋 *Annotatsiya yaratish*\n\nNarx: *1 000 so'm*\n\nTil tanlang:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return AN_LANGUAGE

    elif text == "📝 Taqriz ✨":
        context.user_data.clear()
        context.user_data["mode"] = "taqriz"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🇺🇿 O'zbek",  callback_data="tq_lang_uz"),
             InlineKeyboardButton("🇷🇺 Rus",     callback_data="tq_lang_ru")],
            [InlineKeyboardButton("🇬🇧 Ingliz",  callback_data="tq_lang_en"),
             InlineKeyboardButton("🇰🇷 Kores",   callback_data="tq_lang_ko")],
            [InlineKeyboardButton("🇨🇳 Xitoy",   callback_data="tq_lang_zh"),
             InlineKeyboardButton("🇩🇪 Nemis",   callback_data="tq_lang_de")],
        ])
        await update.message.reply_text(
            "📝 *Taqriz yaratish*\n\nNarx: *2 000 so'm*\n\nTil tanlang:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return TQ_LANGUAGE
    elif text == "📦 Ziplash/Arxivlash 🗜️":
        context.user_data.clear()
        context.user_data["mode"] = "arxivlash"
        context.user_data["arxiv_files"] = []
        price = SERVICE_PRICES["arxivlash"]
        yo_riqnoma = (
            f"📦 *Arxivlash xizmati*\n\n"
            f"💰 Narx: *{price:,} so'm*\n\n"
            f"📌 *Yo'riqnoma:*\n"
            f"1️⃣ Fayllaringizni yuboring (PDF, DOCX, XLSX, JPG, PNG va boshqalar)\n"
            f"2️⃣ Bir nechta fayl yuborishingiz mumkin (max 20 MB/fayl)\n"
            f"3️⃣ Barcha fayllar yuborilgach *Arxivlash* tugmasini bosing\n"
            f"4️⃣ Bot fayllaringizni *.zip* arxivga yig'ib qaytaradi\n\n"
            f"⚠️ *Cheklovlar:*\n"
            f"• Har bir fayl maksimal *20 MB*\n"
            f"• Maksimal *20 ta fayl* bir arxivda\n"
            f"• Fayllar 5 daqiqa ichida yuborilishi kerak\n\n"
            f"📤 Fayllarni yuboring:"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗜️ Arxivlash", callback_data="arx_done")],
            [InlineKeyboardButton("❌ Bekor qilish", callback_data="arx_cancel")],
        ])
        await update.message.reply_text(
            yo_riqnoma,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return ARX_RECEIVE
    elif text == "📄 PDF Konvertatsiya 🔄":
        context.user_data.clear()
        context.user_data["mode"] = "pdf_convert"
        price = SERVICE_PRICES["pdf_convert"]
        yo_riqnoma = (
            f"📄 *PDF Konvertatsiya xizmati*\n\n"
            f"💰 Narx: *{price:,} so'm* (bitta fayl)\n\n"
            f"📌 *Qo'llab-quvvatlanadigan formatlar:*\n"
            f"• 📝 *Word* (DOCX, DOC)\n"
            f"• 📊 *Excel* (XLSX, XLS)\n"
            f"• 📊 *PowerPoint* (PPTX, PPT)\n"
            f"• 🖼️ *Rasm* (JPG, PNG, BMP, WEBP)\n\n"
            f"📌 *Yo'riqnoma:*\n"
            f"1️⃣ Faylingizni yuboring\n"
            f"2️⃣ Bot uni PDF ga aylantirib qaytaradi\n"
            f"3️⃣ Har bir fayl uchun *{price:,} so'm* yechiladi\n\n"
            f"⚠️ Fayl hajmi maksimal *20 MB*\n\n"
            f"📤 Faylingizni yuboring:"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Bekor qilish", callback_data="pdf_cancel")],
        ])
        await update.message.reply_text(
            yo_riqnoma,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return PDF_RECEIVE
    elif text == "💰 Balans":
        user_data = await asyncio.to_thread(db.get_user, user.id)
        balance = user_data['balance'] if user_data else 0
        # Xizmat narxlari jadvali
        msg = (
            f"💰 *Balansingiz: {balance:,} so'm*\n\n"
            "📋 *Xizmat narxlari:*\n"
            "• Taqdimot: `3 000` so'm\n"
            "• Mustaqil ish: `3 000` so'm\n"
            "• Kurs ishi: `12 000` so'm\n"
            "• Infografika: `1 500` so'm\n"
            "• Maqola / Tezis: `2 000` so'm\n"
            "• Test / Krossvord: `1 000–3 000` so'm\n"
            "• Arxivlash: `1 000` so'm\n"
            "• AI yordamchi: (kuniga 3 ta bepul)\n\n"
            f"🏦 *To'lov kartasi:*\n"
            f"`{CARD_NUMBER}`\n"
            f"👤 Abramatova Madina\n\n"
            f"💡 Kerakli summani kartaga o'tkazing va /chekyubor buyrug'i orqali chek rasmini yuboring."
        )
        # Balans sahifasi uchun alohida ReplyKeyboard
        balans_keyboard = ReplyKeyboardMarkup([
            [KeyboardButton("💳 Balans to'ldirish")],
            [KeyboardButton("⬅️ Orqaga")],
        ], resize_keyboard=True)
        await update.message.reply_text(
            msg,
            reply_markup=balans_keyboard,
            parse_mode="Markdown"
        )
        return LANGUAGE_SELECTION
    elif text == "🔗 Referral":
        user_data = await asyncio.to_thread(db.get_user, user.id)
        ref_code = user_data['referral_code'] if user_data else ''
        bot_username = context.bot.username
        ref_link = f"https://t.me/{bot_username}?start=ref_{ref_code}"
        msg = (
            f"🔗 *Referral dasturi*\n\n"
            f"Do'stlaringizni taklif qiling va har bir yangi foydalanuvchi uchun *2 000 so'm* bonus oling!\n\n"
            f"📎 *Sizning referral havolangiz:*\n"
            f"`{ref_link}`\n\n"
            f"🎁 *Bonus:*\n"
            f"• Siz: 2 000 so'm\n"
            f"• Do'stingiz: 4 000 so'm xush kelibsiz bonusi\n\n"
            f"Havolani do'stlaringizga yuboring va bonuslar yig'ing!"
        )
        referral_keyboard = ReplyKeyboardMarkup([
            [KeyboardButton("⬅️ Orqaga")],
        ], resize_keyboard=True)
        await update.message.reply_text(
            msg,
            reply_markup=referral_keyboard,
            parse_mode="Markdown"
        )
        return LANGUAGE_SELECTION
    elif text == "💳 Balans to'ldirish":
        # Balans to'ldirish: summa so'rab TOPUP_AMOUNT state ga o'tish
        _set_topup_state(context, user.id, 'amount')
        _set_topup_amount(context, user.id, 0)
        db.set_user_topup_state(user.id, 'amount', 0)
        msg = (
            f"💳 *Balans to'ldirish*\n\n"
            f"🏦 *To'lov kartasi:*\n"
            f"`{CARD_NUMBER}`\n"
            f"👤 Abramatova Madina\n\n"
            f"📝 *Kartaga qancha so'm o'tkazdingiz?*\n"
            f"Faqat raqam kiriting (masalan: `10000`):\n\n"
            f"_Bekor qilish uchun /start bosing_"
        )
        await update.message.reply_text(
            msg,
            parse_mode="Markdown"
        )
        return TOPUP_AMOUNT
    elif text == "⬅️ Orqaga":       # Asosiy menyuga qaytish
        _set_topup_state(context, user.id, None)
        await update.message.reply_text(
            "🏠 Asosiy menyu:",
            reply_markup=get_main_menu_keyboard()
        )
        return LANGUAGE_SELECTION
    else:
        # Xizmat nomini emoji bilan birga chiroyli ko'rsatish
        service_name = text if text else "Bu xizmat"
        await update.message.reply_text(
            f"⏳ *{service_name}* hozircha ishlab chiqilmoqda.\n"
            f"Tez orada ishga tushiriladi! Kuzatib boring. 🚀",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
        return LANGUAGE_SELECTION

# ─────────────────────────────────────────────
# Handlerlar — Slayd yaratish
# ─────────────────────────────────────────────

async def get_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Til tanlovini qabul qiladi."""
    query = update.callback_query
    await query.answer()

    language_code = query.data.split("_", 1)[1]
    context.user_data["language"] = language_code

    lang_name = LANGUAGE_NAMES.get(language_code, "O'zbek tili")
    await query.edit_message_text(
        text=f"✅ Til: *{lang_name}*\n\nEndi taqdimot mavzusini kiriting:\nIltimos mavzuni aniq va tushunarli holda, imlo xatolarsiz yozing:",
        parse_mode="Markdown"
    )
    return TOPIC

async def get_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Mavzuni qabul qiladi."""
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    topic = update.message.text.strip()
    if not topic:
        await update.message.reply_text("Iltimos, mavzuni kiriting:")
        return TOPIC

    context.user_data["topic"] = topic

    name_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ O'tkazib yuborish", callback_data="skip_name_surname")]
    ])
    await update.message.reply_text(
        f"📌 *Mavzu:* {esc_md(topic)}\n\nIsm va familiyangizni kiriting (ixtiyoriy):",
        reply_markup=name_keyboard,
        parse_mode="Markdown"
    )
    return NAME_SURNAME

async def edit_topic_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Mavzuni tahrirlash tugmasi bosilganda."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text="✏️ Yangi mavzuni kiriting:\nIltimos mavzuni aniq va tushunarli holda, imlo xatolarsiz yozing:",
        parse_mode="Markdown"
    )
    return TOPIC

async def edit_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ism/familiyani tahrirlash tugmasi bosilganda."""
    query = update.callback_query
    await query.answer()
    topic = context.user_data.get("topic", "")
    name_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Mavzuni tahrirlash", callback_data="edit_topic")],
        [InlineKeyboardButton("⏭ O'tkazib yuborish", callback_data="skip_name_surname")]
    ])
    await query.edit_message_text(
        text=f"📌 *Mavzu:* {esc_md(topic)}\n\n✏️ Yangi ism va familiyangizni kiriting:",
        reply_markup=name_keyboard,
        parse_mode="Markdown"
    )
    return NAME_SURNAME

async def get_name_surname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ism-familiyani qabul qiladi yoki o'tkazib yuboradi."""
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        context.user_data["name_surname"] = ""
        topic = context.user_data.get("topic", "")
        edit_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Mavzuni tahrirlash", callback_data="edit_topic")],
            [InlineKeyboardButton("✏️ Ism/familiyani tahrirlash", callback_data="edit_name")],
        ])
        await query.edit_message_text(
            text=f"📌 *Mavzu:* {esc_md(topic)}\n👤 *Ism:* —\n\nNechta slayd kerak?",
            reply_markup=InlineKeyboardMarkup(
                get_slide_count_keyboard().inline_keyboard + edit_keyboard.inline_keyboard
            ),
            parse_mode="Markdown"
        )
    else:
        name_surname = update.message.text.strip()
        context.user_data["name_surname"] = name_surname
        topic = context.user_data.get("topic", "")
        edit_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Mavzuni tahrirlash", callback_data="edit_topic")],
            [InlineKeyboardButton("✏️ Ism/familiyani tahrirlash", callback_data="edit_name")],
        ])
        await update.message.reply_text(
            f"📌 *Mavzu:* {esc_md(topic)}\n👤 *Ism:* {esc_md(name_surname)}\n\nNechta slayd kerak?",
            reply_markup=InlineKeyboardMarkup(
                get_slide_count_keyboard().inline_keyboard + edit_keyboard.inline_keyboard
            ),
            parse_mode="Markdown"
        )
        return SLIDE_COUNT
    return SLIDE_COUNT

async def get_slide_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Slayd sonini qabul qiladi va 1-BOSQICH ni ishga tushiradi."""
    query = update.callback_query
    await query.answer()

    slide_count = int(query.data.split("_")[2])
    context.user_data["slide_count"] = slide_count

    topic = context.user_data.get("topic", "")
    language = context.user_data.get("language", "uz")
    lang_name = LANGUAGE_NAMES.get(language, "O'zbek tili")

    await query.edit_message_text(
        text=f"📊 Slaydlar soni: *{slide_count}*\n\n⏳ Reja tuzilmoqda...",
        parse_mode="Markdown"
    )

    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            generate_plan_with_titles,
            topic, slide_count, language
        )
    except Exception as e:
        logger.error(f"generate_plan_with_titles xatolik: {e}")
        result = None

    if not result or not result.get("plan"):
        result = {
            "plan": [f"1. {esc_md(topic)} haqida umumiy ma'lumot",
                     f"2. {esc_md(topic)} ning asosiy jihatlari",
                     f"3. {esc_md(topic)} ning ahamiyati"],
            "slide_titles": [f"{esc_md(topic)} — {i+1}" for i in range(slide_count)]
        }

    context.user_data["stage1_result"] = result
    plan_items = result.get("plan", [])
    plan_text = format_plan_message(topic, slide_count, lang_name, plan_items)

    await query.edit_message_text(
        text=plan_text,
        reply_markup=get_plan_confirmation_keyboard(),
        parse_mode="Markdown"
    )
    return PLAN_CONFIRMATION

async def plan_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Reja tasdiqlash yoki qayta tuzish."""
    query = update.callback_query
    await query.answer()

    topic       = context.user_data.get("topic", "")
    language    = context.user_data.get("language", "uz")
    slide_count = context.user_data.get("slide_count", 5)
    name_surname = context.user_data.get("name_surname", "")
    lang_name   = LANGUAGE_NAMES.get(language, "O'zbek tili")

    if query.data == "plan_confirm_no":
        await query.edit_message_text(text="🔄 Reja qayta tuzilmoqda...")
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                generate_plan_with_titles,
                topic, slide_count, language
            )
        except Exception as e:
            logger.error(f"Qayta generate_plan_with_titles xatolik: {e}")
            result = None

        if not result or not result.get("plan"):
            result = {
                "plan": [f"1. {esc_md(topic)} haqida umumiy ma'lumot",
                         f"2. {esc_md(topic)} ning asosiy jihatlari",
                         f"3. {esc_md(topic)} ning ahamiyati"],
                "slide_titles": [f"{esc_md(topic)} — {i+1}" for i in range(slide_count)]
            }

        context.user_data["stage1_result"] = result
        plan_items = result.get("plan", [])
        plan_text = format_plan_message(topic, slide_count, lang_name, plan_items)

        await query.edit_message_text(
            text=plan_text,
            reply_markup=get_plan_confirmation_keyboard(),
            parse_mode="Markdown"
        )
        return PLAN_CONFIRMATION

    # ── Tasdiqlandi: 2-BOSQICH ──
    # Balans tekshirish
    user_id = query.from_user.id
    price = SERVICE_PRICES['slayd']
    balance = await asyncio.to_thread(db.get_balance, user_id)
    if balance < price:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Balans to'ldirish", callback_data="topup_start")]
        ])
        await query.edit_message_text(
            f"❌ *Balansingiz yetarli emas!*\n\n"
            f"💰 Joriy balans: *{balance:,} so'm*\n"
            f"💳 Kerakli summa: *{price:,} so'm*\n\n"
            f"Iltimos, avval balansni to'ldiring:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    # ── Faqat 15-shablon: to'g'ridan-to'g'ri taqdimot yaratishga o'tish ──
    chat_id = query.message.chat_id
    # 28-shablon preview rasmini yuborish (agar mavjud bo'lsa)
    previews_dir = os.path.join(os.path.dirname(__file__), "templates", "previews")
    preview_33_path = os.path.join(previews_dir, "33.png")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Shu shablon bilan davom etish", callback_data="template_select_33")],
    ])
    if os.path.exists(preview_33_path):
        with open(preview_33_path, "rb") as f:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=f,
                caption="🎨 *Math Style shablon*\n\nTaqdimot shu shablon asosida yaratiladi.",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text="🎨 *Math Style shablon* tanlandi.\n\nDavom etish uchun tugmani bosing:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    return TEMPLATE_SELECT

async def template_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Foydalanuvchi shablonni tanladi — taqdimot yaratiladi."""
    query = update.callback_query
    await query.answer()
    template_num = int(query.data.split("_")[-1])
    topic        = context.user_data.get("topic", "")
    language     = context.user_data.get("language", "uz")
    slide_count  = context.user_data.get("slide_count", 5)
    name_surname = context.user_data.get("name_surname", "")
    user_id      = query.from_user.id
    price        = SERVICE_PRICES['slayd']
    try:
        await query.edit_message_caption(
            caption=f"⏳ Shablon {template_num} tanlandi! Kontent yaratilmoqda...",
        )
    except Exception:
        try:
            await query.edit_message_text(
                text=f"⏳ Shablon {template_num} tanlandi! Kontent yaratilmoqda...",
            )
        except Exception:
            pass
    stage1 = context.user_data.get("stage1_result", {})
    plan_items   = stage1.get("plan", [])
    slide_titles = stage1.get("slide_titles", [])
    plan_dict = {"title": "Reja", "content": plan_items}
    chat_id = query.message.chat_id
    logger.info(f"Foydalanuvchi tanlagan shablon: {template_num}")
    template_slide_type_names = {
        1: SLIDE_TYPE_NAMES,
        2: SLIDE_TYPE_NAMES,
        3: SLIDE_TYPE_NAMES_T3,
        4: SLIDE_TYPE_NAMES_T4,
        5: SLIDE_TYPE_NAMES_T5,
        6: SLIDE_TYPE_NAMES_T6,
        7: SLIDE_TYPE_NAMES_T7,
        8: SLIDE_TYPE_NAMES_T8,
        9: SLIDE_TYPE_NAMES_T9,
        10: SLIDE_TYPE_NAMES_T10,
        11: SLIDE_TYPE_NAMES_T11,
        12: SLIDE_TYPE_NAMES_T12,
        13: SLIDE_TYPE_NAMES_T13,
        14: SLIDE_TYPE_NAMES_T14,
        15: SLIDE_TYPE_NAMES_T15,
        16: SLIDE_TYPE_NAMES_T16,
        17: SLIDE_TYPE_NAMES_T17,
        18: SLIDE_TYPE_NAMES_T18,
        19: SLIDE_TYPE_NAMES_T19,
        20: SLIDE_TYPE_NAMES_T20,
        21: SLIDE_TYPE_NAMES_T21,
        22: SLIDE_TYPE_NAMES_T22,
        23: SLIDE_TYPE_NAMES_T23,
        24: SLIDE_TYPE_NAMES_T24,
        25: SLIDE_TYPE_NAMES_T25,
        26: SLIDE_TYPE_NAMES_T26,
        27: SLIDE_TYPE_NAMES_T27,
        28: SLIDE_TYPE_NAMES_T28,
        29: SLIDE_TYPE_NAMES_T29,
        30: SLIDE_TYPE_NAMES_T30,
        31: SLIDE_TYPE_NAMES_T31,
        32: SLIDE_TYPE_NAMES_T32,
        33: SLIDE_TYPE_NAMES_T33,
    }[template_num]
    template_generate_func = {
        1: generate_template_1_presentation,
        2: generate_template_2_presentation,
        3: generate_template_3_presentation,
        4: generate_template_4_presentation,
        5: generate_template_5_presentation,
        6: generate_template_6_presentation,
        7: generate_template_7_presentation,
        8: generate_template_8_presentation,
        9: generate_template_9_presentation,
        10: generate_template_10_presentation,
        11: generate_template_11_presentation,
        12: generate_template_12_presentation,
        13: generate_template_13_presentation,
        14: generate_template_14_presentation,
        15: generate_template_15_presentation,
        16: generate_template_16_presentation,
        17: generate_template_17_presentation,
        18: generate_template_18_presentation,
        19: generate_template_19_presentation,
        20: generate_template_20_presentation,
        21: generate_template_21_presentation,
        22: generate_template_22_presentation,
        23: generate_template_23_presentation,
        24: generate_template_24_presentation,
        25: generate_template_25_presentation,
        26: generate_template_26_presentation,
        27: generate_template_27_presentation,
        28: generate_template_28_presentation,
        29: generate_template_29_presentation,
        30: generate_template_30_presentation,
        31: generate_template_31_presentation,
        32: generate_template_32_presentation,
        33: generate_template_33_presentation,
    }[template_num]
    logger.info(f"Foydalanuvchi tanlagan shablon: {template_num}")
    try:
        content_data_list = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: generate_all_content(topic, slide_count, language, slide_titles, template_slide_type_names)
        )

        # Agar bo'sh qaytsa, bir marta qayta urinib ko'rish
        if not content_data_list:
            logger.warning("generate_all_content bo'sh qaytdi, qayta urinilmoqda...")
            await asyncio.sleep(2)
            content_data_list = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: generate_all_content(topic, slide_count, language, slide_titles, template_slide_type_names)
            )

        if not content_data_list:
            raise ValueError("generate_all_content bo'sh qaytdi (2 marta urinildi)")

        # Har bir shablon uchun rasm ishlatadigan slide_type lar
        TEMPLATE_IMAGE_SLIDE_TYPES = {
            1: [2, 4],
            2: [4],
            3: [3, 4],
            4: [3],
            5: [0, 3],
            6: [],
            7: [0, 4],
            8: [0, 2],
            9: [1, 2, 3, 4],  # T9: slayd 4,5,6,7 da rasm bor
            10: [0, 1, 2, 3, 4],  # T10: barcha kontent slaydlarda rasm bor
            11: [1, 2],            # T11: slayd4 (image_left) va slayd5 (quote+image)
            12: [1, 4],
            13: [0, 1, 3, 4],            # T13: slayd3,4,6,7 da rasm bor
            14: [0, 1, 2, 3, 4],           # T14: barcha kontent slaydlarda rasm bor
            15: [0, 1, 2, 3, 4],  # T15: barcha kontent slaydlarda rasm bor
            16: [0, 1, 2, 3, 4],  # T16: barcha kontent slaydlarda rasm bor
            17: [0, 1, 2, 3, 4],  # T17: barcha kontent slaydlarda rasm bor
            18: [0, 2, 4],  # T18: slayd3, slayd5, slayd7 da rasm bor
            19: [0, 1, 2, 3, 4],  # T19: barcha kontent slaydlarda rasm bor
            20: [3, 4],  # T20: slayd6 (Picture), slayd7 (3 doira) da rasm bor
            21: [],  # T21: rasm yo'q, faqat matn
            22: [2, 3],  # T22: slayd5 (idx 2), slayd6 (idx 3) da rasm bor
            23: [0, 1, 2, 3, 4],  # T23: barcha kontent slaydlarda Freeform rasm bor
            24: [0, 2, 3],  # T24: slayd3, slayd5, slayd6 da Freeform rasm bor
            25: [0, 1, 2, 3, 4],  # T25: barcha kontent slaydlarda Picture rasm bor
            26: [0, 1, 2, 3, 4],  # T26: barcha kontent slaydlarda Freeform blip rasm bor
            27: [0, 1, 2],  # T27: slayd3 (idx 0), slayd4 (idx 1), slayd5 (idx 2) da Freeform blip rasm bor
            28: [1, 2, 3],  # T28: slayd4 (idx 1), slayd5 (idx 2), slayd6 (idx 3) da Picture rasm bor
            29: [2, 3],  # T29: slayd5 (idx 2), slayd7 (idx 3) da Picture rasm bor
            30: [2, 4],  # T30: slayd5 (idx 2), slayd7 (idx 4) da Picture rasm bor
            31: [2, 4],  # T31: slayd5 img_left (idx 2), slayd7 img_right (idx 4) da Picture rasm bor
            32: [0, 1, 2, 3, 4],  # T32: barcha kontent slaydlarda rasm bor
            33: [0, 1, 2],  # T33: slayd3 (idx 0), slayd4 (idx 1), slayd5 (idx 2) da rasm bor
        }
        image_slide_types = TEMPLATE_IMAGE_SLIDE_TYPES.get(template_num, [])
        image_queries = []
        if image_slide_types:
            for i, item in enumerate(content_data_list):
                stype = i % 5
                if stype in image_slide_types:
                    q = item.get("image_query", "").strip() if isinstance(item, dict) else ""
                    if q:
                        image_queries.append(q)
        logger.info(f"Shablon {template_num}: {len(image_queries)} ta rasm joyi aniqlandi")

        # PPTX yaratish va rasmlarni PARALLEL yuklash
        template_path = os.path.join(os.path.dirname(__file__), "templates", "shablonlar", f"{template_num}.pptx")
        prs = Presentation(template_path)

        async def fetch_one_preview(q):
            urls = await asyncio.get_event_loop().run_in_executor(
                None, lambda qq=q: fetch_image_preview_urls(qq, count=1)
            )
            return (q, urls[0]) if urls else None

        # PPTX yaratish va rasmlarni bir vaqtda parallel boshlash
        pptx_task = asyncio.get_event_loop().run_in_executor(
            None,
            lambda: template_generate_func(
                prs=prs,
                topic=topic,
                requested_slide_count=slide_count,
                language=language,
                name_surname=name_surname,
                plan=plan_dict,
                content_data_list=content_data_list,
            )
        )
        image_tasks = [fetch_one_preview(q) for q in image_queries]

        # Ikkalasini parallel kutish
        results = await asyncio.gather(pptx_task, *image_tasks, return_exceptions=True)
        presentation_bytes = results[0]
        if isinstance(presentation_bytes, Exception):
            raise presentation_bytes

        preview_urls = [r for r in results[1:] if r is not None and not isinstance(r, Exception)]

        safe_topic = "".join(c for c in topic[:30] if c.isalnum() or c in " _-").strip()
        filename = f"{safe_topic or 'taqdimot'}.pptx"

        # Taqdimotni user_data ga saqlash (keyingi bosqich uchun)
        context.user_data["pending_presentation"] = {
            "bytes": presentation_bytes,
            "filename": filename,
            "content_data_list": content_data_list,
            "template_num": template_num,
            "template_generate_func_name": template_num,
        }

        context.user_data["pending_image_queries"] = image_queries
        context.user_data["pending_preview_urls"] = preview_urls
        context.user_data["collected_user_images"] = []  # foydalanuvchi rasmlari uchun

        if not image_queries:
            # Rasm joyi yo'q — to'g'ridan-to'g'ri yuborish
            await context.bot.send_message(chat_id=chat_id, text="⏳ Taqdimot yuborilmoqda...")
            await _send_final_presentation(update, context, chat_id, user_id, topic, slide_count, price, presentation_bytes, filename)
            return ConversationHandler.END

        # Foydalanuvchiga rasm manbai tanlash imkonini berish
        source_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🖼 O'z rasmlarimdan foydalanish", callback_data="img_source_user")],
            [InlineKeyboardButton("🤖 Rasmlarni avtomatik tanlash", callback_data="img_source_auto")],
        ])
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"🖼 *Taqdimot uchun rasmlar*\n\n"
                f"📊 Bu shablonda *{len(image_queries)} ta rasm joyi* bor.\n\n"
                f"Qanday rasm ishlatmoqchisiz?"
            ),
            reply_markup=source_keyboard,
            parse_mode="Markdown"
        )
        return IMAGE_SOURCE_SELECT

    except Exception as e:
        logger.error(f"Prezentatsiya yaratishda xatolik: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Prezentatsiya yaratishda xatolik yuz berdi:\n`{str(e)}`\n\nIltimos, qayta urinib ko'ring. Balans yechilmadi.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
        return ConversationHandler.END


async def _send_final_presentation(update, context, chat_id, user_id, topic, slide_count, price, presentation_bytes, filename):
    """Taqdimotni foydalanuvchiga yuboradi, balansdan yechadi, arxivga saqlaydi."""
    try:
        if presentation_bytes is None:
            raise ValueError("Taqdimot ma'lumotlari topilmadi (None). Iltimos, qayta urinib ko'ring.")
        # bytes bo'lsa BytesIO ga aylantirish
        if isinstance(presentation_bytes, (bytes, bytearray)):
            doc_to_send = BytesIO(presentation_bytes)
            doc_to_send.name = filename
        elif hasattr(presentation_bytes, 'seek'):
            presentation_bytes.seek(0)
            doc_to_send = presentation_bytes
        else:
            doc_to_send = presentation_bytes
        sent_msg = await context.bot.send_document(
            chat_id=chat_id,
            document=doc_to_send,
            filename=filename,
            caption=(
                f"✅ *{esc_md(topic)}* — taqdimot tayyor!\n"
                f"📊 {slide_count} ta slayd | 📎 PPTX\n\n"
                f"📚 Biz bilan ishingiz oson!\n"
                f"🤖 @slidego\n"
                f"📢 t.me/slidego"
            ),
            parse_mode="Markdown"
        )
        _file_id = sent_msg.document.file_id if sent_msg and sent_msg.document else None
        _lang_name = context.user_data.get('language_name', context.user_data.get('language', 'uz'))
        await archive_send_document(
            bot=context.bot,
            user=update.effective_user,
            service_name="🪄 Slayd yaratish",
            topic=topic,
            language=_lang_name,
            page_count=f"{slide_count} slayd",
            price=price,
            document_bytes=presentation_bytes,
            filename=filename,
        )
        await asyncio.to_thread(db.deduct_balance, user_id, price)
        await asyncio.to_thread(db.log_generation, user_id, 'slayd', topic, price, _file_id, filename)
        new_balance = await asyncio.to_thread(db.get_balance, user_id)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"💰 Balans: *{new_balance:,} so'm*\n\nYana biror narsa kerakmi?",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"_send_final_presentation xatolik: {type(e).__name__}: {e}", exc_info=True)
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ Taqdimot yuborishda xatolik yuz berdi:\n`{str(e)[:200]}`\n\nIltimos, qayta urinib ko'ring.",
                reply_markup=get_main_menu_keyboard(),
                parse_mode="Markdown"
            )
        except Exception:
            pass


async def image_source_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Foydalanuvchi rasm manbai tanladi: o'z rasmlari yoki avtomatik."""
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    action = query.data  # img_source_user yoki img_source_auto

    pending = context.user_data.get("pending_presentation", {})
    presentation_bytes = pending.get("bytes")
    filename = pending.get("filename", "taqdimot.pptx")
    topic = context.user_data.get("topic", "")
    slide_count = context.user_data.get("slide_count", 5)
    price = SERVICE_PRICES['slayd']
    image_queries = context.user_data.get("pending_image_queries", [])

    if action == "img_source_auto":
        # Avtomatik rasm tanlash — taqdimotni to'g'ridan-to'g'ri yuborish
        try:
            await query.edit_message_text("⏳ Rasmlar avtomatik tanlanmoqda va taqdimot yuborilmoqda...")
            if presentation_bytes is None:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Taqdimot ma'lumotlari topilmadi. Iltimos, qaytadan taqdimot yarating.",
                    reply_markup=get_main_menu_keyboard()
                )
                return ConversationHandler.END
            await _send_final_presentation(update, context, chat_id, user_id, topic, slide_count, price, presentation_bytes, filename)
        except Exception as e:
            logger.error(f"img_source_auto xatolik: {type(e).__name__}: {e}", exc_info=True)
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ Xatolik yuz berdi:\n`{str(e)[:200]}`\n\nIltimos, qayta urinib ko'ring.",
                    reply_markup=get_main_menu_keyboard(),
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        return ConversationHandler.END

    elif action == "img_source_user":
        # Foydalanuvchi o'z rasmlarini yuborishi kerak
        context.user_data["collected_user_images"] = []
        img_count = len(image_queries)
        await query.edit_message_text(
            f"🖼 *O'z rasmlaringizni yuboring*\n\n"
            f"Bu shablonda *{img_count} ta rasm joyi* bor.\n"
            f"Iltimos, *{img_count} ta rasm* yuboring (tartib bilan).\n\n"
            f"Rasmlar yuborilgandan so'ng taqdimot avtomatik yaratiladi.\n"
            f"Yoki /skip buyrug'i bilan avtomatik rasmlardan foydalaning.",
            parse_mode="Markdown"
        )
        return USER_IMAGE_COLLECT

    return ConversationHandler.END


async def user_image_collect_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Foydalanuvchi rasmlarini qabul qiladi va to'plangan rasmlar soni yetarli bo'lsa taqdimot yaratadi."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    pending = context.user_data.get("pending_presentation", {})
    presentation_bytes = pending.get("bytes")
    filename = pending.get("filename", "taqdimot.pptx")
    topic = context.user_data.get("topic", "")
    slide_count = context.user_data.get("slide_count", 5)
    price = SERVICE_PRICES['slayd']
    image_queries = context.user_data.get("pending_image_queries", [])
    collected = context.user_data.get("collected_user_images", [])
    img_count = len(image_queries)

    # /skip buyrug'i — avtomatik rasmlardan foydalanish
    if update.message and update.message.text and update.message.text.strip().lower() in ["/skip", "skip"]:
        await update.message.reply_text("⏳ Avtomatik rasmlar bilan taqdimot yuborilmoqda...")
        await _send_final_presentation(update, context, chat_id, user_id, topic, slide_count, price, presentation_bytes, filename)
        return ConversationHandler.END

    # Rasm qabul qilish
    if update.message and update.message.photo:
        photo = update.message.photo[-1]  # Eng yuqori sifatli rasm
        file = await context.bot.get_file(photo.file_id)
        file_bytes = await file.download_as_bytearray()
        collected.append(bytes(file_bytes))
        context.user_data["collected_user_images"] = collected

        received = len(collected)
        remaining = img_count - received

        if received >= img_count:
            # Yetarli rasm to'plandi — taqdimotni qayta yaratish va yuborish
            await update.message.reply_text(
                f"✅ {received} ta rasm qabul qilindi!\n⏳ Taqdimot rasmlar bilan yaratilmoqda..."
            )
            # Taqdimotni user_images bilan qayta yaratish
            await _rebuild_and_send_presentation_with_user_images(update, context, chat_id, user_id, topic, slide_count, price, filename, collected)
            return ConversationHandler.END
        else:
            await update.message.reply_text(
                f"✅ {received}/{img_count} rasm qabul qilindi. Yana *{remaining} ta* rasm yuboring.",
                parse_mode="Markdown"
            )
            return USER_IMAGE_COLLECT
    else:
        await update.message.reply_text(
            f"❌ Iltimos, rasm yuboring (hozircha {len(collected)}/{img_count} ta qabul qilindi).\n"
            f"Yoki /skip buyrug'i bilan avtomatik rasmlardan foydalaning."
        )
        return USER_IMAGE_COLLECT


async def _rebuild_and_send_presentation_with_user_images(
    update, context, chat_id, user_id, topic, slide_count, price, filename, user_images_bytes
):
    """Foydalanuvchi rasmlari bilan taqdimotni qayta yaratadi va yuboradi."""
    pending = context.user_data.get("pending_presentation", {})
    template_num = pending.get("template_num", 1)
    content_data_list = pending.get("content_data_list", [])
    name_surname = context.user_data.get("name_surname", "")
    language = context.user_data.get("language", "uz")
    stage1 = context.user_data.get("stage1_result", {})
    plan_items = stage1.get("plan", [])
    plan_dict = {"title": "Reja", "content": plan_items}

    template_generate_func = {
        1: generate_template_1_presentation,
        2: generate_template_2_presentation,
        3: generate_template_3_presentation,
        4: generate_template_4_presentation,
        5: generate_template_5_presentation,
        6: generate_template_6_presentation,
        7: generate_template_7_presentation,
        8: generate_template_8_presentation,
        9: generate_template_9_presentation,
        10: generate_template_10_presentation,
        11: generate_template_11_presentation,
        12: generate_template_12_presentation,
        13: generate_template_13_presentation,
        14: generate_template_14_presentation,
        15: generate_template_15_presentation,
        16: generate_template_16_presentation,
        17: generate_template_17_presentation,
        18: generate_template_18_presentation,
        19: generate_template_19_presentation,
        20: generate_template_20_presentation,
        21: generate_template_21_presentation,
        22: generate_template_22_presentation,
        23: generate_template_23_presentation,
        24: generate_template_24_presentation,
        25: generate_template_25_presentation,
        26: generate_template_26_presentation,
        27: generate_template_27_presentation,
        28: generate_template_28_presentation,
        29: generate_template_29_presentation,
        30: generate_template_30_presentation,
        31: generate_template_31_presentation,
        32: generate_template_32_presentation,
        33: generate_template_33_presentation,
    }.get(template_num, generate_template_16_presentation)
    try:
        template_path = os.path.join(os.path.dirname(__file__), "templates", "shablonlar", f"{template_num}.pptx")
        prs = Presentation(template_path)

        presentation_bytes = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: template_generate_func(
                prs=prs,
                topic=topic,
                requested_slide_count=slide_count,
                language=language,
                name_surname=name_surname,
                plan=plan_dict,
                content_data_list=content_data_list,
                user_images=user_images_bytes,
            )
        )

        if isinstance(presentation_bytes, Exception):
            raise presentation_bytes

        # BytesIO bo'lsa bytes ga aylantirish
        if hasattr(presentation_bytes, 'read'):
            presentation_bytes = presentation_bytes.read()

        await _send_final_presentation(update, context, chat_id, user_id, topic, slide_count, price, presentation_bytes, filename)

    except Exception as e:
        logger.error(f"User images bilan taqdimot yaratishda xatolik: {e}")
        # Fallback: eski taqdimotni yuborish
        old_bytes = pending.get("bytes")
        if old_bytes:
            await update.effective_message.reply_text("⚠️ Rasmlar bilan xatolik yuz berdi. Avtomatik rasmlar bilan yuborilmoqda...")
            await _send_final_presentation(update, context, chat_id, user_id, topic, slide_count, price, old_bytes, filename)
        else:
            await update.effective_message.reply_text(f"❌ Xatolik: {str(e)}")


async def image_confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Eski IMAGE_CONFIRM handler — endi ishlatilmaydi, lekin ConversationHandler uchun saqlanadi."""
    return ConversationHandler.END


# ─────────────────────────────────────────────
# Handlerlar — Loyiha ishi
# ─────────────────────────────────────────────
async def li_get_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    language_code = query.data.split("_", 2)[2]  # li_lang_uz -> uz
    context.user_data["li_language"] = language_code
    lang_name = LANGUAGE_NAMES.get(language_code, "O'zbek tili")
    await query.edit_message_text(
        text=f"✅ Til: *{lang_name}*\n\nLoyiha ishi mavzusini kiriting:",
        parse_mode="Markdown"
    )
    return LI_TOPIC

async def li_get_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    topic = update.message.text.strip()
    if not topic:
        await update.message.reply_text("Iltimos, mavzuni kiriting:")
        return LI_TOPIC
    context.user_data["li_topic"] = topic
    # Ism-familiya MAJBURIY — "Shart emas" yo'q
    await update.message.reply_text(
        f"📌 *Mavzu:* {esc_md(topic)}\n\n"
        f"👤 Ism-familiyangizni kiriting:\n"
        f"_(Hujjatda 'Bajardi:' qatorida yoziladi — majburiy)_",
        parse_mode="Markdown"
    )
    return LI_NAME_SURNAME

async def li_get_name_surname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    # Faqat matn qabul qilinadi (majburiy)
    name = update.message.text.strip() if update.message else ""
    if not name:
        await update.message.reply_text(
            "⚠️ Ism-familiyangizni kiriting (majburiy):"
        )
        return LI_NAME_SURNAME
    context.user_data["li_name_surname"] = name
    await update.message.reply_text(
        f"✅ *Bajardi:* {name}\n\nHujjat nechta sahifadan iborat bo'lsin?",
        reply_markup=get_li_page_count_keyboard(),
        parse_mode="Markdown"
    )
    return LI_PAGE_COUNT

async def li_get_page_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    page_count = int(query.data.split("_")[2])
    context.user_data["li_page_count"] = page_count
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Shart emas", callback_data="li_skip_university")]])
    await query.edit_message_text(
        text=(
            f"📄 Sahifalar soni: *{page_count}*\n\n"
            f"🏢 Ta'lim muassasasi nomini kiriting:\n"
            f"_(Kiritilsa, muqovada 'TA'LIM MUASSASA NOMI' o'rniga yoziladi)_"
        ),
        reply_markup=keyboard, parse_mode="Markdown"
    )
    return LI_UNIVERSITY

async def li_get_university(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    skip_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Shart emas", callback_data="li_skip_subject")]])
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        context.user_data["li_university"] = ""
        await query.edit_message_text(
            text=(
                "📖 Fan yoki yo'nalish nomini kiriting:\n"
                "_(Kiritilsa, muqovada 'TANLANGAN FANIDAN' o'rniga yoziladi)_"
            ),
            reply_markup=skip_kb, parse_mode="Markdown"
        )
    else:
        context.user_data["li_university"] = update.message.text.strip()
        await update.message.reply_text(
            "📖 Fan yoki yo'nalish nomini kiriting:\n"
            "_(Kiritilsa, muqovada 'TANLANGAN FANIDAN' o'rniga yoziladi)_",
            reply_markup=skip_kb, parse_mode="Markdown"
        )
    return LI_SUBJECT

async def li_get_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    skip_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Shart emas", callback_data="li_skip_teacher")]])
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        context.user_data["li_subject"] = ""
        await query.edit_message_text(
            text="O'qituvchi (Qabul qildi) ismini kiriting:",
            reply_markup=skip_kb, parse_mode="Markdown"
        )
    else:
        context.user_data["li_subject"] = update.message.text.strip()
        await update.message.reply_text(
            "O'qituvchi (Qabul qildi) ismini kiriting:",
            reply_markup=skip_kb, parse_mode="Markdown"
        )
    return LI_TEACHER

async def li_get_teacher(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        context.user_data["li_teacher"] = ""
        chat_id = query.message.chat_id
        await query.edit_message_text(text="⏳ Loyiha ishi yaratilmoqda, biroz kuting...")
    else:
        context.user_data["li_teacher"] = update.message.text.strip()
        chat_id = update.message.chat_id
        await update.message.reply_text("⏳ Loyiha ishi yaratilmoqda, biroz kuting...")

    user_id      = update.effective_user.id
    topic        = context.user_data.get("li_topic", "")
    page_count   = context.user_data.get("li_page_count", 15)
    language     = context.user_data.get("li_language", "uz")
    name_surname = context.user_data.get("li_name_surname", "")
    university   = context.user_data.get("li_university", "")
    subject      = context.user_data.get("li_subject", "")
    teacher      = context.user_data.get("li_teacher", "")

    # Balans tekshirish
    price = SERVICE_PRICES['loyiha_ishi']
    balance = await asyncio.to_thread(db.get_balance, user_id)
    if balance < price:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Balans to'ldirish", callback_data="topup_start")]
        ])
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"❌ *Balansingiz yetarli emas!*\n\n"
                f"💰 Joriy balans: *{balance:,} so'm*\n"
                f"💳 Kerakli summa: *{price:,} so'm*\n\n"
                f"Iltimos, avval balansni to'ldiring:"
            ),
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    try:
        doc_bytes = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: generate_loyiha_ishi(
                topic=topic,
                page_count=page_count,
                language=language,
                name_surname=name_surname,
                university_info=university,
                subject_name=subject,
                teacher_name=teacher,
            )
        )
        safe_topic = "".join(c for c in topic[:30] if c.isalnum() or c in " _-").strip()
        filename = f"{safe_topic or 'loyiha_ishi'}.docx"
        # Fayl yuborildi — faqat shundan keyin balansdan yechish
        sent_msg = await context.bot.send_document(
            chat_id=chat_id,
            document=doc_bytes,
            filename=filename,
            caption=(
                f"✅ *{esc_md(topic)}* — loyiha ishi tayyor!\n"
                f"📄 Taxminiy {page_count} sahifa | 📎 DOCX\n\n"
                f"📚 Biz bilan ishingiz oson!\n"
                f"🤖 @slidego\n"
                f"📢 t.me/slidego"
            ),
            parse_mode="Markdown"
        )
        _file_id = sent_msg.document.file_id if sent_msg and sent_msg.document else None
        # Arxiv kanalga yuborish
        await archive_send_document(
            bot=context.bot,
            user=update.effective_user,
            service_name="📁 Loyiha ishi",
            topic=topic,
            language=language,
            page_count=page_count,
            price=price,
            document_bytes=doc_bytes,
            filename=filename,
        )
        await asyncio.to_thread(db.deduct_balance, user_id, price)
        await asyncio.to_thread(db.log_generation, user_id, 'loyiha_ishi', topic, price, _file_id, filename)
        new_balance = await asyncio.to_thread(db.get_balance, user_id)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"💰 Balans: *{new_balance:,} so'm*\n\nYana biror narsa kerakmi?",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Loyiha ishi yaratishda xatolik: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Loyiha ishi yaratishda xatolik:\n`{str(e)}`\n\nIltimos, qayta urinib ko'ring. Balans yechilmadi.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    return ConversationHandler.END

## ─────────────────────────────────────────────
# Handlerlar — Infografika
# ─────────────────────────────────────────────
async def ig_get_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Infografika: tilni qabul qiladi."""
    query = update.callback_query
    await query.answer()
    lang_code = query.data.split("_", 2)[2]  # ig_lang_uz -> uz
    context.user_data["ig_language"] = lang_code
    lang_name = LANGUAGE_NAMES.get(lang_code, "O'zbek tili")
    # Infografika turi tanlash
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Statistik",   callback_data="ig_type_statistik"),
         InlineKeyboardButton("🔄 Jarayon",    callback_data="ig_type_jarayon")],
        [InlineKeyboardButton("↔️ Taqqoslash", callback_data="ig_type_taqqoslash"),
         InlineKeyboardButton("📌 Umumiy",     callback_data="ig_type_umumiy")],
    ])
    await query.edit_message_text(
        text=f"✅ Til: *{lang_name}*\n\nInfografika turini tanlang:\n\n"
             f"📊 *Statistik* — grafiklar va diagrammalar\n"
             f"🔄 *Jarayon* — qadamba-qadam ko'rsatma\n"
             f"↔️ *Taqqoslash* — ikki narsa taqqoslash\n"
             f"📌 *Umumiy* — umumiy ma'lumotli infografika",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return IG_TYPE

async def ig_get_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Infografika: turini qabul qiladi."""
    query = update.callback_query
    await query.answer()
    infotype = query.data.split("_", 2)[2]  # ig_type_statistik -> statistik
    context.user_data["ig_type"] = infotype
    type_names = {
        "statistik": "📊 Statistik",
        "jarayon":   "🔄 Jarayon",
        "taqqoslash": "↔️ Taqqoslash",
        "umumiy":    "📌 Umumiy",
    }
    type_name = type_names.get(infotype, infotype)
    # Rang sxemasi tanlash
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔵 Ko'k",        callback_data="ig_color_ko'k"),
         InlineKeyboardButton("🟢 Yashil",     callback_data="ig_color_yashil")],
        [InlineKeyboardButton("🔴 Qizil",       callback_data="ig_color_qizil"),
         InlineKeyboardButton("🟣 Binafsha",   callback_data="ig_color_binafsha")],
        [InlineKeyboardButton("🟠 To'q sariq", callback_data="ig_color_to'q sariq")],
    ])
    await query.edit_message_text(
        text=f"✅ Tur: *{type_name}*\n\nRang sxemasini tanlang:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return IG_COLOR

async def ig_get_color(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Infografika: rang sxemasini qabul qiladi."""
    query = update.callback_query
    await query.answer()
    # ig_color_ko'k -> ko'k
    color = "_".join(query.data.split("_")[2:])
    context.user_data["ig_color"] = color
    color_names = {
        "ko'k": "🔵 Ko'k", "yashil": "🟢 Yashil",
        "qizil": "🔴 Qizil", "binafsha": "🟣 Binafsha",
        "to'q sariq": "🟠 To'q sariq",
    }
    color_name = color_names.get(color, color)
    # Sifat tanlash (Oddiy / HD)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Oddiy (1,500 so'm)",  callback_data="ig_quality_oddiy")],
        [InlineKeyboardButton("✨ HD — DALL-E 3 (3,000 so'm)", callback_data="ig_quality_hd")],
    ])
    await query.edit_message_text(
        text=(
            f"✅ Rang: *{color_name}*\n\n"
            f"🌟 *Infografika sifatini tanlang:*\n\n"
            f"📊 *Oddiy* — 1,500 so'm\n"
            f"Matplotlib bilan yaratiladi. Tez, arzon.\n\n"
            f"✨ *HD (DALL-E 3)* — 3,000 so'm\n"
            f"Sun'iy intellekt bilan yaratiladi. Professional, chiroyli."
        ),
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return IG_QUALITY

async def ig_get_quality(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Infografika: sifat (Oddiy/HD) tanlashni qabul qiladi."""
    query = update.callback_query
    await query.answer()
    quality = query.data.split("_")[2]  # ig_quality_oddiy -> oddiy
    context.user_data["ig_quality"] = quality
    quality_name = "✨ HD (DALL-E 3)" if quality == "hd" else "📊 Oddiy"
    await query.edit_message_text(
        text=(
            f"✅ Sifat: *{quality_name}*\n\n"
            f"📝 Infografika mavzusini kiriting:\n"
            f"_(masalan: Sun'iy intellekt, Iqlim o'zgarishi, Sog'lom ovqatlanish...)_"
        ),
        parse_mode="Markdown"
    )
    return IG_TOPIC

async def ig_get_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Infografika: mavzuni qabul qiladi va generatsiya qiladi."""
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    topic = update.message.text.strip()
    if not topic:
        await update.message.reply_text("Iltimos, mavzuni kiriting:")
        return IG_TOPIC
    user_id    = update.effective_user.id
    lang_code  = context.user_data.get("ig_language", "uz")
    infotype   = context.user_data.get("ig_type", "umumiy")
    color      = context.user_data.get("ig_color", "ko'k")
    quality    = context.user_data.get("ig_quality", "oddiy")
    lang_name  = LANGUAGE_NAMES.get(lang_code, "O'zbek tili")
    is_hd      = (quality == "hd")
    # Balans tekshirish
    price = SERVICE_PRICES.get('infografika_hd', 5000) if is_hd else SERVICE_PRICES.get('infografika', 3000)
    balance = await asyncio.to_thread(db.get_balance, user_id)
    if balance < price:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Balans to'ldirish", callback_data="topup_start")]
        ])
        await update.message.reply_text(
            f"❌ *Balansingiz yetarli emas!*\n\n"
            f"💰 Joriy balans: *{balance:,} so'm*\n"
            f"💳 Kerakli summa: *{price:,} so'm*\n\n"
            f"Iltimos, avval balansni to'ldiring:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    quality_label = "✨ HD (DALL-E 3)" if is_hd else "📊 Oddiy"
    await update.message.reply_text(
        f"⏳ *{esc_md(topic)}* mavzusida *{quality_label}* infografika yaratilmoqda...\n"
        f"Bu biroz vaqt olishi mumkin, kuting!",
        parse_mode="Markdown"
    )
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")
    try:
        import tempfile, os
        tmp_path = tempfile.mktemp(suffix=".png")
        if is_hd:
            out_path = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: generate_infografika_hd(
                    topic=topic,
                    ig_type=infotype,
                    language=lang_name,
                    color_scheme=color,
                    out_path=tmp_path
                )
            )
        else:
            out_path = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: generate_infografika(
                    topic=topic,
                    ig_type=infotype,
                    language=lang_name,
                    color_scheme=color,
                    out_path=tmp_path
                )
            )
        # Balansdan yechish
        await asyncio.to_thread(db.deduct_balance, user_id, price)
        service_label = "Infografika HD" if is_hd else "Infografika"
        await asyncio.to_thread(db.log_deduction, user_id, price, f"{service_label}: {esc_md(topic)}")
        # PNG yuborish
        with open(out_path, "rb") as f:
            await update.message.reply_photo(
                photo=f,
                caption=(
                    f"✅ *{esc_md(topic)}* — {quality_label} infografika tayyor!\n"
                    f"🖼 PNG\n\n"
                    f"📚 Biz bilan ishingiz oson!\n"
                    f"🤖 @slidego\n"
                    f"📢 t.me/slidego"
                ),
                parse_mode="Markdown"
            )
        # Arxiv kanalga yuborish
        _ig_lang = context.user_data.get('ig_language', 'O\'zbek tili')
        await archive_send_photo(
            bot=context.bot,
            user=update.effective_user,
            service_name=f"📊 Infografika {'HD' if is_hd else 'Oddiy'}",
            topic=topic,
            language=_ig_lang,
            price=price,
            photo_path=out_path,
        )
        # Temp faylni o'chirish
        try:
            os.unlink(out_path)
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Infografika xatolik: {e}")
        await update.message.reply_text(
            "❌ Infografika yaratishda xatolik yuz berdi. Iltimos, qayta urinib ko'ring.",
            reply_markup=get_main_menu_keyboard()
        )
    return ConversationHandler.END

# ─────────────────────────────────────────────
# Handlerlar — Referat
# ─────────────────────────────────────────────
async def rf_get_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Referat: tilni qabul qiladi."""
    query = update.callback_query
    await query.answer()
    language_code = query.data.split("_", 2)[2]  # rf_lang_uz -> uz
    context.user_data["rf_language"] = language_code
    lang_name = LANGUAGE_NAMES.get(language_code, "O'zbek tili")
    await query.edit_message_text(
        text=f"✅ Til: *{lang_name}*\n\nReferat mavzusini kiriting:",
        parse_mode="Markdown"
    )
    return RF_TOPIC

async def rf_get_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Referat: mavzuni qabul qiladi."""
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    topic = update.message.text.strip()
    if not topic:
        await update.message.reply_text("Iltimos, mavzuni kiriting:")
        return RF_TOPIC
    context.user_data["rf_topic"] = topic
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Shart emas", callback_data="rf_skip_name")]
    ])
    await update.message.reply_text(
        f"📌 *Mavzu:* {esc_md(topic)}\n\n"
        f"Ism-familiyangizni kiriting:\n"
        f"_(Kiritilgan ism hujjatda 'Tayyorladi:' qatorida yoziladi)_",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return RF_NAME_SURNAME

async def rf_get_name_surname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Referat: ism-familiyani qabul qiladi yoki o'tkazib yuboradi."""
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        context.user_data["rf_name_surname"] = ""
        await query.edit_message_text(
            text="Hujjat nechta sahifadan iborat bo'lsin?",
            reply_markup=get_rf_page_count_keyboard()
        )
    else:
        context.user_data["rf_name_surname"] = update.message.text.strip()
        await update.message.reply_text(
            "Hujjat nechta sahifadan iborat bo'lsin?",
            reply_markup=get_rf_page_count_keyboard()
        )
    return RF_PAGE_COUNT

async def rf_get_page_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Referat: sahifa sonini qabul qiladi."""
    query = update.callback_query
    await query.answer()
    page_count = int(query.data.split("_")[2])
    context.user_data["rf_page_count"] = page_count
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Shart emas", callback_data="rf_skip_university")]
    ])
    await query.edit_message_text(
        text=(
            f"📄 Sahifalar soni: *{page_count}*\n\n"
            f"Universitet yoki muassasa ma'lumotlarini kiriting:\n"
            f"_(Kiritilsa, hujjat birinchi sahifasiga avtomatik qo'shiladi)_"
        ),
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return RF_UNIVERSITY

async def rf_get_university(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Referat: universitet ma'lumotini qabul qiladi yoki o'tkazib yuboradi."""
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    skip_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Shart emas", callback_data="rf_skip_teacher")]
    ])
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        context.user_data["rf_university"] = ""
        await query.edit_message_text(
            text=(
                "O'qituvchi (Qabul qildi) ismini kiriting:\n"
                "_(Kiritilsa, hujjatda 'Qabul qildi:' qatorida ko'rsatiladi)_"
            ),
            reply_markup=skip_kb,
            parse_mode="Markdown"
        )
    else:
        context.user_data["rf_university"] = update.message.text.strip()
        await update.message.reply_text(
            "O'qituvchi (Qabul qildi) ismini kiriting:\n"
            "_(Kiritilsa, hujjatda 'Qabul qildi:' qatorida ko'rsatiladi)_",
            reply_markup=skip_kb,
            parse_mode="Markdown"
        )
    return RF_TEACHER

async def rf_get_teacher(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Referat: o'qituvchi ismini qabul qiladi va hujjat yaratadi."""
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        context.user_data["rf_teacher"] = ""
        chat_id = query.message.chat_id
        await query.edit_message_text(text="⏳ Referat yaratilmoqda, biroz kuting...")
    else:
        context.user_data["rf_teacher"] = update.message.text.strip()
        chat_id = update.message.chat_id
        await update.message.reply_text("⏳ Referat yaratilmoqda, biroz kuting...")

    user_id      = update.effective_user.id
    topic        = context.user_data.get("rf_topic", "")
    page_count   = context.user_data.get("rf_page_count", 15)
    language     = context.user_data.get("rf_language", "uz")
    name_surname = context.user_data.get("rf_name_surname", "")
    university   = context.user_data.get("rf_university", "")
    teacher      = context.user_data.get("rf_teacher", "")

    # Balans tekshirish
    price = SERVICE_PRICES['referat']
    balance = await asyncio.to_thread(db.get_balance, user_id)
    if balance < price:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Balans to'ldirish", callback_data="topup_start")]
        ])
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"❌ *Balansingiz yetarli emas!*\n\n"
                f"💰 Joriy balans: *{balance:,} so'm*\n"
                f"💳 Kerakli summa: *{price:,} so'm*\n\n"
                f"Iltimos, avval balansni to'ldiring:"
            ),
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    try:
        doc_bytes = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: generate_mustaqil_ish(
                topic=topic,
                page_count=page_count,
                language=language,
                name_surname=name_surname,
                university_info=university,
                teacher_name=teacher,
                doc_type="REFERAT",
            )
        )
        safe_topic = "".join(c for c in topic[:30] if c.isalnum() or c in " _-").strip()
        filename = f"{safe_topic or 'referat'}.docx"
        # Fayl yuborildi — faqat shundan keyin balansdan yechish
        sent_msg = await context.bot.send_document(
            chat_id=chat_id,
            document=doc_bytes,
            filename=filename,
            caption=(
                f"✅ *{esc_md(topic)}* — referat tayyor!\n"
                f"📄 Taxminiy {page_count} sahifa | 📎 DOCX\n\n"
                f"📚 Biz bilan ishingiz oson!\n"
                f"🤖 @slidego\n"
                f"📢 t.me/slidego"
            ),
            parse_mode="Markdown"
        )
        _file_id = sent_msg.document.file_id if sent_msg and sent_msg.document else None
        # Arxiv kanalga yuborish
        await archive_send_document(
            bot=context.bot,
            user=update.effective_user,
            service_name="📚 Referat",
            topic=topic,
            language=language,
            page_count=page_count,
            price=price,
            document_bytes=doc_bytes,
            filename=filename,
        )
        await asyncio.to_thread(db.deduct_balance, user_id, price)
        await asyncio.to_thread(db.log_generation, user_id, 'referat', topic, price, _file_id, filename)
        new_balance = await asyncio.to_thread(db.get_balance, user_id)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"💰 Balans: *{new_balance:,} so'm*\n\nYana biror narsa kerakmi?",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Referat yaratishda xatolik: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Referat yaratishda xatolik:\n`{str(e)}`\n\nIltimos, qayta urinib ko'ring. Balans yechilmadi.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    return ConversationHandler.END

# ─────────────────────────────────────────────
# Handlerlar — Mustaqil ish
# ─────────────────────────────────────────────

async def mi_get_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Mustaqil ish: tilni qabul qiladi."""
    query = update.callback_query
    await query.answer()

    language_code = query.data.split("_", 2)[2]  # mi_lang_uz -> uz
    context.user_data["mi_language"] = language_code
    lang_name = LANGUAGE_NAMES.get(language_code, "O'zbek tili")

    await query.edit_message_text(
        text=f"✅ Til: *{lang_name}*\n\nMustaqil ish mavzusini kiriting:",
        parse_mode="Markdown"
    )
    return MI_TOPIC

async def mi_get_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Mustaqil ish: mavzuni qabul qiladi."""
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    topic = update.message.text.strip()
    if not topic:
        await update.message.reply_text("Iltimos, mavzuni kiriting:")
        return MI_TOPIC

    context.user_data["mi_topic"] = topic

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Shart emas", callback_data="mi_skip_name")]
    ])
    await update.message.reply_text(
        f"📌 *Mavzu:* {esc_md(topic)}\n\n"
        f"Ism-familiyangizni kiriting:\n"
        f"_(Kiritilgan ism hujjatda 'Tayyorladi:' qatorida yoziladi)_",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return MI_NAME_SURNAME

async def mi_get_name_surname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Mustaqil ish: ism-familiyani qabul qiladi yoki o'tkazib yuboradi."""
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        context.user_data["mi_name_surname"] = ""
        await query.edit_message_text(
            text="Hujjat nechta sahifadan iborat bo'lsin?",
            reply_markup=get_mi_page_count_keyboard()
        )
    else:
        name_surname = update.message.text.strip()
        context.user_data["mi_name_surname"] = name_surname
        await update.message.reply_text(
            "Hujjat nechta sahifadan iborat bo'lsin?",
            reply_markup=get_mi_page_count_keyboard()
        )
    return MI_PAGE_COUNT

async def mi_get_page_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Mustaqil ish: sahifa sonini qabul qiladi."""
    query = update.callback_query
    await query.answer()

    page_count = int(query.data.split("_")[2])
    context.user_data["mi_page_count"] = page_count

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Shart emas", callback_data="mi_skip_university")]
    ])
    await query.edit_message_text(
        text=(
            f"📄 Sahifalar soni: *{page_count}*\n\n"
            f"Universitet yoki muassasa ma'lumotlarini kiriting:\n"
            f"_(Kiritilsa, taqdimot birinchi sahifasiga avtomatik qo'shiladi)_"
        ),
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return MI_UNIVERSITY

async def mi_get_university(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Mustaqil ish: universitet ma'lumotini qabul qiladi yoki o'tkazib yuboradi."""
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        context.user_data["mi_university"] = ""
        await query.edit_message_text(
            text=(
                "O'qituvchi (Qabul qildi) ismini kiriting:\n"
                "_(Kiritilsa, hujjatda 'Qabul qildi:' qatorida ko'rsatiladi)_"
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭ Shart emas", callback_data="mi_skip_teacher")]
            ]),
            parse_mode="Markdown"
        )
    else:
        university = update.message.text.strip()
        context.user_data["mi_university"] = university
        await update.message.reply_text(
            "O'qituvchi (Qabul qildi) ismini kiriting:\n"
            "_(Kiritilsa, hujjatda 'Qabul qildi:' qatorida ko'rsatiladi)_",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭ Shart emas", callback_data="mi_skip_teacher")]
            ]),
            parse_mode="Markdown"
        )
    return MI_TEACHER

async def mi_get_teacher(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Mustaqil ish: o'qituvchi ismini qabul qiladi va hujjat yaratadi."""
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        context.user_data["mi_teacher"] = ""
        chat_id = query.message.chat_id
        await query.edit_message_text(
            text="⏳ Mustaqil ish yaratilmoqda, biroz kuting...",
            parse_mode="Markdown"
        )
    else:
        teacher = update.message.text.strip()
        context.user_data["mi_teacher"] = teacher
        chat_id = update.message.chat_id
        await update.message.reply_text(
            "⏳ Mustaqil ish yaratilmoqda, biroz kuting..."
        )

    # Collect all data
    user_id       = update.effective_user.id
    topic         = context.user_data.get("mi_topic", "")
    page_count    = context.user_data.get("mi_page_count", 15)
    language      = context.user_data.get("mi_language", "uz")
    name_surname  = context.user_data.get("mi_name_surname", "")
    university    = context.user_data.get("mi_university", "")
    teacher       = context.user_data.get("mi_teacher", "")

    # Balans tekshirish
    price = SERVICE_PRICES['mustaqil_ish']
    balance = await asyncio.to_thread(db.get_balance, user_id)
    if balance < price:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Balans to'ldirish", callback_data="topup_start")]
        ])
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"❌ *Balansingiz yetarli emas!*\n\n"
                f"💰 Joriy balans: *{balance:,} so'm*\n"
                f"💳 Kerakli summa: *{price:,} so'm*\n\n"
                f"Iltimos, avval balansni to'ldiring:"
            ),
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    try:
        doc_bytes = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: generate_mustaqil_ish(
                topic=topic,
                page_count=page_count,
                language=language,
                name_surname=name_surname,
                university_info=university,
                teacher_name=teacher,
            )
        )

        safe_topic = "".join(c for c in topic[:30] if c.isalnum() or c in " _-").strip()
        filename = f"{safe_topic or 'mustaqil_ish'}.docx"

        # Fayl yuborildi — faqat shundan keyin balansdan yechish
        sent_msg = await context.bot.send_document(
            chat_id=chat_id,
            document=doc_bytes,
            filename=filename,
            caption=(
                f"✅ *{esc_md(topic)}* — mustaqil ish tayyor!\n"
                f"📄 Taxminiy {page_count} sahifa | 📎 DOCX\n\n"
                f"📚 Biz bilan ishingiz oson!\n"
                f"🤖 @slidego\n"
                f"📢 t.me/slidego"
            ),
            parse_mode="Markdown"
        )
        _file_id = sent_msg.document.file_id if sent_msg and sent_msg.document else None
        # Arxiv kanalga yuborish
        await archive_send_document(
            bot=context.bot,
            user=update.effective_user,
            service_name="📄 Mustaqil ish",
            topic=topic,
            language=language,
            page_count=page_count,
            price=price,
            document_bytes=doc_bytes,
            filename=filename,
        )
        await asyncio.to_thread(db.deduct_balance, user_id, price)
        await asyncio.to_thread(db.log_generation, user_id, 'mustaqil_ish', topic, price, _file_id, filename)
        new_balance = await asyncio.to_thread(db.get_balance, user_id)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"💰 Balans: *{new_balance:,} so'm*\n\nYana biror narsa kerakmi?",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Mustaqil ish yaratishda xatolik: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Mustaqil ish yaratishda xatolik:\n`{str(e)}`\n\nIltimos, qayta urinib ko'ring. Balans yechilmadi.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )

    return ConversationHandler.END

# ─────────────────────────────────────────────
# Handlerlar — Maqola
# ─────────────────────────────────────────────

async def mq_get_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maqola: tilni qabul qiladi."""
    query = update.callback_query
    await query.answer()
    language_code = query.data.split("_", 2)[2]  # mq_lang_uz -> uz
    context.user_data["mq_language"] = language_code
    lang_name = LANGUAGE_NAMES.get(language_code, "O'zbek tili")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔬 Ilmiy",        callback_data="mq_type_ilmiy"),
         InlineKeyboardButton("📝 Publitsistik", callback_data="mq_type_publitsistik")],
        [InlineKeyboardButton("📊 Tahliliy",     callback_data="mq_type_tahliliy")],
    ])
    await query.edit_message_text(
        text=f"✅ Til: *{lang_name}*\n\nMaqola turini tanlang:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return MQ_TYPE

async def mq_get_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maqola: turini qabul qiladi."""
    query = update.callback_query
    await query.answer()
    article_type = query.data.split("_", 2)[2]  # mq_type_ilmiy -> ilmiy
    context.user_data["mq_type"] = article_type
    type_names = {
        "ilmiy": "🔬 Ilmiy maqola",
        "publitsistik": "📝 Publitsistik maqola",
        "tahliliy": "📊 Tahliliy maqola",
    }
    type_name = type_names.get(article_type, article_type)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("5 sahifa",  callback_data="mq_pages_5"),
         InlineKeyboardButton("7 sahifa",  callback_data="mq_pages_7"),
         InlineKeyboardButton("9 sahifa",  callback_data="mq_pages_9")],
        [InlineKeyboardButton("11 sahifa", callback_data="mq_pages_11"),
         InlineKeyboardButton("13 sahifa", callback_data="mq_pages_13"),
         InlineKeyboardButton("15 sahifa", callback_data="mq_pages_15")],
    ])
    await query.edit_message_text(
        text=f"✅ Tur: *{type_name}*\n\nMaqola necha sahifa bo'lsin?\n_(Asosiy qism sahifasi — jami hujjat 2 sahifa ko'p bo'ladi)_",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return MQ_PAGE_COUNT

async def mq_get_page_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maqola: sahifa sonini qabul qiladi."""
    query = update.callback_query
    await query.answer()
    page_count = int(query.data.split("_")[2])  # mq_pages_5 -> 5
    context.user_data["mq_page_count"] = page_count

    await query.edit_message_text(
        text=f"✅ Hajm: *{page_count} sahifa*\n\nMaqola mavzusini kiriting:",
        parse_mode="Markdown"
    )
    return MQ_TOPIC

async def mq_get_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maqola: mavzuni qabul qiladi."""
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    topic = update.message.text.strip()
    if not topic:
        await update.message.reply_text("Iltimos, mavzuni kiriting:")
        return MQ_TOPIC
    context.user_data["mq_topic"] = topic

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Shart emas", callback_data="mq_skip_name")]
    ])
    await update.message.reply_text(
        f"📌 *Mavzu:* {esc_md(topic)}\n\n"
        f"Muallif ism-familiyasini kiriting:\n"
        f"_(Ixtiyoriy — maqola sarlavha sahifasida ko'rinadi)_",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return MQ_NAME_SURNAME

async def mq_get_name_surname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maqola: ism-familiyani qabul qiladi yoki o'tkazib yuboradi."""
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        context.user_data["mq_name_surname"] = ""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ Shart emas", callback_data="mq_skip_university")]
        ])
        await query.edit_message_text(
            text="Muassasa yoki universitet nomini kiriting:\n_(Ixtiyoriy)_",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    else:
        context.user_data["mq_name_surname"] = update.message.text.strip()
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ Shart emas", callback_data="mq_skip_university")]
        ])
        await update.message.reply_text(
            "Muassasa yoki universitet nomini kiriting:\n_(Ixtiyoriy)_",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    return MQ_UNIVERSITY

async def mq_get_university(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maqola: muassasani qabul qiladi, so'ng maqolani yaratadi."""
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        context.user_data["mq_university"] = ""
        chat_id = query.message.chat_id
        await query.edit_message_text(text="⏳ Maqola yaratilmoqda, biroz kuting...")
    else:
        context.user_data["mq_university"] = update.message.text.strip()
        chat_id = update.message.chat_id
        await update.message.reply_text("⏳ Maqola yaratilmoqda, biroz kuting...")

    user_id      = update.effective_user.id
    topic        = context.user_data.get("mq_topic", "")
    language     = context.user_data.get("mq_language", "uz")
    article_type = context.user_data.get("mq_type", "ilmiy")
    page_count   = context.user_data.get("mq_page_count", 5)
    name_surname = context.user_data.get("mq_name_surname", "")
    university   = context.user_data.get("mq_university", "")

    # Balans tekshirish
    price = SERVICE_PRICES['maqola']
    balance = await asyncio.to_thread(db.get_balance, user_id)
    if balance < price:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Balans to'ldirish", callback_data="topup_start")]
        ])
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"❌ *Balansingiz yetarli emas!*\n\n"
                f"💰 Joriy balans: *{balance:,} so'm*\n"
                f"💳 Kerakli summa: *{price:,} so'm*\n\n"
                f"Iltimos, avval balansni to'ldiring:"
            ),
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    try:
        doc_bytes = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: generate_maqola(
                topic=topic,
                language=language,
                article_type=article_type,
                page_count=page_count,
                name_surname=name_surname,
                university=university,
            )
        )
        safe_topic = "".join(c for c in topic[:30] if c.isalnum() or c in " _-").strip()
        filename = f"{safe_topic or 'maqola'}.docx"

        sent_msg = await context.bot.send_document(
            chat_id=chat_id,
            document=doc_bytes,
            filename=filename,
            caption=(
                f"✅ *{esc_md(topic)}* — maqola tayyor!\n"
                f"📰 Taxminiy {page_count} sahifa | 📎 DOCX\n\n"
                f"📚 Biz bilan ishingiz oson!\n"
                f"🤖 @slidego\n"
                f"📢 t.me/slidego"
            ),
            parse_mode="Markdown"
        )
        _file_id = sent_msg.document.file_id if sent_msg and sent_msg.document else None
        # Arxiv kanalga yuborish
        await archive_send_document(
            bot=context.bot,
            user=update.effective_user,
            service_name="📰 Maqola",
            topic=topic,
            language=language,
            page_count=page_count,
            price=price,
            document_bytes=doc_bytes,
            filename=filename,
        )
        await asyncio.to_thread(db.deduct_balance, user_id, price)
        await asyncio.to_thread(db.log_generation, user_id, 'maqola', topic, price, _file_id, filename)
        new_balance = await asyncio.to_thread(db.get_balance, user_id)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"💰 Balans: *{new_balance:,} so'm*\n\nYana biror narsa kerakmi?",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Maqola yaratishda xatolik: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Maqola yaratishda xatolik:\n`{str(e)}`\n\nIltimos, qayta urinib ko'ring. Balans yechilmadi.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    return ConversationHandler.END

# ─────────────────────────────────────────────
# Handlerlar — Kurs ishi / BMI
# ─────────────────────────────────────────────

async def ki_get_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Kurs ishi yoki BMI turini qabul qiladi."""
    query = update.callback_query
    await query.answer()
    work_type = query.data.split("_", 2)[2]  # ki_type_kurs_ishi -> kurs_ishi
    context.user_data["ki_type"] = work_type
    type_name = "📚 Kurs ishi" if work_type == "kurs_ishi" else "🎓 Bitiruv malakaviy ishi (BMI)"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("O'zbek tili",  callback_data="ki_lang_uz"),
         InlineKeyboardButton("Ingliz tili",  callback_data="ki_lang_en")],
        [InlineKeyboardButton("Rus tili",     callback_data="ki_lang_ru"),
         InlineKeyboardButton("Kores tili",   callback_data="ki_lang_ko")],
        [InlineKeyboardButton("Xitoy tili",   callback_data="ki_lang_zh"),
         InlineKeyboardButton("Nemis tili",   callback_data="ki_lang_de")],
    ])
    await query.edit_message_text(
        text=f"✅ Tur: *{type_name}*\n\nQaysi tilda yozmoqchisiz?",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return KI_LANGUAGE

async def ki_get_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Kurs ishi: tilni qabul qiladi."""
    query = update.callback_query
    await query.answer()
    language_code = query.data.split("_", 2)[2]  # ki_lang_uz -> uz
    context.user_data["ki_language"] = language_code
    lang_name = LANGUAGE_NAMES.get(language_code, "O'zbek tili")
    work_type = context.user_data.get("ki_type", "kurs_ishi")

    if work_type == "kurs_ishi":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("20 sahifa — 12 000 so'm", callback_data="ki_pages_20")],
            [InlineKeyboardButton("25 sahifa — 14 000 so'm", callback_data="ki_pages_25")],
            [InlineKeyboardButton("35 sahifa — 16 000 so'm", callback_data="ki_pages_35")],
            [InlineKeyboardButton("45 sahifa — 20 000 so'm", callback_data="ki_pages_45")],
        ])
    else:  # bmi
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("50 sahifa — 20 000 so'm", callback_data="ki_pages_50")],
            [InlineKeyboardButton("70 sahifa — 30 000 so'm", callback_data="ki_pages_70")],
            [InlineKeyboardButton("100 sahifa — 45 000 so'm", callback_data="ki_pages_100")],
        ])
    await query.edit_message_text(
        text=f"✅ Til: *{lang_name}*\n\nNecha sahifa bo'lsin?",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return KI_PAGE_COUNT

async def ki_get_page_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Kurs ishi: sahifa sonini qabul qiladi."""
    query = update.callback_query
    await query.answer()
    page_count = int(query.data.split("_")[2])  # ki_pages_25 -> 25
    context.user_data["ki_page_count"] = page_count

    await query.edit_message_text(
        text=f"✅ Hajm: *{page_count} sahifa*\n\nMavzuni kiriting:",
        parse_mode="Markdown"
    )
    return KI_TOPIC

async def ki_get_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Kurs ishi: mavzuni qabul qiladi."""
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    topic = update.message.text.strip()
    if not topic:
        await update.message.reply_text("Iltimos, mavzuni kiriting:")
        return KI_TOPIC
    context.user_data["ki_topic"] = topic
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Shart emas", callback_data="ki_skip_name")],
        [InlineKeyboardButton("✏️ Mavzuni tahrirlash", callback_data="ki_edit_topic")],
    ])
    await update.message.reply_text(
        f"📌 *Mavzu:* {esc_md(topic)}\n\n"
        f"Ism-familiyangizni kiriting:\n"
        f"_(Ixtiyoriy — muqovada ko'rinadi)_",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return KI_NAME_SURNAME

async def ki_edit_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Kurs ishi: mavzuni qayta kiritish."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text="✏️ Yangi mavzuni kiriting:",
        parse_mode="Markdown"
    )
    return KI_EDIT_TOPIC

async def ki_edit_topic_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Kurs ishi: tahrirlangan mavzuni saqlash."""
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    topic = update.message.text.strip()
    if not topic:
        await update.message.reply_text("Iltimos, mavzuni kiriting:")
        return KI_EDIT_TOPIC
    context.user_data["ki_topic"] = topic
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Shart emas", callback_data="ki_skip_name")],
        [InlineKeyboardButton("✏️ Mavzuni tahrirlash", callback_data="ki_edit_topic")],
    ])
    await update.message.reply_text(
        f"✅ *Mavzu yangilandi:* {esc_md(topic)}\n\n"
        f"Ism-familiyangizni kiriting:\n"
        f"_(Ixtiyoriy — muqovada ko'rinadi)_",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return KI_NAME_SURNAME

async def ki_get_name_surname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Kurs ishi: ism-familiyani qabul qiladi."""
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        context.user_data["ki_name_surname"] = ""
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Shart emas", callback_data="ki_skip_university")]])
        await query.edit_message_text(
            text="Universitet nomini kiriting:\n_(Ixtiyoriy)_",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    else:
        context.user_data["ki_name_surname"] = update.message.text.strip()
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Shart emas", callback_data="ki_skip_university")]])
        await update.message.reply_text(
            "Universitet nomini kiriting:\n_(Ixtiyoriy)_",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    return KI_UNIVERSITY

async def ki_get_university(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Kurs ishi: universitetni qabul qiladi."""
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        context.user_data["ki_university"] = ""
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Shart emas", callback_data="ki_skip_faculty")]])
        await query.edit_message_text(
            text="Fakultet nomini kiriting:\n_(Ixtiyoriy)_",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    else:
        context.user_data["ki_university"] = update.message.text.strip()
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Shart emas", callback_data="ki_skip_faculty")]])
        await update.message.reply_text(
            "Fakultet nomini kiriting:\n_(Ixtiyoriy)_",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    return KI_FACULTY

async def ki_get_faculty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Kurs ishi: fakultetni qabul qiladi."""
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        context.user_data["ki_faculty"] = ""
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Shart emas", callback_data="ki_skip_subject")]])
        await query.edit_message_text(
            text="Fan nomini kiriting:\n_(Ixtiyoriy)_",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    else:
        context.user_data["ki_faculty"] = update.message.text.strip()
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Shart emas", callback_data="ki_skip_subject")]])
        await update.message.reply_text(
            "Fan nomini kiriting:\n_(Ixtiyoriy)_",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    return KI_SUBJECT

async def ki_get_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Kurs ishi: fan nomini qabul qiladi."""
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        context.user_data["ki_subject"] = ""
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Shart emas", callback_data="ki_skip_teacher")]])
        await query.edit_message_text(
            text="Ilmiy rahbar (o'qituvchi) ismini kiriting:\n_(Ixtiyoriy)_",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    else:
        context.user_data["ki_subject"] = update.message.text.strip()
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Shart emas", callback_data="ki_skip_teacher")]])
        await update.message.reply_text(
            "Ilmiy rahbar (o'qituvchi) ismini kiriting:\n_(Ixtiyoriy)_",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    return KI_TEACHER

async def ki_get_teacher(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Kurs ishi: o'qituvchini qabul qiladi, so'ng kurs ishini yaratadi."""
    _tr = await topup_message_router(update, context)
    if _tr is not None:
        return _tr
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        context.user_data["ki_teacher"] = ""
        chat_id = query.message.chat_id
        await query.edit_message_text(text="⏳ Yaratilmoqda, biroz kuting...")
    else:
        context.user_data["ki_teacher"] = update.message.text.strip()
        chat_id = update.message.chat_id
        await update.message.reply_text("⏳ Yaratilmoqda, biroz kuting...")

    user_id      = update.effective_user.id
    work_type    = context.user_data.get("ki_type", "kurs_ishi")
    topic        = context.user_data.get("ki_topic", "")
    language     = context.user_data.get("ki_language", "uz")
    page_count   = context.user_data.get("ki_page_count", 25)
    name_surname = context.user_data.get("ki_name_surname", "")
    university   = context.user_data.get("ki_university", "")
    faculty      = context.user_data.get("ki_faculty", "")
    subject      = context.user_data.get("ki_subject", "")
    teacher      = context.user_data.get("ki_teacher", "")

    # Narx aniqlash
    # Sahifa soniga qarab narx aniqlash
    ki_prices = {20: 12000, 25: 14000, 35: 16000, 45: 20000}
    bmi_prices = {50: 20000, 70: 30000, 100: 45000}
    if work_type == 'bmi':
        price = bmi_prices.get(page_count, 20000)
    else:
        price = ki_prices.get(page_count, 12000)
    service_label = "🎓 BMI" if work_type == 'bmi' else "📚 Kurs ishi"

    # Balans tekshirish
    balance = await asyncio.to_thread(db.get_balance, user_id)
    if balance < price:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Balans to'ldirish", callback_data="topup_start")]
        ])
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"❌ *Balansingiz yetarli emas!*\n\n"
                f"💰 Joriy balans: *{balance:,} so'm*\n"
                f"💳 Kerakli summa: *{price:,} so'm*\n\n"
                f"Iltimos, avval balansni to'ldiring:"
            ),
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    await context.bot.send_chat_action(chat_id=chat_id, action="upload_document")
    try:
        doc_bytes = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: generate_kurs_ishi(
                topic=topic,
                language=language,
                work_type=work_type,
                page_count=page_count,
                name_surname=name_surname,
                university=university,
                faculty=faculty,
                subject=subject,
                teacher=teacher,
            )
        )
        safe_topic = "".join(c for c in topic[:30] if c.isalnum() or c in " _-").strip()
        filename = f"{safe_topic or 'kurs_ishi'}.docx"

        sent_msg = await context.bot.send_document(
            chat_id=chat_id,
            document=doc_bytes,
            filename=filename,
            caption=(
                f"✅ {esc_md(topic)} — {service_label} tayyor!\n"
                f"📄 Taxminiy {page_count} sahifa | 📎 DOCX\n\n"
                f"📚 Biz bilan ishingiz oson!\n"
                f"🤖 @slidego\n"
                f"📢 t.me/slidego"
            ),
        )
        _file_id = sent_msg.document.file_id if sent_msg and sent_msg.document else None
        await archive_send_document(
            bot=context.bot,
            user=update.effective_user,
            service_name=service_label,
            topic=topic,
            language=language,
            page_count=page_count,
            price=price,
            document_bytes=doc_bytes,
            filename=filename,
        )
        await asyncio.to_thread(db.deduct_balance, user_id, price)
        await asyncio.to_thread(db.log_generation, user_id, work_type, topic, price, _file_id, filename)
        new_balance = await asyncio.to_thread(db.get_balance, user_id)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"💰 Balans: *{new_balance:,} so'm*\n\nYana biror narsa kerakmi?",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Kurs ishi yaratishda xatolik: {type(e).__name__}: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Yaratishda xatolik:\n`{str(e)}`\n\nIltimos, qayta urinib ko'ring. Balans yechilmadi.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    return ConversationHandler.END

# ─────────────────────────────────────────────
# Handlerlar — Tezis
# ─────────────────────────────────────────────

async def tz_get_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Tezis turini qabul qiladi."""
    query = update.callback_query
    await query.answer()
    tz_type = query.data.replace("tz_type_", "")
    context.user_data["tz_type"] = tz_type
    type_names = {
        "konferensiya": "Konferensiya tezisi",
        "olimpiada": "Olimpiada tezisi",
        "seminar": "Seminar tezisi",
        "dissertatsiya": "Dissertatsiya tezisi",
    }
    type_name = type_names.get(tz_type, "Tezis")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("O'zbek tili", callback_data="tz_lang_uz"),
         InlineKeyboardButton("Ingliz tili", callback_data="tz_lang_en")],
        [InlineKeyboardButton("Rus tili", callback_data="tz_lang_ru"),
         InlineKeyboardButton("Kores tili", callback_data="tz_lang_ko")],
        [InlineKeyboardButton("Xitoy tili", callback_data="tz_lang_zh"),
         InlineKeyboardButton("Nemis tili", callback_data="tz_lang_de")],
    ])
    await query.edit_message_text(
        f"✅ *{type_name}* tanlandi.\n\nQaysi tilda yozilsin?",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return TZ_LANGUAGE

async def tz_get_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Tezis tilini qabul qiladi."""
    query = update.callback_query
    await query.answer()
    lang = query.data.replace("tz_lang_", "")
    context.user_data["tz_lang"] = lang
    lang_names = {"uz": "O'zbek", "en": "Ingliz", "ru": "Rus", "ko": "Kores", "zh": "Xitoy", "de": "Nemis"}
    lang_name = lang_names.get(lang, lang)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("1 sahifa — 2 000 so'm", callback_data="tz_pages_1")],
        [InlineKeyboardButton("2 sahifa — 2 000 so'm", callback_data="tz_pages_2")],
        [InlineKeyboardButton("3 sahifa — 2 000 so'm", callback_data="tz_pages_3")],
        [InlineKeyboardButton("5 sahifa — 2 000 so'm", callback_data="tz_pages_5")],
    ])
    await query.edit_message_text(
        f"✅ *{lang_name} tili* tanlandi.\n\nNecha sahifali tezis kerak?",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return TZ_PAGE_COUNT

async def tz_get_page_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Tezis sahifa sonini qabul qiladi."""
    query = update.callback_query
    await query.answer()
    pages = int(query.data.replace("tz_pages_", ""))
    context.user_data["tz_pages"] = pages
    await query.edit_message_text(
        f"✅ *{pages} sahifa* tanlandi.\n\nTezis mavzusini kiriting:",
        parse_mode="Markdown"
    )
    return TZ_TOPIC

async def tz_get_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Tezis mavzusini qabul qiladi."""
    topic = update.message.text.strip()
    context.user_data["tz_topic"] = topic
    await update.message.reply_text(
        f"✅ Mavzu: *{esc_md(topic)}*\n\nMuallif ism-familiyasini kiriting:\n(Ixtiyoriy — o'tkazib yuborish uchun \"- \" yozing)",
        parse_mode="Markdown"
    )
    return TZ_NAME_SURNAME

async def tz_get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Tezis muallif ismini qabul qiladi."""
    name = update.message.text.strip()
    if name == "-":
        name = ""
    context.user_data["tz_name"] = name
    await update.message.reply_text(
        "Muassasa/universitet nomini kiriting:\n(Ixtiyoriy — o'tkazib yuborish uchun \"-\" yozing)"
    )
    return TZ_INSTITUTION

async def tz_get_institution(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muassasani qabul qiladi, so'ng tezisni yaratadi."""
    institution = update.message.text.strip()
    if institution == "-":
        institution = ""
    context.user_data["tz_institution"] = institution

    # Ma'lumotlarni olish
    topic = context.user_data.get("tz_topic", "")
    tz_type = context.user_data.get("tz_type", "konferensiya")
    lang = context.user_data.get("tz_lang", "uz")
    pages = context.user_data.get("tz_pages", 2)
    name = context.user_data.get("tz_name", "")
    user = update.effective_user

    # Balans tekshiruvi
    price = SERVICE_PRICES['tezis']
    user_data = await asyncio.to_thread(db.get_user, user.id)
    balance = user_data['balance'] if user_data else 0
    if balance < price:
        await update.message.reply_text(
            f"⚠️ Balansingiz yetarli emas!\n"
            f"💰 Kerakli: {price:,} so'm | Mavjud: {balance:,} so'm\n\n"
            f"Balansni to'ldirish uchun \"Balans & Referral\" bo'limiga o'ting.",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END

    type_names = {
        "konferensiya": "Konferensiya tezisi",
        "olimpiada": "Olimpiada tezisi",
        "seminar": "Seminar tezisi",
        "dissertatsiya": "Dissertatsiya tezisi",
    }
    lang_names = {"uz": "O'zbek", "en": "Ingliz", "ru": "Rus", "ko": "Kores", "zh": "Xitoy", "de": "Nemis"}

    await update.message.reply_text(
        f"⏳ *{type_names.get(tz_type, 'Tezis')}* yaratilmoqda...\n"
        f"📌 Mavzu: {esc_md(topic)}\n"
        f"🌍 Til: {lang_names.get(lang, lang)} | 📄 {pages} sahifa\n\n"
        f"Bir daqiqa kuting...",
        parse_mode="Markdown"
    )
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_document")
    try:
        # Tezis yaratish
        doc_bytes = await generate_tezis(
            topic=topic,
            tezis_type=tz_type,
            lang=lang,
            pages=pages,
            author=name,
            institution=institution,
        )

        # Balansdan yechish
        await asyncio.to_thread(db.deduct_balance, user.id, price)
        await asyncio.to_thread(db.log_generation, user.id, 'tezis', topic, price)

        # Foydalanuvchiga yuborish
        file_name = f"tezis_{topic[:30].replace(' ', '_')}.docx"
        doc_bytes.seek(0)
        caption = (
            f"✅ {topic} — tezis tayyor!\n"
            f"📄 {pages} sahifa | 📎 DOCX\n\n"
            f"📚 Biz bilan ishingiz oson!\n"
            f"🤖 @slidego\n"
            f"📢 t.me/slidego"
        )
        sent_msg = await context.bot.send_document(
            chat_id=user.id,
            document=doc_bytes,
            filename=file_name,
            caption=caption
        )

        # Arxiv kanalga yuborish
        archive_doc = BytesIO(sent_msg.document.file_id.encode() if isinstance(sent_msg.document.file_id, str) else b"")
        doc_bytes.seek(0)
        archive_doc = BytesIO(doc_bytes.read())
        archive_doc.seek(0)
        await archive_send_document(
            context.bot,
            document=archive_doc,
            filename=file_name,
            caption=f"📜 Tezis | {esc_md(topic)} | {lang_names.get(lang, lang)} | {pages} sah | User: {user.id}"
        )

        await update.message.reply_text(
            f"🎉 Tezis muvaffaqiyatli yaratildi!\n"
            f"💰 Balansingizdan {price:,} so'm yechildi.",
            reply_markup=get_main_menu_keyboard()
        )

    except Exception as e:
        logger.error(f"Tezis yaratishda xatolik: {e}")
        await update.message.reply_text(
            "❌ Tezis yaratishda xatolik yuz berdi. Iltimos, qayta urinib ko'ring.",
            reply_markup=get_main_menu_keyboard()
        )

    return ConversationHandler.END

# ─────────────────────────────────────────────
# Handlerlar — Test tuzish
# ─────────────────────────────────────────────

async def ts_get_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Test tilini qabul qiladi."""
    query = update.callback_query
    await query.answer()
    lang = query.data.replace("ts_lang_", "")
    context.user_data["ts_lang"] = lang
    lang_names = {"uz": "O'zbek", "en": "Ingliz", "ru": "Rus", "ko": "Kores", "zh": "Xitoy", "de": "Nemis"}
    lang_name = lang_names.get(lang, lang)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📌 10 ta savol — 1 000 so'm", callback_data="ts_count_10")],
        [InlineKeyboardButton("📚 20 ta savol — 2 000 so'm", callback_data="ts_count_20")],
        [InlineKeyboardButton("📝 30 ta savol — 2 000 so'm", callback_data="ts_count_30")],
        [InlineKeyboardButton("🏆 50 ta savol — 3 000 so'm", callback_data="ts_count_50")],
    ])
    await query.edit_message_text(
        f"✅ *{lang_name} tili* tanlandi.\n\nNechta savol kerak?",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return TS_COUNT

async def ts_get_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Savol sonini qabul qiladi."""
    query = update.callback_query
    await query.answer()
    count = int(query.data.replace("ts_count_", ""))
    context.user_data["ts_count"] = count
    price = SERVICE_PRICES.get(f"test_{count}", 1000)
    await query.edit_message_text(
        f"✅ *{count} ta savol* tanlandi (narx: {price:,} so'm).\n\n"
        f"Test mavzusini kiriting:\n"
        f"_(Masalan: Biologiya — hujayra, Tarix — Amir Temur, Python dasturlash...)_",
        parse_mode="Markdown"
    )
    return TS_TOPIC

async def ts_get_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Test mavzusini qabul qiladi."""
    topic = update.message.text.strip()
    context.user_data["ts_topic"] = topic
    await update.message.reply_text(
        f"✅ Mavzu: *{esc_md(topic)}*\n\nMuallif / o'qituvchi ismini kiriting:\n"
        f"_(Ixtiyoriy — o'tkazib yuborish uchun \"-\" yozing)_",
        parse_mode="Markdown"
    )
    return TS_AUTHOR

async def ts_get_author(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muallif ismini qabul qiladi, so'ng testni yaratadi."""
    author = update.message.text.strip()
    if author == "-":
        author = ""
    context.user_data["ts_author"] = author

    # Ma'lumotlarni olish
    topic = context.user_data.get("ts_topic", "")
    lang = context.user_data.get("ts_lang", "uz")
    count = context.user_data.get("ts_count", 10)
    user = update.effective_user

    # Narx
    price = SERVICE_PRICES.get(f"test_{count}", 1000)

    # Balans tekshiruvi
    user_data = await asyncio.to_thread(db.get_user, user.id)
    balance = user_data['balance'] if user_data else 0
    if balance < price:
        await update.message.reply_text(
            f"⚠️ Balansingiz yetarli emas!\n"
            f"💰 Kerakli: {price:,} so'm | Mavjud: {balance:,} so'm\n\n"
            f"Balansni to'ldirish uchun \"Balans & Referral\" bo'limiga o'ting.",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END

    lang_names = {"uz": "O'zbek", "en": "Ingliz", "ru": "Rus", "ko": "Kores", "zh": "Xitoy", "de": "Nemis"}

    await update.message.reply_text(
        f"⏳ *{esc_md(topic)}* mavzusida *{count} ta savol* yaratilmoqda...\n"
        f"🌍 Til: {lang_names.get(lang, lang)}\n\n"
        f"Bir daqiqa kuting...",
        parse_mode="Markdown"
    )
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_document")
    try:
        # Test yaratish (2 ta DOCX)
        question_doc, answer_doc = await generate_test(
            topic=topic,
            count=count,
            lang=lang,
            author=author,
        )

        # Balansdan yechish
        await asyncio.to_thread(db.deduct_balance, user.id, price)
        await asyncio.to_thread(db.log_generation, user.id, 'test', topic, price)

        # Savol varaqasini yuborish
        q_filename = f"test_savollar_{topic[:25].replace(' ', '_')}.docx"
        question_doc.seek(0)
        await context.bot.send_document(
            chat_id=user.id,
            document=question_doc,
            filename=q_filename,
            caption=(
                f"📝 Savol varaqasi — {topic}\n"
                f"📌 {count} ta savol | DOCX\n\n"
                f"📚 Biz bilan ishingiz oson!\n"
                f"🤖 @slidego | 📢 t.me/slidego"
            )
        )

        # Javoblar varaqasini yuborish
        a_filename = f"test_javoblar_{topic[:25].replace(' ', '_')}.docx"
        answer_doc.seek(0)
        await context.bot.send_document(
            chat_id=user.id,
            document=answer_doc,
            filename=a_filename,
            caption=(
                f"✅ Javoblar varaqasi — {topic}\n"
                f"📌 {count} ta savol | DOCX\n\n"
                f"📚 Biz bilan ishingiz oson!\n"
                f"🤖 @slidego | 📢 t.me/slidego"
            )
        )

        # Arxiv kanalga yuborish (savol varaqasi)
        question_doc.seek(0)
        archive_q = BytesIO(question_doc.read())
        archive_q.seek(0)
        await archive_send_document(
            bot=context.bot,
            user=user,
            service_name="Test tuzish",
            topic=topic,
            language=lang_names.get(lang, lang),
            page_count=count,
            price=price,
            document_bytes=archive_q,
            filename=q_filename,
        )

        await update.message.reply_text(
            f"🎉 Test muvaffaqiyatli yaratildi!\n"
            f"📝 Savol varaqasi + ✅ Javoblar varaqasi yuborildi.\n"
            f"💰 Balansingizdan {price:,} so'm yechildi.",
            reply_markup=get_main_menu_keyboard()
        )

    except Exception as e:
        import traceback
        logger.error(f"Test yaratishda xatolik: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        await update.message.reply_text(
            f"❌ Test yaratishda xatolik yuz berdi.\n"
            f"`{type(e).__name__}: {str(e)[:200]}`\n\n"
            f"Iltimos, qayta urinib ko'ring. Balans yechilmadi.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    return ConversationHandler.END
# ─────────────────────────────────────────────
# Handlerlar — Glossaryry
# ─────────────────────────────────────────────

async def gl_get_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Glossary tilini qabul qiladi."""
    query = update.callback_query
    await query.answer()
    lang = query.data.replace("gl_lang_", "")
    context.user_data["gl_lang"] = lang
    lang_names = {"uz": "O'zbek", "en": "Ingliz", "ru": "Rus", "ko": "Kores", "zh": "Xitoy", "de": "Nemis"}
    lang_name = lang_names.get(lang, lang)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📌 Kichik (15 ta atama) — 1 000 so'm", callback_data="gl_size_small")],
        [InlineKeyboardButton("📚 O'rta (30 ta atama) — 2 000 so'm", callback_data="gl_size_medium")],
        [InlineKeyboardButton("🏆 Katta (50 ta atama) — 3 000 so'm", callback_data="gl_size_large")],
    ])
    await query.edit_message_text(
        f"✅ *{lang_name} tili* tanlandi.\n\nGlossary hajmini tanlang:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return GL_SIZE

async def gl_get_size(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Glossary hajmini qabul qiladi."""
    query = update.callback_query
    await query.answer()
    size = query.data.replace("gl_size_", "")
    context.user_data["gl_size"] = size
    size_labels = {"small": "Kichik (15 ta)", "medium": "O'rta (30 ta)", "large": "Katta (50 ta)"}
    size_label = size_labels.get(size, size)
    await query.edit_message_text(
        f"✅ *{size_label}* tanlandi.\n\nGlossary mavzusini kiriting:\n"
        f"_(Masalan: Iqtisodiyot, Biologiya, Dasturlash, Huquq...)_",
        parse_mode="Markdown"
    )
    return GL_TOPIC

async def gl_get_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Glossary mavzusini qabul qiladi."""
    topic = update.message.text.strip()
    context.user_data["gl_topic"] = topic
    await update.message.reply_text(
        f"✅ Mavzu: *{esc_md(topic)}*\n\nMuallif ism-familiyasini kiriting:\n"
        f"_(Ixtiyoriy — o'tkazib yuborish uchun \"-\" yozing)_",
        parse_mode="Markdown"
    )
    return GL_AUTHOR

async def gl_get_author(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muallif ismini qabul qiladi, so'ng glossaryni yaratadi."""
    author = update.message.text.strip()
    if author == "-":
        author = ""
    context.user_data["gl_author"] = author

    # Ma'lumotlarni olish
    topic = context.user_data.get("gl_topic", "")
    lang = context.user_data.get("gl_lang", "uz")
    size = context.user_data.get("gl_size", "small")
    user = update.effective_user
    chat_id = update.effective_chat.id

    # Narx aniqlash
    price_key = f"glossary_{size}"
    price = SERVICE_PRICES.get(price_key, 1000)

    # Balans tekshiruvi
    user_data = await asyncio.to_thread(db.get_user, user.id)
    balance = user_data['balance'] if user_data else 0
    if balance < price:
        await update.message.reply_text(
            f"⚠️ Balansingiz yetarli emas!\n"
            f"💰 Kerakli: {price:,} so'm | Mavjud: {balance:,} so'm\n\n"
            f"Balansni to'ldirish uchun \"Balans & Referral\" bo'limiga o'ting.",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END

    size_labels = {"small": "Kichik (15 ta)", "medium": "O'rta (30 ta)", "large": "Katta (50 ta)"}
    lang_names = {"uz": "O'zbek", "en": "Ingliz", "ru": "Rus", "ko": "Kores", "zh": "Xitoy", "de": "Nemis"}

    await update.message.reply_text(
        f"⏳ *{esc_md(topic)}* mavzusida glossary yaratilmoqda...\n"
        f"📌 Hajm: {size_labels.get(size, size)} | 🌍 Til: {lang_names.get(lang, lang)}\n\n"
        f"Bir daqiqa kuting...",
        parse_mode="Markdown"
    )
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_document")
    try:
        # Glossary yaratish
        doc_bytes = await generate_glossary(
            topic=topic,
            size=size,
            lang=lang,
            author=author,
        )

        # Balansdan yechish
        await asyncio.to_thread(db.deduct_balance, user.id, price)
        await asyncio.to_thread(db.log_generation, user.id, 'glossary', topic, price)

        # Foydalanuvchiga yuborish
        file_name = f"glossary_{topic[:30].replace(' ', '_')}.docx"
        doc_bytes.seek(0)
        caption = (
            f"✅ {topic} — Glossary tayyor!\n"
            f"📌 {size_labels.get(size, size)} | 📎 DOCX\n\n"
            f"📚 Biz bilan ishingiz oson!\n"
            f"🤖 @slidego\n"
            f"📢 t.me/slidego"
        )
        sent_msg = await context.bot.send_document(
            chat_id=user.id,
            document=doc_bytes,
            filename=file_name,
            caption=caption
        )

        # Arxiv kanalga yuborish
        doc_bytes.seek(0)
        archive_doc = BytesIO(doc_bytes.read())
        archive_doc.seek(0)
        await archive_send_document(
            bot=context.bot,
            user=user,
            service_name="Glossary",
            topic=topic,
            language=lang_names.get(lang, lang),
            page_count=size_labels.get(size, size),
            price=price,
            document_bytes=archive_doc,
            filename=file_name,
        )

        await update.message.reply_text(
            f"🎉 Glossary muvaffaqiyatli yaratildi!\n"
            f"💰 Balansingizdan {price:,} so'm yechildi.",
            reply_markup=get_main_menu_keyboard()
        )

    except Exception as e:
        logger.error(f"Glossary yaratishda xatolik: {e}")
        await update.message.reply_text(
            "❌ Glossary yaratishda xatolik yuz berdi. Iltimos, qayta urinib ko'ring.",
            reply_markup=get_main_menu_keyboard()
        )

    return ConversationHandler.END
# ─────────────────────────────────────────────
# Handlerlar — Krossvord
# ─────────────────────────────────────────────
async def kr_get_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Krossvord tilini qabul qiladi."""
    query = update.callback_query
    await query.answer()
    lang = query.data.replace("kr_lang_", "")
    context.user_data["kr_lang"] = lang
    lang_names = {"uz": "O'zbek", "en": "Ingliz", "ru": "Rus", "ko": "Kores", "zh": "Xitoy", "de": "Nemis"}
    lang_name = lang_names.get(lang, lang)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📌 10 ta so'z — 1 000 so'm", callback_data="kr_count_10")],
        [InlineKeyboardButton("📚 15 ta so'z — 2 000 so'm", callback_data="kr_count_15")],
        [InlineKeyboardButton("🏆 20 ta so'z — 2 000 so'm", callback_data="kr_count_20")],
    ])
    await query.edit_message_text(
        f"✅ Til: {lang_name}\n\nNechta so'zli krossvord kerak?",
        reply_markup=keyboard
    )
    return KR_COUNT

async def kr_get_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Krossvord so'z sonini qabul qiladi."""
    query = update.callback_query
    await query.answer()
    count = int(query.data.replace("kr_count_", ""))
    context.user_data["kr_count"] = count
    price = SERVICE_PRICES.get(f"krossvord_{count}", 1000)
    await query.edit_message_text(
        f"✅ So'zlar soni: {count} ta\n"
        f"💰 Narx: {price:,} so'm\n\n"
        f"Krossvord mavzusini kiriting:\n"
        f"_(Masalan: Biologiya — hujayra, Matematika, Tarix)_",
        parse_mode="Markdown"
    )
    return KR_TOPIC

async def kr_get_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Krossvord mavzusini qabul qiladi."""
    topic = update.message.text.strip()
    context.user_data["kr_topic"] = topic
    await update.message.reply_text(
        f"✅ Mavzu: *{esc_md(topic)}*\n\nMuallif / o'qituvchi ismini kiriting:\n"
        f"_(Ixtiyoriy — o'tkazib yuborish uchun \"-\" yozing)_",
        parse_mode="Markdown"
    )
    return KR_AUTHOR

async def kr_get_author(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muallif ismini qabul qiladi, so'ng krossvord yaratadi."""
    author = update.message.text.strip()
    if author == "-":
        author = ""
    context.user_data["kr_author"] = author
    topic = context.user_data.get("kr_topic", "")
    lang = context.user_data.get("kr_lang", "uz")
    count = context.user_data.get("kr_count", 10)
    user = update.effective_user
    price = SERVICE_PRICES.get(f"krossvord_{count}", 1000)
    # Balans tekshiruvi
    user_data = await asyncio.to_thread(db.get_user, user.id)
    balance = user_data['balance'] if user_data else 0
    if balance < price:
        await update.message.reply_text(
            f"⚠️ Balansingiz yetarli emas!\n"
            f"💰 Kerakli: {price:,} so'm | Mavjud: {balance:,} so'm\n\n"
            f"Balansni to'ldirish uchun \"Balans & Referral\" bo'limiga o'ting.",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END
    lang_names = {"uz": "O'zbek", "en": "Ingliz", "ru": "Rus", "ko": "Kores", "zh": "Xitoy", "de": "Nemis"}
    await update.message.reply_text(
        f"⏳ *{esc_md(topic)}* mavzusida *{count} ta so'zli* krossvord yaratilmoqda...\n"
        f"🌍 Til: {lang_names.get(lang, lang)}\n\n"
        f"Bir daqiqa kuting...",
        parse_mode="Markdown"
    )
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_document")
    try:
        empty_doc, answer_doc = await generate_crossword(
            topic=topic,
            count=count,
            lang=lang,
            author=author,
        )
        # Balansdan yechish
        await asyncio.to_thread(db.deduct_balance, user.id, price)
        await asyncio.to_thread(db.log_generation, user.id, 'krossvord', topic, price)
        # Bo'sh to'r yuborish
        q_filename = f"krossvord_{topic[:25].replace(' ', '_')}.docx"
        empty_doc.seek(0)
        await context.bot.send_document(
            chat_id=user.id,
            document=empty_doc,
            filename=q_filename,
            caption=(
                f"🧩 Krossvord — {topic}\n"
                f"📌 {count} ta so'z | DOCX\n\n"
                f"Biz bilan ishingiz oson!\n"
                f"@slidego | t.me/slidego"
            )
        )
        # Javobli to'r yuborish
        a_filename = f"krossvord_javob_{topic[:25].replace(' ', '_')}.docx"
        answer_doc.seek(0)
        await context.bot.send_document(
            chat_id=user.id,
            document=answer_doc,
            filename=a_filename,
            caption=(
                f"✅ Krossvord javoblari — {topic}\n"
                f"📌 {count} ta so'z | DOCX\n\n"
                f"Biz bilan ishingiz oson!\n"
                f"@slidego | t.me/slidego"
            )
        )
        # Arxiv kanalga yuborish
        empty_doc.seek(0)
        archive_doc = BytesIO(empty_doc.read())
        archive_doc.seek(0)
        await archive_send_document(
            bot=context.bot,
            user=user,
            service_name="Krossvord",
            topic=topic,
            language=lang_names.get(lang, lang),
            page_count=count,
            price=price,
            document_bytes=archive_doc,
            filename=q_filename,
        )
        await update.message.reply_text(
            f"🎉 Krossvord muvaffaqiyatli yaratildi!\n"
            f"📝 Bo'sh to'r + ✅ Javobli to'r yuborildi.\n"
            f"💰 Balansingizdan {price:,} so'm yechildi.",
            reply_markup=get_main_menu_keyboard()
        )
    except Exception as e:
        import traceback
        logger.error(f"Krossvord yaratishda xatolik: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        await update.message.reply_text(
            f"❌ Krossvord yaratishda xatolik yuz berdi.\n"
            f"`{type(e).__name__}: {str(e)[:200]}`\n\n"
            f"Iltimos, qayta urinib ko'ring. Balans yechilmadi.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    return ConversationHandler.END
# ─────────────────────────────────────────────
# Handlerlar — Insho / Esse
# ─────────────────────────────────────────────
async def in_get_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Insho turini qabul qiladi."""
    query = update.callback_query
    await query.answer()
    insho_type = query.data.replace("in_type_", "")
    context.user_data["in_type"] = insho_type
    type_labels = {
        "erkin": "✍️ Erkin insho",
        "tahliliy": "🔍 Tahliliy esse",
        "argumentativ": "💡 Argumentativ esse",
        "tavsifiy": "📖 Tavsifiy insho",
        "muqoyasali": "⚖️ Muqoyasali esse",
    }
    type_label = type_labels.get(insho_type, insho_type)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇺🇿 O'zbek tili",  callback_data="in_lang_uz"),
         InlineKeyboardButton("🇬🇧 Ingliz tili",  callback_data="in_lang_en")],
        [InlineKeyboardButton("🇷🇺 Rus tili",     callback_data="in_lang_ru"),
         InlineKeyboardButton("🇰🇷 Kores tili",   callback_data="in_lang_ko")],
        [InlineKeyboardButton("🇨🇳 Xitoy tili",   callback_data="in_lang_zh"),
         InlineKeyboardButton("🇩🇪 Nemis tili",   callback_data="in_lang_de")],
    ])
    await query.edit_message_text(
        f"✅ Tur: {type_label}\n\nQaysi tilda insho yozmoqchisiz?",
        reply_markup=keyboard
    )
    return IN_LANGUAGE

async def in_get_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Insho tilini qabul qiladi."""
    query = update.callback_query
    await query.answer()
    lang = query.data.replace("in_lang_", "")
    context.user_data["in_lang"] = lang
    lang_names = {"uz": "O'zbek", "en": "Ingliz", "ru": "Rus", "ko": "Kores", "zh": "Xitoy", "de": "Nemis"}
    lang_name = lang_names.get(lang, lang)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📌 1 sahifa — 1 000 so'm", callback_data="in_pages_1")],
        [InlineKeyboardButton("📚 2 sahifa — 2 000 so'm", callback_data="in_pages_2")],
        [InlineKeyboardButton("🏆 3 sahifa — 2 000 so'm", callback_data="in_pages_3")],
        [InlineKeyboardButton("🌟 5 sahifa — 3 000 so'm", callback_data="in_pages_5")],
    ])
    await query.edit_message_text(
        f"✅ Til: {lang_name}\n\nNecha sahifali insho kerak?",
        reply_markup=keyboard
    )
    return IN_PAGE_COUNT

async def in_get_page_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sahifa sonini qabul qiladi."""
    query = update.callback_query
    await query.answer()
    pages = int(query.data.replace("in_pages_", ""))
    context.user_data["in_pages"] = pages
    price = SERVICE_PRICES.get(f"insho_{pages}", 1000)
    await query.edit_message_text(
        f"✅ Sahifa soni: {pages} ta\n"
        f"💰 Narx: {price:,} so'm\n\n"
        f"Insho mavzusini kiriting:\n"
        f"_(Masalan: Ekologiya muammolari, Sun'iy intellekt va kelajak)_",
        parse_mode="Markdown"
    )
    return IN_TOPIC

async def in_get_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Insho mavzusini qabul qiladi."""
    topic = update.message.text.strip()
    context.user_data["in_topic"] = topic
    await update.message.reply_text(
        f"✅ Mavzu: *{esc_md(topic)}*\n\nIsm-familiyangizni kiriting:\n"
        f"_(Ixtiyoriy — o'tkazib yuborish uchun \"-\" yozing)_",
        parse_mode="Markdown"
    )
    return IN_NAME_SURNAME

async def in_get_name_surname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ism-familiyani qabul qiladi."""
    author = update.message.text.strip()
    if author == "-":
        author = ""
    context.user_data["in_author"] = author
    await update.message.reply_text(
        f"Muassasa / maktab / universitetingiz nomini kiriting:\n"
        f"_(Ixtiyoriy — o'tkazib yuborish uchun \"-\" yozing)_",
        parse_mode="Markdown"
    )
    return IN_INSTITUTION

async def in_get_institution(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muassasa nomini qabul qiladi, so'ng insho yaratadi."""
    institution = update.message.text.strip()
    if institution == "-":
        institution = ""
    context.user_data["in_institution"] = institution

    topic = context.user_data.get("in_topic", "")
    lang = context.user_data.get("in_lang", "uz")
    pages = context.user_data.get("in_pages", 2)
    insho_type = context.user_data.get("in_type", "erkin")
    author = context.user_data.get("in_author", "")
    user = update.effective_user
    price = SERVICE_PRICES.get(f"insho_{pages}", 1000)

    # Balans tekshiruvi
    user_data = await asyncio.to_thread(db.get_user, user.id)
    balance = user_data['balance'] if user_data else 0
    if balance < price:
        await update.message.reply_text(
            f"⚠️ Balansingiz yetarli emas!\n"
            f"💰 Kerakli: {price:,} so'm | Mavjud: {balance:,} so'm\n\n"
            f"Balansni to'ldirish uchun \"Balans & Referral\" bo'limiga o'ting.",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END

    type_labels = {
        "erkin": "Erkin insho", "tahliliy": "Tahliliy esse",
        "argumentativ": "Argumentativ esse", "tavsifiy": "Tavsifiy insho",
        "muqoyasali": "Muqoyasali esse",
    }
    lang_names = {"uz": "O'zbek", "en": "Ingliz", "ru": "Rus", "ko": "Kores", "zh": "Xitoy", "de": "Nemis"}

    await update.message.reply_text(
        f"⏳ *{esc_md(topic)}* mavzusida *{pages} sahifali {type_labels.get(insho_type, 'insho')}* yozilmoqda...\n"
        f"🌍 Til: {lang_names.get(lang, lang)}\n\n"
        f"Bir daqiqa kuting...",
        parse_mode="Markdown"
    )
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_document")
    try:
        doc_bytes = await generate_insho(
            topic=topic,
            insho_type=insho_type,
            lang=lang,
            pages=pages,
            author=author,
            institution=institution,
        )
        # Balansdan yechish
        await asyncio.to_thread(db.deduct_balance, user.id, price)
        await asyncio.to_thread(db.log_generation, user.id, 'insho', topic, price)

        filename = f"insho_{topic[:25].replace(' ', '_')}.docx"
        doc_bytes.seek(0)
        await context.bot.send_document(
            chat_id=user.id,
            document=doc_bytes,
            filename=filename,
            caption=(
                f"✍️ Insho — {topic}\n"
                f"📌 {pages} sahifa | {type_labels.get(insho_type, 'insho')} | DOCX\n\n"
                f"Biz bilan ishingiz oson!\n"
                f"@slidego | t.me/slidego"
            )
        )
        # Arxiv kanalga yuborish
        doc_bytes.seek(0)
        archive_doc = BytesIO(doc_bytes.read())
        archive_doc.seek(0)
        await archive_send_document(
            bot=context.bot,
            user=user,
            service_name="Insho / Esse",
            topic=topic,
            language=lang_names.get(lang, lang),
            page_count=pages,
            price=price,
            document_bytes=archive_doc,
            filename=filename,
        )
        await update.message.reply_text(
            f"🎉 Insho muvaffaqiyatli yaratildi!\n"
            f"💰 Balansingizdan {price:,} so'm yechildi.",
            reply_markup=get_main_menu_keyboard()
        )
    except Exception as e:
        import traceback
        logger.error(f"Insho yaratishda xatolik: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        await update.message.reply_text(
            f"❌ Insho yaratishda xatolik yuz berdi.\n"
            f"`{type(e).__name__}: {str(e)[:200]}`\n\n"
            f"Iltimos, qayta urinib ko'ring. Balans yechilmadi.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    return ConversationHandler.END
# ─────────────────────────────────────────────
# Handlerlar — Hujjat & Dizayn
# ─────────────────────────────────────────────
HJ_LANG_NAMES = {"uz": "O'zbek", "en": "Ingliz", "ru": "Rus", "ko": "Kores", "zh": "Xitoy", "de": "Nemis"}

HJ_LANG_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🇺🇿 O'zbek", callback_data="hj_lang_uz"),
     InlineKeyboardButton("🇧🇬 Ingliz", callback_data="hj_lang_en")],
    [InlineKeyboardButton("🇷🇺 Rus",    callback_data="hj_lang_ru"),
     InlineKeyboardButton("🇰🇷 Kores",  callback_data="hj_lang_ko")],
    [InlineKeyboardButton("🇨🇳 Xitoy",  callback_data="hj_lang_zh"),
     InlineKeyboardButton("🇩🇪 Nemis",  callback_data="hj_lang_de")],
])

async def back_to_main_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Barcha xizmatlar uchun universal bosh menyuga qaytish handler."""
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    try:
        await query.message.delete()
    except Exception:
        pass
    await query.message.reply_text(
        "Bosh menyudasiz. Xizmatni tanlang:",
        reply_markup=get_main_menu_keyboard()
    )
    return ConversationHandler.END

async def hj_back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    await query.message.reply_text(
        "Bosh menyudasiz. Xizmatni tanlang:",
        reply_markup=get_main_menu_keyboard()
    )
    return ConversationHandler.END

async def hj_back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Rezyume / CV",       callback_data="hj_rezyume")],
        [InlineKeyboardButton("📜 Motivatsion xat",    callback_data="hj_motivatsion")],
        [InlineKeyboardButton("📊 Jadval & Diagramma", callback_data="hj_jadval")],
        [InlineKeyboardButton("🗺️ Kontsept xarita",    callback_data="hj_mindmap")],
    ])
    await query.edit_message_text(
        "📂 *Hujjat & Dizayn xizmatlari*\n\n"
        "• 📄 Rezyume / CV — 3 000 so'm\n"
        "• 📜 Motivatsion xat — 2 000 so'm\n"
        "• 📊 Jadval & Diagramma — 2 000 so'm\n"
        "• 🗺️ Kontsept xarita — 2 000 so'm\n\n"
        "Xizmatni tanlang:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return HJ_MENU

async def hj_get_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Hujjat submenu tanlovi."""
    query = update.callback_query
    await query.answer()
    service = query.data.replace("hj_", "")
    context.user_data["hj_service"] = service

    # Rezyume uchun alohida yangi flow
    if service == "rezyume":
        context.user_data["cv_data"] = {}
        await query.edit_message_text(
            "📄 *Rezyume / CV yaratish*\n\n"
            "Professional rezyumengizni yaratish uchun bir nechta savollarga javob bering.\n"
            "💰 Narx: 3 000 so'm\n\n"
            "🌍 Qaysi tilda yaratilsin?",
            parse_mode="Markdown",
            reply_markup=CV_LANG_KEYBOARD
        )
        return CV_LANG
    service_info = {
        "rezyume":     ("📄 Rezyume / CV",       "Ism-familiyangizni kiriting:",                  3000),
        "motivatsion": ("📜 Motivatsion xat",  "Ism-familiyangizni kiriting:",                  2000),
        "jadval":      ("📊 Jadval & Diagramma", "Jadval mavzusini kiriting:\n(masalan: O'zbekiston aholisi, Davlatlar YaIM, Oylik harorat)", 2000),
        "mindmap":     ("🗺️ Kontsept xarita",  "Mind map mavzusini kiriting:\n(masalan: Sun'iy intellekt, Ekologiya, Marketing)",       2000),
    }
    title, question, price = service_info.get(service, ("Xizmat", "Kiriting:", 2000))
    context.user_data["hj_price"] = price
    context.user_data["hj_title"] = title

    await query.edit_message_text(
        f"✅ {title} tanlandi.\n💰 Narx: {price:,} so'm\n\nQaysi tilda?",
        reply_markup=HJ_LANG_KEYBOARD
    )
    return HJ_LANG

async def hj_get_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Til tanlovi."""
    query = update.callback_query
    await query.answer()
    lang = query.data.replace("hj_lang_", "")
    context.user_data["hj_lang"] = lang
    service = context.user_data.get("hj_service", "")
    title = context.user_data.get("hj_title", "")
    lang_name = HJ_LANG_NAMES.get(lang, lang)

    questions = {
        "rezyume":     f"✅ Til: {lang_name}\n\nIsm-familiyangizni kiriting:",
        "motivatsion": f"✅ Til: {lang_name}\n\nIsm-familiyangizni kiriting:",
        "jadval":      f"✅ Til: {lang_name}\n\nJadval mavzusini kiriting:\n_(masalan: O'zbekiston aholisi, Davlatlar YaIM)_",
        "mindmap":     f"✅ Til: {lang_name}\n\nMind map mavzusini kiriting:\n_(masalan: Sun'iy intellekt, Ekologiya)_",
    }
    await query.edit_message_text(
        questions.get(service, f"✅ Til: {lang_name}\n\nMavzuni kiriting:"),
        parse_mode="Markdown"
    )
    return HJ_INPUT1

async def hj_get_input1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Birinchi kirish (ism yoki mavzu)."""
    text = update.message.text.strip()
    context.user_data["hj_input1"] = text
    service = context.user_data.get("hj_service", "")

    if service in ("rezyume", "motivatsion"):
        # Ikkinchi kirish kerak
        q2 = {
            "rezyume":     "Kasbingizni kiriting:\n_(masalan: Dasturchi, Iqtisodchi, Muhandis)_",
            "motivatsion": "Maqsadingizni kiriting:\n_(masalan: MIT universitetiga, Google kompaniyasiga, Davlat stipendiyasiga)_",
        }
        await update.message.reply_text(q2[service], parse_mode="Markdown")
        return HJ_INPUT2
    else:
        # Jadval va mindmap uchun to'g'ridan-to'g'ri yaratish
        return await _hj_generate(update, context, text, "", "")

async def hj_get_input2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ikkinchi kirish (kasb yoki maqsad)."""
    text = update.message.text.strip()
    context.user_data["hj_input2"] = text
    service = context.user_data.get("hj_service", "")

    if service == "rezyume":
        await update.message.reply_text(
            "Qo'shimcha ma'lumot kiriting:\n"
            "_(tajriba, ko'nikmalar, ta'lim — ixtiyoriy, '-' yozing o'tkazib yuborish uchun)_",
            parse_mode="Markdown"
        )
        return HJ_INPUT3
    else:
        # Motivatsion xat uchun sabab
        await update.message.reply_text(
            "Nima uchun shu joyni tanlayotganingizni qisqacha yozing:\n"
            "_(ixtiyoriy, '-' yozing o'tkazib yuborish uchun)_",
            parse_mode="Markdown"
        )
        return HJ_INPUT3

async def hj_get_input3(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Uchinchi kirish (qo'shimcha ma'lumot)."""
    text = update.message.text.strip()
    if text == "-":
        text = ""
    context.user_data["hj_input3"] = text
    input1 = context.user_data.get("hj_input1", "")
    input2 = context.user_data.get("hj_input2", "")
    return await _hj_generate(update, context, input1, input2, text)

async def _hj_generate(update: Update, context: ContextTypes.DEFAULT_TYPE,
                       input1: str, input2: str, input3: str) -> int:
    """Hujjatni yaratadi va yuboradi."""
    service = context.user_data.get("hj_service", "")
    lang = context.user_data.get("hj_lang", "uz")
    price = context.user_data.get("hj_price", 2000)
    title = context.user_data.get("hj_title", "Hujjat")
    user = update.effective_user
    lang_name = HJ_LANG_NAMES.get(lang, lang)

    # Balans tekshiruvi
    user_data = await asyncio.to_thread(db.get_user, user.id)
    balance = user_data['balance'] if user_data else 0
    if balance < price:
        await update.message.reply_text(
            f"⚠️ Balansingiz yetarli emas!\n"
            f"💰 Kerakli: {price:,} so'm | Mavjud: {balance:,} so'm\n\n"
            f"Balansni to'ldirish uchun \"Balans & Referral\" bo'limiga o'ting.",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"⏳ *{esc_md(title)}* yaratilmoqda...\n🌍 Til: {lang_name}\n\nBir daqiqa kuting...",
        parse_mode="Markdown"
    )
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_document")
    try:
        import time
        t0 = time.time()
        if service == "rezyume":
            doc = await generate_cv(input1, input2, lang, input3)
            filename = f"rezyume_{input1[:20].replace(' ','_')}.pdf"
            ext = "pdf"
            caption = f"📄 Rezyume / CV\n{input1} — {input2}\n🌍 {lang_name} | PDF"
        elif service == "motivatsion":
            doc = await generate_motivation(input1, input2, lang, input3)
            filename = f"motivatsion_{input1[:20].replace(' ','_')}.docx"
            ext = "docx"
            caption = f"📜 Motivatsion xat\n{input1} → {input2}\n🌍 {lang_name} | DOCX"
        elif service == "jadval":
            doc = await generate_table(input1, lang)
            filename = f"jadval_{input1[:20].replace(' ','_')}.xlsx"
            ext = "xlsx"
            caption = f"📊 Jadval & Diagramma\n{input1}\n🌍 {lang_name} | Excel"
        elif service == "mindmap":
            doc = await generate_mindmap(input1, lang)
            filename = f"mindmap_{input1[:20].replace(' ','_')}.png"
            ext = "png"
            caption = f"🗺️ Kontsept xarita\n{input1}\n🌍 {lang_name} | PNG"
        else:
            await update.message.reply_text("❌ Noma'lum xizmat.", reply_markup=get_main_menu_keyboard())
            return ConversationHandler.END

        elapsed = time.time() - t0

        # Balansdan yechish
        await asyncio.to_thread(db.deduct_balance, user.id, price)
        await asyncio.to_thread(db.log_generation, user.id, service, input1, price)

        doc.seek(0)
        if ext == "png":
            await context.bot.send_photo(
                chat_id=user.id,
                photo=doc,
                caption=caption + f"\n\n@slidego | t.me/slidego"
            )
        else:
            await context.bot.send_document(
                chat_id=user.id,
                document=doc,
                filename=filename,
                caption=caption + f"\n\n@slidego | t.me/slidego"
            )

        # Arxiv
        doc.seek(0)
        archive_doc = BytesIO(doc.read())
        archive_doc.seek(0)
        await archive_send_document(
            bot=context.bot,
            user=user,
            service_name=title,
            topic=input1,
            language=lang_name,
            page_count=1,
            price=price,
            document_bytes=archive_doc,
            filename=filename,
        )

        await update.message.reply_text(
            f"🎉 Tayyor! ({elapsed:.1f} soniya)\n💰 Balansingizdan {price:,} so'm yechildi.",
            reply_markup=get_main_menu_keyboard()
        )
    except Exception as e:
        import traceback
        logger.error(f"Hujjat yaratishda xatolik: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        await update.message.reply_text(
            f"❌ Xatolik yuz berdi.\n"
            f"`{type(e).__name__}: {str(e)[:200]}`\n\n"
            f"Iltimos, qayta urinib ko'ring. Balans yechilmadi.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    return ConversationHandler.END
# ═══════════════════════════════════════════════════════════════════════════
# ANNOTATSIYA HANDLER
# ═══════════════════════════════════════════════════════════════════════════

AN_TYPE_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("📚 Ilmiy maqola",  callback_data="an_type_ilmiy"),
     InlineKeyboardButton("📄 Kurs ishi",     callback_data="an_type_kurs")],
    [InlineKeyboardButton("📖 Kitob",          callback_data="an_type_kitob"),
     InlineKeyboardButton("🎓 Diplom ishi",   callback_data="an_type_diplom")],
    [InlineKeyboardButton("📋 Referat",        callback_data="an_type_referat")],
])

async def an_get_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Annotatsiya — til tanlash callback."""
    query = update.callback_query
    await query.answer()
    lang = query.data.replace("an_lang_", "")
    context.user_data["an_lang"] = lang
    lang_name = AN_LANG_LABELS.get(lang, lang)
    await query.edit_message_text(
        f"📋 *Annotatsiya yaratish*\n"
        f"🌍 Til: {lang_name}\n\n"
        f"Asar turini tanlang:",
        reply_markup=AN_TYPE_KEYBOARD,
        parse_mode="Markdown"
    )
    return AN_TYPE

async def an_get_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Annotatsiya — tur tanlash callback."""
    query = update.callback_query
    await query.answer()
    doc_type = query.data.replace("an_type_", "")
    context.user_data["an_type"] = doc_type
    type_labels = {
        "ilmiy": "Ilmiy maqola", "kurs": "Kurs ishi",
        "kitob": "Kitob", "diplom": "Diplom ishi", "referat": "Referat"
    }
    type_name = type_labels.get(doc_type, doc_type)
    lang = context.user_data.get("an_lang", "uz")
    lang_name = AN_LANG_LABELS.get(lang, lang)
    await query.edit_message_text(
        f"📋 *Annotatsiya yaratish*\n"
        f"🌍 Til: {lang_name} | 📄 Tur: {type_name}\n\n"
        f"Asar sarlavhasini yozing:",
        parse_mode="Markdown"
    )
    return AN_TITLE

async def an_get_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Annotatsiya — sarlavha kiritish."""
    title = update.message.text.strip()
    context.user_data["an_title"] = title
    lang = context.user_data.get("an_lang", "uz")
    lang_name = AN_LANG_LABELS.get(lang, lang)
    type_labels = {
        "ilmiy": "Ilmiy maqola", "kurs": "Kurs ishi",
        "kitob": "Kitob", "diplom": "Diplom ishi", "referat": "Referat"
    }
    doc_type = context.user_data.get("an_type", "kurs")
    type_name = type_labels.get(doc_type, doc_type)
    await update.message.reply_text(
        f"📋 *Annotatsiya yaratish*\n"
        f"🌍 Til: {lang_name} | 📄 Tur: {type_name}\n"
        f"📌 Sarlavha: {esc_md(title)}\n\n"
        f"Muallif ismini yozing (ixtiyoriy, o'tkazib yuborish uchun — yozing):",
        parse_mode="Markdown"
    )
    return AN_AUTHOR

async def an_get_author(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Annotatsiya — muallif va generatsiya."""
    user = update.effective_user
    author_text = update.message.text.strip()
    author = "" if author_text.lower() in ["-", ".", "o'tkazib yuborish", "skip", "нет", "no"] else author_text

    lang = context.user_data.get("an_lang", "uz")
    doc_type = context.user_data.get("an_type", "kurs")
    title = context.user_data.get("an_title", "")
    lang_name = AN_LANG_LABELS.get(lang, lang)

    # Balans tekshirish
    user_data = await asyncio.to_thread(db.get_user, user.id)
    balance = user_data["balance"] if user_data else 0
    price = ANNOTATSIYA_PRICE

    if balance < price:
        await update.message.reply_text(
            f"❌ *Balans yetarli emas!*\n\n"
            f"💰 Balansingiz: `{balance:,}` so'm\n"
            f"💳 Kerakli summa: `{price:,}` so'm\n\n"
            f"Balansni to'ldiring:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💳 Balans to'ldirish", callback_data="topup_start")
            ]]),
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    type_labels = {
        "ilmiy": "Ilmiy maqola", "kurs": "Kurs ishi",
        "kitob": "Kitob", "diplom": "Diplom ishi", "referat": "Referat"
    }
    type_name = type_labels.get(doc_type, doc_type)

    await update.message.reply_text(
        f"⏳ *{esc_md(title)}* asari uchun annotatsiya yaratilmoqda...\n"
        f"🌍 Til: {lang_name} | 📄 Tur: {type_name}\n\n"
        f"Bir daqiqa kuting...",
        parse_mode="Markdown"
    )
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_document")
    try:
        doc_bytes = await generate_annotation(title, doc_type, lang, author)

        # Balans yechish
        await asyncio.to_thread(db.deduct_balance, user.id, price)

        # Foydalanuvchiga yuborish
        filename = f"annotatsiya_{title[:20].replace(' ', '_')}.docx"
        await update.message.reply_document(
            document=doc_bytes,
            filename=filename,
            caption=(
                f"✅ *Annotatsiya tayyor!*\n\n"
                f"📌 {esc_md(title)}\n"
                f"📄 Tur: {type_name}\n"
                f"🌍 Til: {lang_name}\n"
                f"💰 Yechildi: {price:,} so'm\n\n"
                f"@slidego | t.me/slidego"
            ),
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )

        # Arxivga yuborish
        try:
            from io import BytesIO
            if hasattr(doc_bytes, 'getvalue'):
                archive_doc = BytesIO(doc_bytes.getvalue())
            else:
                doc_bytes.seek(0)
                archive_doc = BytesIO(doc_bytes.read())
            archive_doc.seek(0)
            await context.bot.send_document(
                chat_id=ARCHIVE_CHANNEL,
                document=archive_doc,
                filename=filename,
                caption=(
                    f"📋 Annotatsiya\n"
                    f"👤 {user.full_name} (@{user.username or 'nouser'}) | ID: {user.id}\n"
                    f"📌 {esc_md(title)} | {type_name} | {lang_name}"
                )
            )
        except Exception as e:
            logger.warning(f"Annotatsiya arxiv xatolik: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Annotatsiya xatolik: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Annotatsiya yaratishda xatolik yuz berdi.\n{str(e)[:100]}\n\n"
            f"Iltimos, qayta urinib ko'ring. Balans yechilmadi.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    return ConversationHandler.END

# ═══════════════════════════════════════════════════════════════════════════
# TAQRIZ HANDLERR
# ═══════════════════════════════════════════════════════════════════════════

TQ_TYPE_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("📄 Kurs ishi",     callback_data="tq_type_kurs"),
     InlineKeyboardButton("🎓 Diplom ishi",   callback_data="tq_type_diplom")],
    [InlineKeyboardButton("📚 Ilmiy maqola",  callback_data="tq_type_maqola"),
     InlineKeyboardButton("📖 Kitob",          callback_data="tq_type_kitob")],
    [InlineKeyboardButton("📋 Referat",        callback_data="tq_type_referat")],
])

async def tq_get_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Taqriz — til tanlash callback."""
    query = update.callback_query
    await query.answer()
    lang = query.data.replace("tq_lang_", "")
    context.user_data["tq_lang"] = lang
    lang_name = TQ_LANG_LABELS.get(lang, lang)
    await query.edit_message_text(
        f"📝 *Taqriz yaratish*\n"
        f"🌍 Til: {lang_name}\n\n"
        f"Asar turini tanlang:",
        reply_markup=TQ_TYPE_KEYBOARD,
        parse_mode="Markdown"
    )
    return TQ_TYPE

async def tq_get_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Taqriz — tur tanlash callback."""
    query = update.callback_query
    await query.answer()
    doc_type = query.data.replace("tq_type_", "")
    context.user_data["tq_type"] = doc_type
    type_name = TAQRIZ_TYPES.get(doc_type, doc_type)
    lang = context.user_data.get("tq_lang", "uz")
    lang_name = TQ_LANG_LABELS.get(lang, lang)
    await query.edit_message_text(
        f"📝 *Taqriz yaratish*\n"
        f"🌍 Til: {lang_name} | 📄 Tur: {type_name}\n\n"
        f"Asar sarlavhasini yozing:",
        parse_mode="Markdown"
    )
    return TQ_TITLE

async def tq_get_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Taqriz — sarlavha kiritish."""
    title = update.message.text.strip()
    context.user_data["tq_title"] = title
    lang = context.user_data.get("tq_lang", "uz")
    lang_name = TQ_LANG_LABELS.get(lang, lang)
    doc_type = context.user_data.get("tq_type", "kurs")
    type_name = TAQRIZ_TYPES.get(doc_type, doc_type)
    await update.message.reply_text(
        f"📝 *Taqriz yaratish*\n"
        f"🌍 Til: {lang_name} | 📄 Tur: {type_name}\n"
        f"📌 Sarlavha: {esc_md(title)}\n\n"
        f"Asar muallifining ismini yozing:",
        parse_mode="Markdown"
    )
    return TQ_AUTHOR

async def tq_get_author(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Taqriz — muallif ismi."""
    author = update.message.text.strip()
    context.user_data["tq_author"] = author
    lang = context.user_data.get("tq_lang", "uz")
    lang_name = TQ_LANG_LABELS.get(lang, lang)
    await update.message.reply_text(
        f"📝 *Taqriz yaratish*\n"
        f"🌍 Til: {lang_name}\n"
        f"✍️ Muallif: {esc_md(author)}\n\n"
        f"Taqrizchi ismini yozing (ixtiyoriy, o'tkazib yuborish uchun — yozing):",
        parse_mode="Markdown"
    )
    return TQ_REVIEWER

async def tq_get_reviewer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Taqriz — taqrizchi ismi."""
    reviewer_text = update.message.text.strip()
    reviewer = "" if reviewer_text.lower() in ["-", ".", "o'tkazib yuborish", "skip", "нет", "no"] else reviewer_text
    context.user_data["tq_reviewer"] = reviewer
    lang = context.user_data.get("tq_lang", "uz")
    lang_name = TQ_LANG_LABELS.get(lang, lang)
    await update.message.reply_text(
        f"📝 *Taqriz yaratish*\n"
        f"🌍 Til: {lang_name}\n\n"
        f"Asar haqida qisqa ma'lumot yozing (ixtiyoriy, o'tkazib yuborish uchun — yozing):\n"
        f"_(masalan: asosiy mavzu, qaysi fan bo'yicha)_",
        parse_mode="Markdown"
    )
    return TQ_SUMMARY

async def tq_get_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Taqriz — qisqa mazmun va generatsiya."""
    user = update.effective_user
    summary_text = update.message.text.strip()
    summary = "" if summary_text.lower() in ["-", ".", "o'tkazib yuborish", "skip", "нет", "no"] else summary_text

    lang = context.user_data.get("tq_lang", "uz")
    doc_type = context.user_data.get("tq_type", "kurs")
    title = context.user_data.get("tq_title", "")
    author = context.user_data.get("tq_author", "")
    reviewer = context.user_data.get("tq_reviewer", "")
    lang_name = TQ_LANG_LABELS.get(lang, lang)
    type_name = TAQRIZ_TYPES.get(doc_type, doc_type)

    # Balans tekshirish
    user_data = await asyncio.to_thread(db.get_user, user.id)
    balance = user_data["balance"] if user_data else 0
    price = TAQRIZ_PRICE

    if balance < price:
        await update.message.reply_text(
            f"❌ *Balans yetarli emas!*\n\n"
            f"💰 Balansingiz: `{balance:,}` so'm\n"
            f"💳 Kerakli summa: `{price:,}` so'm\n\n"
            f"Balansni to'ldiring:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💳 Balans to'ldirish", callback_data="topup_start")
            ]]),
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"⏳ *{esc_md(title)}* asari uchun taqriz yaratilmoqda...\n"
        f"🌍 Til: {lang_name} | 📄 Tur: {type_name}\n\n"
        f"Bir daqiqa kuting...",
        parse_mode="Markdown"
    )
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_document")
    try:
        doc_bytes = await generate_taqriz(title, doc_type, author, reviewer, lang, summary)

        # Balans yechish
        await asyncio.to_thread(db.deduct_balance, user.id, price)

        # Foydalanuvchiga yuborish
        filename = f"taqriz_{title[:20].replace(' ', '_')}.docx"
        await update.message.reply_document(
            document=doc_bytes,
            filename=filename,
            caption=(
                f"✅ *Taqriz tayyor!*\n\n"
                f"📌 {esc_md(title)}\n"
                f"✍️ Muallif: {esc_md(author)}\n"
                f"📄 Tur: {type_name}\n"
                f"🌍 Til: {lang_name}\n"
                f"💰 Yechildi: {price:,} so'm\n\n"
                f"@slidego | t.me/slidego"
            ),
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )

        # Arxivga yuborish
        try:
            from io import BytesIO
            if hasattr(doc_bytes, 'getvalue'):
                archive_doc = BytesIO(doc_bytes.getvalue())
            else:
                doc_bytes.seek(0)
                archive_doc = BytesIO(doc_bytes.read())
            archive_doc.seek(0)
            await context.bot.send_document(
                chat_id=ARCHIVE_CHANNEL,
                document=archive_doc,
                filename=filename,
                caption=(
                    f"📝 Taqriz\n"
                    f"👤 {user.full_name} (@{user.username or 'nouser'}) | ID: {user.id}\n"
                    f"📌 {esc_md(title)} | {esc_md(author)} | {type_name} | {lang_name}"
                )
            )
        except Exception as e:
            logger.warning(f"Taqriz arxiv xatolik: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Taqriz xatolik: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Taqriz yaratishda xatolik yuz berdi.\n{str(e)[:100]}\n\n"
            f"Iltimos, qayta urinib ko'ring. Balans yechilmadi.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    return ConversationHandler.END

# ═══════════════════════════════════════════════════════════════════════════
# ARXIVLASH HANDLERR
# ═══════════════════════════════════════════════════════════════════════════
async def arx_receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Arxivlash — foydalanuvchi fayl yuboradi."""
    user = update.effective_user
    # Faqat arxivlash rejimida ishlaydi
    if context.user_data.get("mode") != "arxivlash":
        return ARX_RECEIVE

    arxiv_files = context.user_data.setdefault("arxiv_files", [])

    # Maksimal fayl soni tekshiruvi
    if len(arxiv_files) >= 20:
        await update.message.reply_text(
            "⚠️ Maksimal *20 ta fayl* yuborishingiz mumkin.\n"
            "Arxivlash uchun *Arxivlash* tugmasini bosing.",
            parse_mode="Markdown"
        )
        return ARX_RECEIVE

    # Fayl turini aniqlash
    msg = update.message
    file_obj = None
    file_name = None

    if msg.document:
        file_obj = msg.document
        file_name = msg.document.file_name or f"fayl_{len(arxiv_files)+1}"
    elif msg.photo:
        file_obj = msg.photo[-1]  # eng katta o'lcham
        file_name = f"rasm_{len(arxiv_files)+1}.jpg"
    elif msg.video:
        file_obj = msg.video
        file_name = msg.video.file_name or f"video_{len(arxiv_files)+1}.mp4"
    elif msg.audio:
        file_obj = msg.audio
        file_name = msg.audio.file_name or f"audio_{len(arxiv_files)+1}.mp3"
    elif msg.voice:
        file_obj = msg.voice
        file_name = f"ovoz_{len(arxiv_files)+1}.ogg"
    else:
        await update.message.reply_text(
            "⚠️ Faqat fayl, rasm, video yoki audio yuboring.\n"
            "Yoki *Arxivlash* tugmasini bosib arxivni yarating.",
            parse_mode="Markdown"
        )
        return ARX_RECEIVE

    # Fayl hajmini tekshirish (20 MB)
    file_size = getattr(file_obj, 'file_size', 0) or 0
    if file_size > 20 * 1024 * 1024:
        await update.message.reply_text(
            f"⚠️ *{esc_md(file_name)}* fayli juda katta ({file_size // (1024*1024)} MB).\n"
            f"Maksimal fayl hajmi: *20 MB*",
            parse_mode="Markdown"
        )
        return ARX_RECEIVE

    # file_id ni saqlash
    arxiv_files.append({"file_id": file_obj.file_id, "name": file_name})
    count = len(arxiv_files)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🗜️ Arxivlash ({count} ta fayl)", callback_data="arx_done")],
        [InlineKeyboardButton("❌ Bekor qilish", callback_data="arx_cancel")],
    ])
    await update.message.reply_text(
        f"✅ *{esc_md(file_name)}* qabul qilindi ({count}/20)\n\n"
        f"Yana fayl yuborishingiz yoki *Arxivlash* tugmasini bosishingiz mumkin.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return ARX_RECEIVE


async def arx_done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Arxivlash — 'Arxivlash' tugmasi bosildi, zip yaratish va to'lov."""
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    arxiv_files = context.user_data.get("arxiv_files", [])
    if not arxiv_files:
        await query.edit_message_text(
            "⚠️ Hech qanday fayl yuklanmadi.\nIltimos, avval fayllarni yuboring.",
            parse_mode="Markdown"
        )
        return ARX_RECEIVE

    # Balans tekshirish
    price = SERVICE_PRICES["arxivlash"]
    user_data = await asyncio.to_thread(db.get_user, user.id)
    balance = user_data["balance"] if user_data else 0
    if balance < price:
        await query.edit_message_text(
            f"❌ *Balans yetarli emas!*\n\n"
            f"💰 Balansingiz: `{balance:,}` so'm\n"
            f"💳 Kerakli summa: `{price:,}` so'm\n\n"
            f"Balansni to'ldiring:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💳 Balans to'ldirish", callback_data="topup_start")
            ]]),
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    await query.edit_message_text(
        f"⏳ *{len(arxiv_files)} ta fayl* yuklanmoqda va arxivlanmoqda...\n\nBir daqiqa kuting.",
        parse_mode="Markdown"
    )
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_document")

    try:
        import zipfile
        zip_buffer = BytesIO()
        # Fayllarni yuklab zip ga qo'shish
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for i, finfo in enumerate(arxiv_files):
                try:
                    tg_file = await context.bot.get_file(finfo["file_id"])
                    file_bytes = await tg_file.download_as_bytearray()
                    # Bir xil nomli fayllar uchun raqam qo'shish
                    fname = finfo["name"]
                    existing_names = [f["name"] for f in arxiv_files[:i]]
                    if fname in existing_names:
                        base, ext = fname.rsplit('.', 1) if '.' in fname else (fname, '')
                        fname = f"{base}_{i+1}.{ext}" if ext else f"{base}_{i+1}"
                    zf.writestr(fname, bytes(file_bytes))
                except Exception as e:
                    logger.warning(f"Fayl yuklab olishda xatolik {finfo['name']}: {e}")

        zip_buffer.seek(0)
        zip_size_kb = len(zip_buffer.getvalue()) // 1024

        # Balans yechish
        await asyncio.to_thread(db.deduct_balance, user.id, price)

        # Arxivni foydalanuvchiga yuborish
        zip_name = f"arxiv_{user.id}_{len(arxiv_files)}fayl.zip"
        zip_buffer.seek(0)
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=zip_buffer,
            filename=zip_name,
            caption=(
                f"✅ *Arxiv tayyor!*\n\n"
                f"📦 Fayllar soni: *{len(arxiv_files)} ta*\n"
                f"📁 Arxiv hajmi: *{zip_size_kb:,} KB*\n"
                f"💰 Yechildi: *{price:,} so'm*\n\n"
                f"@slidego | t.me/slidego"
            ),
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
        logger.info(f"Arxivlash: {user.id} | {len(arxiv_files)} fayl | {price} so'm")

    except Exception as e:
        logger.error(f"Arxivlash xatolik: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                f"❌ Arxiv yaratishda xatolik yuz berdi.\n"
                f"`{str(e)[:100]}`\n\n"
                f"Balans yechilmadi. Qayta urinib ko'ring."
            ),
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    return ConversationHandler.END


async def arx_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Arxivlash — bekor qilish."""
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text(
        "❌ Arxivlash bekor qilindi.",
        parse_mode="Markdown"
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Asosiy menyu:",
        reply_markup=get_main_menu_keyboard()
    )
    return ConversationHandler.END
# ═══════════════════════════════════════════════════════════════════════════
# PDF KONVERTATSIYA HANDLER
# ═══════════════════════════════════════════════════════════════════════════
# Qo'llab-quvvatlanadigan kengaytmalar
PDF_SUPPORTED_DOCS = {".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".odt", ".ods", ".odp", ".txt", ".html", ".htm"}
PDF_SUPPORTED_IMGS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif"}
PDF_ALL_SUPPORTED = PDF_SUPPORTED_DOCS | PDF_SUPPORTED_IMGS


async def pdf_receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """PDF Konvertatsiya — foydalanuvchi fayl yuboradi, bot PDF ga aylantiradi."""
    user = update.effective_user
    if context.user_data.get("mode") != "pdf_convert":
        return PDF_RECEIVE

    msg = update.message
    file_obj = None
    file_name = None

    if msg.document:
        file_obj = msg.document
        file_name = msg.document.file_name or "fayl"
    elif msg.photo:
        file_obj = msg.photo[-1]
        file_name = "rasm.jpg"
    else:
        await update.message.reply_text(
            "⚠️ Faqat fayl yoki rasm yuboring.\n"
            "Qo'llab-quvvatlanadigan: DOCX, XLSX, PPTX, JPG, PNG va boshqalar.",
            parse_mode="Markdown"
        )
        return PDF_RECEIVE

    # Kengaytmani tekshirish
    ext = os.path.splitext(file_name)[1].lower()
    if ext not in PDF_ALL_SUPPORTED and not msg.photo:
        await update.message.reply_text(
            f"⚠️ *{esc_md(file_name)}* formati qo'llab-quvvatlanmaydi.\n\n"
            f"Qo'llab-quvvatlanadigan formatlar:\n"
            f"DOCX, DOC, XLSX, XLS, PPTX, PPT, JPG, PNG, BMP, WEBP",
            parse_mode="Markdown"
        )
        return PDF_RECEIVE

    # Fayl hajmini tekshirish
    file_size = getattr(file_obj, 'file_size', 0) or 0
    if file_size > 20 * 1024 * 1024:
        await update.message.reply_text(
            f"⚠️ Fayl juda katta ({file_size // (1024*1024)} MB). Maksimal: *20 MB*",
            parse_mode="Markdown"
        )
        return PDF_RECEIVE

    # Balans tekshirish
    price = SERVICE_PRICES["pdf_convert"]
    user_data = await asyncio.to_thread(db.get_user, user.id)
    balance = user_data["balance"] if user_data else 0
    if balance < price:
        await update.message.reply_text(
            f"❌ *Balans yetarli emas!*\n\n"
            f"💰 Balansingiz: `{balance:,}` so'm\n"
            f"💳 Kerakli summa: `{price:,}` so'm\n\n"
            f"Balansni to'ldiring:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💳 Balans to'ldirish", callback_data="topup_start")
            ]]),
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    # Jarayon boshlanmoqda
    await update.message.reply_text(
        f"⏳ *{esc_md(file_name)}* PDF ga aylantirilmoqda...\nBir daqiqa kuting.",
        parse_mode="Markdown"
    )
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_document")

    try:
        import subprocess, tempfile, shutil

        # Faylni Telegram dan yuklab olish
        tg_file = await context.bot.get_file(file_obj.file_id)
        file_bytes = await tg_file.download_as_bytearray()

        # Vaqtinchalik papka
        tmp_dir = tempfile.mkdtemp(prefix="pdf_conv_")
        try:
            input_path = os.path.join(tmp_dir, file_name)
            with open(input_path, 'wb') as f:
                f.write(file_bytes)

            pdf_name = os.path.splitext(file_name)[0] + ".pdf"
            pdf_path = os.path.join(tmp_dir, pdf_name)

            if msg.photo or ext in PDF_SUPPORTED_IMGS:
                # Rasm → PDF (Pillow)
                from PIL import Image
                img = Image.open(input_path)
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                img.save(pdf_path, 'PDF', resolution=150)
            else:
                # Office/Text → PDF (LibreOffice)
                result = await asyncio.to_thread(
                    subprocess.run,
                    ['libreoffice', '--headless', '--convert-to', 'pdf',
                     '--outdir', tmp_dir, input_path],
                    capture_output=True, text=True, timeout=60
                )
                if result.returncode != 0 or not os.path.exists(pdf_path):
                    raise Exception(f"LibreOffice xatolik: {result.stderr[:200]}")

            # PDF ni o'qish
            with open(pdf_path, 'rb') as f:
                pdf_bytes = BytesIO(f.read())

            pdf_size_kb = os.path.getsize(pdf_path) // 1024

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        # Balans yechish
        await asyncio.to_thread(db.deduct_balance, user.id, price)

        # PDF ni foydalanuvchiga yuborish
        pdf_bytes.seek(0)
        await update.message.reply_document(
            document=pdf_bytes,
            filename=pdf_name,
            caption=(
                f"✅ *PDF tayyor!*\n\n"
                f"📄 {esc_md(file_name)} → {esc_md(pdf_name)}\n"
                f"📁 Hajmi: *{pdf_size_kb:,} KB*\n"
                f"💰 Yechildi: *{price:,} so'm*\n\n"
                f"@slidego | t.me/slidego"
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Yana konvertatsiya", callback_data="pdf_again")],
                [InlineKeyboardButton("🏠 Asosiy menyu", callback_data="pdf_cancel")],
            ]),
            parse_mode="Markdown"
        )
        logger.info(f"PDF konvert: {user.id} | {file_name} -> {pdf_name} | {price} so'm")

    except Exception as e:
        logger.error(f"PDF konvertatsiya xatolik: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ PDF yaratishda xatolik yuz berdi.\n"
            f"`{esc_md(str(e)[:150])}`\n\n"
            f"Balans yechilmadi. Qayta urinib ko'ring.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    return ConversationHandler.END


async def pdf_again_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """PDF Konvertatsiya — yana konvertatsiya qilish."""
    query = update.callback_query
    await query.answer()
    context.user_data["mode"] = "pdf_convert"
    price = SERVICE_PRICES["pdf_convert"]
    await query.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            f"📄 *Yana fayl yuboring:*\n\n"
            f"DOCX, XLSX, PPTX, JPG, PNG va boshqalar\n"
            f"💰 Narx: *{price:,} so'm*/fayl"
        ),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Bekor qilish", callback_data="pdf_cancel")],
        ]),
        parse_mode="Markdown"
    )
    return PDF_RECEIVE


async def pdf_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """PDF Konvertatsiya — bekor qilish."""
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Asosiy menyu:",
        reply_markup=get_main_menu_keyboard()
    )
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════════════
# AI YORDAMCHI HANDLERR
# ═══════════════════════════════════════════════════════════════════════════

async def ai_chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """AI yordamchi — savol qabul qilish va javob berish."""
    user = update.effective_user
    text = update.message.text.strip()

    # Asosiy menyu tugmalaridan biri bosilsa — suhbatni tugatish
    main_menu_buttons = [
        "🤖 AI yordamchi 💬", "🎧 Slayd yaratish ✨", "📄 Mustaqil ish ✨",
        "📁 Loyiha ishi ✨", "📊 Infografika ✨", "📰 Maqola ✨",
        "🎓 Kurs ishi / BMI 📝", "📚 Referat ✨", "📜 Tezis ✨",
        "💡 Glossary ✨", "🧩 Krossvord ✨", "🔠 Test tuzish",
        "✍️ Insho / Esse ✨", "📂 Hujjat & Dizayn ✨",
        "📋 Annotatsiya ✨", "📝 Taqriz ✨", "📦 Ziplash/Arxivlash 🗜️", "📄 PDF Konvertatsiya 🔄", "💰 Balans", "🔗 Referral"
    ]
    if text in main_menu_buttons:
        return await handle_main_menu_selection(update, context)

    # Kunlik limit tekshirish
    daily_count = await asyncio.to_thread(get_ai_daily_count, user.id)
    is_free = daily_count < AI_FREE_LIMIT

    if not is_free:
        # Balans tekshirish
        user_data = await asyncio.to_thread(db.get_user, user.id)
        balance = user_data["balance"] if user_data else 0
        if balance < AI_PRICE_PER_MSG:
            await update.message.reply_text(
                f"❌ *Balans yetarli emas!*\n\n"
                f"💰 Balansingiz: `{balance:,}` so'm\n"
                f"💳 Kerakli summa: `{AI_PRICE_PER_MSG:,}` so'm\n\n"
                f"Balansni to'ldiring yoki ertaga bepul savollardan foydalaning:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("💳 Balans to'ldirish", callback_data="topup_start")
                ]]),
                parse_mode="Markdown"
            )
            return AI_CHAT

    # Suhbat tarixini olish
    history = context.user_data.get("ai_history", [])
    history.append({"role": "user", "content": text})

    # Yozmoqda animatsiyasi
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        # GPT dan javob olish
        response = await asyncio.to_thread(get_ai_response_sync, history)

        # Tarixga qo'shish (maksimum 10 ta xabar saqlash)
        history.append({"role": "assistant", "content": response})
        if len(history) > 20:
            history = history[-20:]
        context.user_data["ai_history"] = history

        # Kunlik hisobni oshirish
        new_count = await asyncio.to_thread(increment_ai_daily_count, user.id)

        # Balans yechish (bepul emas bo'lsa)
        if not is_free:
            await asyncio.to_thread(db.deduct_balance, user.id, AI_PRICE_PER_MSG)
            cost_text = f"\n\n💳 Yechildi: {AI_PRICE_PER_MSG:,} so'm"
        else:
            remaining = max(0, AI_FREE_LIMIT - new_count)
            if remaining > 0:
                cost_text = f"\n\n🎁 Qolgan bepul: {remaining} ta"
            else:
                cost_text = f"\n\n⚠️ Bepul savollar tugadi. Keyingi savol: {AI_PRICE_PER_MSG:,} so'm"

        # Javobni yuborish
        # Telegram Markdown limit: 4096 belgi
        full_response = response + cost_text
        if len(full_response) > 4000:
            # Uzun javobni bo'lib yuborish
            await update.message.reply_text(response[:4000], parse_mode="Markdown")
            await update.message.reply_text(response[4000:] + cost_text, parse_mode="Markdown")
        else:
            try:
                await update.message.reply_text(full_response, parse_mode="Markdown")
            except Exception:
                # Markdown xatosi bo'lsa — oddiy matn
                await update.message.reply_text(full_response)

    except Exception as e:
        logger.error(f"AI yordamchi xatolik: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.\n"
            f"Balans yechilmadi."
        )

    return AI_CHAT

def get_ai_response_sync(messages: list) -> str:
    """Sinxron GPT javob olish (asyncio.to_thread uchun)."""
    import asyncio as _asyncio
    loop = _asyncio.new_event_loop()
    try:
        return loop.run_until_complete(get_ai_response(messages))
    finally:
        loop.close()

# ─────────────────────────────────────────────
# Handlerlar — Rezyume / CV (yangi, to'liq)
# ─────────────────────────────────────────────
CV_LANG_NAMES = {"uz": "O'zbek", "en": "Ingliz", "ru": "Rus", "ko": "Kores", "zh": "Xitoy", "de": "Nemis"}

CV_LANG_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🇺🇿 O'zbek", callback_data="cv_lang_uz"),
     InlineKeyboardButton("🇬🇧 Ingliz", callback_data="cv_lang_en")],
    [InlineKeyboardButton("🇷🇺 Rus",    callback_data="cv_lang_ru"),
     InlineKeyboardButton("🇰🇷 Kores",  callback_data="cv_lang_ko")],
    [InlineKeyboardButton("🇨🇳 Xitoy",  callback_data="cv_lang_zh"),
     InlineKeyboardButton("🇩🇪 Nemis",  callback_data="cv_lang_de")],
])

CV_TONE_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("💼 Professional", callback_data="cv_tone_professional"),
     InlineKeyboardButton("✍️ Ijodiy",       callback_data="cv_tone_creative")],
    [InlineKeyboardButton("📝 Qisqa",        callback_data="cv_tone_concise"),
     InlineKeyboardButton("📖 Batafsil",     callback_data="cv_tone_detailed")],
])

CV_LENGTH_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("📄 1 sahifa", callback_data="cv_length_1"),
     InlineKeyboardButton("📄📄 2 sahifa", callback_data="cv_length_2")],
])

def _cv_skip_text(lang: str) -> str:
    skips = {
        "uz": "_(o'tkazib yuborish uchun '-' yozing)_",
        "ru": "_(введите '-' чтобы пропустить)_",
        "en": "_(type '-' to skip)_",
        "ko": "_(건너뛰려면 '-' 입력)_",
        "zh": "_(输入'-'跳过)_",
        "de": "_(geben Sie '-' ein, um zu überspringen)_",
    }
    return skips.get(lang, "_(type '-' to skip)_")

async def cv_get_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Til tanlandi."""
    query = update.callback_query
    await query.answer()
    lang = query.data.replace("cv_lang_", "")
    context.user_data["cv_data"] = {"lang": lang}
    lang_name = CV_LANG_NAMES.get(lang, lang)
    await query.edit_message_text(
        f"✅ Til: {lang_name}\n\n"
        f"👤 *1/14 — To'liq ism, familiya, otangizning ismi:*\n"
        f"Misol: Alisher Navoiy Nizomiddinovich",
        parse_mode="Markdown"
    )
    return CV_FULLNAME

async def cv_get_fullname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """To'liq ism."""
    text = update.message.text.strip()
    context.user_data["cv_data"]["fullname"] = text
    lang = context.user_data["cv_data"].get("lang", "uz")
    skip = _cv_skip_text(lang)
    await update.message.reply_text(
        f"✅ Ism: *{text}*\n\n"
        f"📧 *2/14 — Email manzilingiz:*\n"
        f"Misol: alisher@gmail.com\n{skip}",
        parse_mode="Markdown"
    )
    return CV_EMAIL

async def cv_get_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Email."""
    text = update.message.text.strip()
    context.user_data["cv_data"]["email"] = "" if text == "-" else text
    lang = context.user_data["cv_data"].get("lang", "uz")
    skip = _cv_skip_text(lang)
    await update.message.reply_text(
        f"📞 *3/14 — Telefon raqamingiz:*\n"
        f"Misol: +998 90 123 45 67\n{skip}",
        parse_mode="Markdown"
    )
    return CV_PHONE

async def cv_get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Telefon."""
    text = update.message.text.strip()
    context.user_data["cv_data"]["phone"] = "" if text == "-" else text
    lang = context.user_data["cv_data"].get("lang", "uz")
    skip = _cv_skip_text(lang)
    await update.message.reply_text(
        f"📍 *4/14 — Joylashuvingiz (Location):*\n"
        f"Misol: Toshkent, O'zbekiston\n{skip}",
        parse_mode="Markdown"
    )
    return CV_LOCATION

async def cv_get_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Joylashuv."""
    text = update.message.text.strip()
    context.user_data["cv_data"]["location"] = "" if text == "-" else text
    lang = context.user_data["cv_data"].get("lang", "uz")
    skip = _cv_skip_text(lang)
    await update.message.reply_text(
        f"🔗 *5/14 — Havolalaringiz (Links):*\n"
        f"GitHub, LinkedIn, Portfolio va boshqalar\n"
        f"Misol: github.com/username | linkedin.com/in/username\n{skip}",
        parse_mode="Markdown"
    )
    return CV_LINKS

async def cv_get_links(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Havolalar."""
    text = update.message.text.strip()
    context.user_data["cv_data"]["links"] = "" if text == "-" else text
    lang = context.user_data["cv_data"].get("lang", "uz")
    skip = _cv_skip_text(lang)
    await update.message.reply_text(
        f"🖼️ *6/14 — Profil rasmi (ixtiyoriy):*\n"
        f"Rasm yuboring yoki '-' yozing o'tkazib yuborish uchun",
        parse_mode="Markdown"
    )
    return CV_PHOTO

async def cv_get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Profil rasmi."""
    lang = context.user_data["cv_data"].get("lang", "uz")
    skip = _cv_skip_text(lang)
    if update.message.photo:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        import io as _io
        photo_bytes = _io.BytesIO()
        await file.download_to_memory(photo_bytes)
        photo_bytes.seek(0)
        context.user_data["cv_data"]["photo"] = photo_bytes.read()
    elif update.message.text and update.message.text.strip() == "-":
        context.user_data["cv_data"]["photo"] = None
    else:
        context.user_data["cv_data"]["photo"] = None
    await update.message.reply_text(
        f"💼 *7/14 — Lavozimingiz (Professional title):*\n"
        f"Misol: Frontend Developer | Marketing Manager | Data Scientist\n{skip}",
        parse_mode="Markdown"
    )
    return CV_TITLE

async def cv_get_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Lavozim."""
    text = update.message.text.strip()
    context.user_data["cv_data"]["title"] = "" if text == "-" else text
    lang = context.user_data["cv_data"].get("lang", "uz")
    skip = _cv_skip_text(lang)
    await update.message.reply_text(
        f"🗺️ *8/15 — Mintaqa-xudud (Region):*\n"
        f"Ishlash yoki yashash mintaqangizni kiriting\n"
        f"Misol: Toshkent shahri | Samarqand viloyati | Andijon\n{skip}",
        parse_mode="Markdown"
    )
    return CV_REGION

async def cv_get_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Mintaqa-xudud."""
    text = update.message.text.strip()
    context.user_data["cv_data"]["region"] = "" if text == "-" else text
    lang = context.user_data["cv_data"].get("lang", "uz")
    skip = _cv_skip_text(lang)
    await update.message.reply_text(
        f"📝 *9/15 — Professional xulosa (Professional Summary):*\n"
        f"O'zingiz haqida 2-3 jumlada qisqacha yozing\n"
        f"Misol: 5 yillik tajribaga ega frontend developer. React va Vue.js da ixtisoslashganman.\n{skip}",
        parse_mode="Markdown"
    )
    return CV_SUMMARY

async def cv_get_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Professional xulosa."""
    text = update.message.text.strip()
    context.user_data["cv_data"]["summary"] = "" if text == "-" else text
    lang = context.user_data["cv_data"].get("lang", "uz")
    skip = _cv_skip_text(lang)
    await update.message.reply_text(
        f"💼 *10/15 — Ish tajribangiz (Experience):*\n"
        f"Har qatorda bitta lavozim yozing\n"
        f"Misol:\n"
        f"• Frontend Developer | ABC Company | 2022-2024\n"
        f"  - React bilan web ilovalar yaratdim\n"
        f"  - 30% tezlikni oshirdim\n{skip}",
        parse_mode="Markdown"
    )
    return CV_EXPERIENCE

async def cv_get_experience(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Tajriba."""
    text = update.message.text.strip()
    context.user_data["cv_data"]["experience"] = "" if text == "-" else text
    lang = context.user_data["cv_data"].get("lang", "uz")
    skip = _cv_skip_text(lang)
    await update.message.reply_text(
        f"🚀 *11/15 — Loyihalaringiz (Projects):*\n"
        f"Har qatorda bitta loyiha\n"
        f"Misol:\n"
        f"• E-commerce sayt | React + Node.js | 2023\n"
        f"  - 10,000+ foydalanuvchi\n{skip}",
        parse_mode="Markdown"
    )
    return CV_PROJECTS

async def cv_get_projects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Loyihalar."""
    text = update.message.text.strip()
    context.user_data["cv_data"]["projects"] = "" if text == "-" else text
    lang = context.user_data["cv_data"].get("lang", "uz")
    skip = _cv_skip_text(lang)
    await update.message.reply_text(
        f"🎓 *12/15 — Ta'limingiz (Education):*\n"
        f"Misol:\n"
        f"• Toshkent Davlat Texnika Universiteti\n"
        f"  Kompyuter muhandisligi | 2018-2022\n{skip}",
        parse_mode="Markdown"
    )
    return CV_EDUCATION

async def cv_get_education(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ta'lim."""
    text = update.message.text.strip()
    context.user_data["cv_data"]["education"] = "" if text == "-" else text
    lang = context.user_data["cv_data"].get("lang", "uz")
    skip = _cv_skip_text(lang)
    await update.message.reply_text(
        f"🏆 *13/15 — Sertifikatlaringiz (Certifications):*\n"
        f"Misol:\n"
        f"• AWS Certified Developer | Amazon | 2023\n"
        f"• Google Analytics Certificate | 2022\n{skip}",
        parse_mode="Markdown"
    )
    return CV_CERTIFICATIONS

async def cv_get_certifications(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sertifikatlar."""
    text = update.message.text.strip()
    context.user_data["cv_data"]["certifications"] = "" if text == "-" else text
    lang = context.user_data["cv_data"].get("lang", "uz")
    skip = _cv_skip_text(lang)
    await update.message.reply_text(
        f"🛠️ *14/15 — Ko'nikmalaringiz (Skills):*\n"
        f"Vergul bilan ajrating\n"
        f"Misol: Python, React, SQL, Git, Docker, Figma\n{skip}",
        parse_mode="Markdown"
    )
    return CV_SKILLS

async def cv_get_skills(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ko'nikmalar."""
    text = update.message.text.strip()
    context.user_data["cv_data"]["skills"] = "" if text == "-" else text
    await update.message.reply_text(
        "🎨 *15/15 — Uslub variantlari (Style Options):*\n\n"
        "*Ohang (Tone) tanlang:*",
        parse_mode="Markdown",
        reply_markup=CV_TONE_KEYBOARD
    )
    return CV_TONE

async def cv_get_tone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Tone tanlandi."""
    query = update.callback_query
    await query.answer()
    tone = query.data.replace("cv_tone_", "")
    tone_names = {
        "professional": "💼 Professional",
        "creative": "✍️ Ijodiy",
        "concise": "📝 Qisqa",
        "detailed": "📖 Batafsil"
    }
    context.user_data["cv_data"]["tone"] = tone
    await query.edit_message_text(
        f"✅ Ohang: {tone_names.get(tone, tone)}\n\n"
        f"📏 *Uzunlik (Length) tanlang:*",
        parse_mode="Markdown",
        reply_markup=CV_LENGTH_KEYBOARD
    )
    return CV_LENGTH

async def cv_get_length(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Length tanlandi — rezyume yaratish."""
    query = update.callback_query
    await query.answer()
    length = int(query.data.replace("cv_length_", ""))
    context.user_data["cv_data"]["length"] = length
    cv_data = context.user_data.get("cv_data", {})
    user = update.effective_user
    price = 3000
    user_data = await asyncio.to_thread(db.get_user, user.id)
    balance = user_data["balance"] if user_data else 0
    if balance < price:
        await query.edit_message_text(
            f"⚠️ Balansingiz yetarli emas!\n"
            f"💰 Kerakli: {price:,} so'm | Mavjud: {balance:,} so'm\n\n"
            f"Balansni to'ldirish uchun \"Balans & Referral\" bo'limiga o'ting."
        )
        await context.bot.send_message(chat_id=user.id, text="Asosiy menyu:", reply_markup=get_main_menu_keyboard())
        return ConversationHandler.END
    lang = cv_data.get("lang", "uz")
    lang_name = CV_LANG_NAMES.get(lang, lang)
    fullname = cv_data.get("fullname", "")
    await query.edit_message_text(
        f"⏳ *Rezyume yaratilmoqda...*\n"
        f"👤 {fullname}\n"
        f"🌍 Til: {lang_name} | {length} sahifa\n\n"
        f"Bir daqiqa kuting...",
        parse_mode="Markdown"
    )
    await context.bot.send_chat_action(chat_id=user.id, action="upload_document")
    try:
        import time
        t0 = time.time()
        doc = await generate_cv_full(cv_data)
        elapsed = time.time() - t0
        await asyncio.to_thread(db.deduct_balance, user.id, price)
        await asyncio.to_thread(db.log_generation, user.id, "rezyume", fullname, price)
        doc.seek(0)
        filename = f"rezyume_{fullname[:20].replace(' ', '_')}.pdf"
        caption = (
            f"📄 Rezyume / CV\n"
            f"👤 {fullname}\n"
            f"🌍 {lang_name} | {length} sahifa | PDF\n\n"
            f"@slidego | t.me/slidego"
        )
        await context.bot.send_document(
            chat_id=user.id,
            document=doc,
            filename=filename,
            caption=caption
        )
        doc.seek(0)
        archive_doc = BytesIO(doc.read())
        archive_doc.seek(0)
        await archive_send_document(
            bot=context.bot,
            user=user,
            service_name="Rezyume / CV",
            topic=fullname,
            language=lang_name,
            page_count=length,
            price=price,
            document_bytes=archive_doc,
            filename=filename,
        )
        await context.bot.send_message(
            chat_id=user.id,
            text=f"🎉 Tayyor! ({elapsed:.1f} soniya)\n💰 Balansingizdan {price:,} so'm yechildi.",
            reply_markup=get_main_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"CV yaratish xatolik: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id=user.id,
            text=(
                f"❌ Rezyume yaratishda xatolik yuz berdi.\n"
                f"`{type(e).__name__}: {str(e)[:200]}`\n\n"
                f"Iltimos, qayta urinib ko'ring. Balans yechilmadi."
            ),
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Suhbatni bekor qiladi."""
    await update.message.reply_text(
        "Bekor qilindi. Yana yordamim kerakmi?",
        reply_markup=get_main_menu_keyboard()
    )
    return ConversationHandler.END

# ─────────────────────────────────────────────
# Obuna tekshiruv callback
# ─────────────────────────────────────────────

async def check_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi 'A'zo bo'ldim' tugmasini bosganda tekshiradi."""
    query = update.callback_query
    user = update.effective_user
    is_subscribed = await check_subscription(context.bot, user.id, force=True)
    if is_subscribed:
        await query.answer(text="✅ Tabriklaymiz! Kanalga a'zo bo'ldingiz.", show_alert=False)
        # A'zo bo'ldi — start ni qayta ishga tushirish
        try:
            await query.edit_message_text(
                f"✅ Rahmat, {user.first_name}! Kanalga a'zo bo'ldingiz.\n\n"
                f"Endi botdan to'liq foydalanishingiz mumkin!"
            )
        except Exception:
            pass
        # Asosiy menyuni yuborish
        await context.bot.send_message(
            chat_id=user.id,
            text=f"Assalomu alaykum, {user.first_name}! 👋\n\nQuyidagi xizmatlardan birini tanlang:",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await query.answer(
            text="⚠️ Siz hali @slidego kanaliga a'zo bo'lmagansiz! Avval a'zo bo'ling, so'ng qayta tekshiring.",
            show_alert=True
        )

# ─────────────────────────────────────────────
# Balans to'ldirish handlerlari

def _get_topup_state(context, user_id):
    """topup_state ni DB dan oladi (restart bo'lsa ham yo'qolmaydi)."""
    row = db.get_user_topup_state(user_id)
    return row['state'] if row else None

def _set_topup_state(context, user_id, state):
    """topup_state ni DB ga saqlaydi."""
    if state is None:
        db.set_user_topup_state(user_id, None)
    else:
        current_amount = _get_topup_amount(context, user_id)
        db.set_user_topup_state(user_id, state, current_amount)

def _get_topup_amount(context, user_id):
    """topup_amount ni DB dan oladi."""
    row = db.get_user_topup_state(user_id)
    return row['amount'] if row else 0

def _set_topup_amount(context, user_id, amount):
    """topup_amount ni DB ga saqlaydi."""
    current_state = _get_topup_state(context, user_id) or 'amount'
    db.set_user_topup_state(user_id, current_state, amount)

# ConversationHandler dan MUSTAQIL — context.user_data['topup_state'] orqali
# topup_state: None | 'amount' | 'screenshot'
# ─────────────────────────────────────────────
async def topup_handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """TOPUP_AMOUNT state da foydalanuvchi kiritgan raqamni qabul qiladi."""
    text = update.message.text.strip().replace(' ', '').replace(',', '')
    try:
        amount = int(text)
    except ValueError:
        await update.message.reply_text(
            "⚠️ Faqat raqam kiriting!\n"
            "Masalan: `10000`",
            parse_mode="Markdown"
        )
        return TOPUP_AMOUNT
    if amount < MIN_TOPUP:
        await update.message.reply_text(
            f"⚠️ Minimal to'lov miqdori: *{MIN_TOPUP:,} so'm*\n"
            f"Iltimos, kamida `{MIN_TOPUP:,}` so'm kiriting:",
            parse_mode="Markdown"
        )
        return TOPUP_AMOUNT
    # DB ga ham yozish - /chekyubor buyrug'i uchun
    db.set_user_topup_state(update.effective_user.id, 'screenshot', amount)
    _set_topup_amount(context, update.effective_user.id, amount)
    _set_topup_state(context, update.effective_user.id, 'screenshot')
    await update.message.reply_text(
        f"✅ Kerakli summani kartaga o'tkazing.\n\n"
        f"💳 *{amount:,} so'm*\n\n"
        f"Endi chekni /chekyubor buyrug'i orqali chek rasmi yoki PDF ni yuboring.",
        parse_mode="Markdown"
    )
    return TOPUP_SCREENSHOT

async def topup_handle_screenshot_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """TOPUP_SCREENSHOT state da matn kelganda rasm so'raydi."""
    await update.message.reply_text(
        "📸 *Chek rasmini yuboring!*\n\n"
        "Bank ilovasidan to'lov tasdig'i screenshotini yuboring.",
        parse_mode="Markdown"
    )
    return TOPUP_SCREENSHOT

async def topup_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Balans to'ldirish boshlaydi — callback yoki message orqali."""
    msg = (
        f"💳 *Balans to'ldirish*\n\n"
        f"🏦 Karta raqami:\n`{CARD_NUMBER}`\n"
        f"👤 Abramatova Madina\n\n"
        f"⚠️ Minimal to'lov: *{MIN_TOPUP:,} so'm*\n\n"
        f"📝 Qancha so'm to'lamoqchisiz?\n"
        f"Faqat raqam kiriting (masalan: `10000`):"
    )
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        try:
            await query.edit_message_text(msg, parse_mode="Markdown")
        except Exception:
            await query.message.reply_text(msg, parse_mode="Markdown")
    else:
        await update.message.reply_text(msg, parse_mode="Markdown")
    _set_topup_state(context, update.effective_user.id, 'amount')
    _set_topup_amount(context, update.effective_user.id, 0)
    logger.info(f"topup_start: user {update.effective_user.id} topup boshladi")
    return TOPUP_AMOUNT

async def topup_message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Routes text messages based on the user's top-up state.
    Admin mode ham shu yerda tekshiriladi - barcha state larda ishlashi uchun.
    
    Returns:
        int or None: TOPUP_AMOUNT, TOPUP_SCREENSHOT yoki None (topup aktiv emas)
    """
    # Admin mode tekshiruvi - barcha state larda birinchi ishlaydi
    user_id = update.effective_user.id
    if user_id in ADMIN_IDS:
        adm_mode = context.bot_data.get("admin_modes", {}).get(user_id)
        if adm_mode in ("set_balance", "delete_user", "add_balance"):
            await admin_delete_user_message(update, context)
            # ConversationHandler.END - admin conversation dan chiqadi
            return ConversationHandler.END

    # This router now only handles TEXT messages during the top-up flow.
    # Photo messages are handled by the global topup_get_screenshot handler.
    # NOTE: This router is called from TOPIC, NAME_SURNAME, and other states.
    # If topup_state is active, we need to redirect user to topup flow.
    # But we cannot return TOPUP_AMOUNT or TOPUP_SCREENSHOT from those states
    # because those states don't have handlers for them.
    # So we just show a message and return None (let the current state handle it).
    topup_state = _get_topup_state(context, update.effective_user.id)
    if topup_state in ('amount', 'screenshot'):
        # Foydalanuvchi topup jarayonida boshqa state da xabar yubordi
        # Uni topup ga yo'naltiramiz
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("💳 Balans to'ldirish", callback_data="topup_start")
        ]])
        await update.message.reply_text(
            "⚠️ Siz balans to'ldirish jarayonidasiz!\n"
            "Davom etish uchun quyidagi tugmani bosing:",
            reply_markup=kb,
            parse_mode="Markdown"
        )
        return None
    return None

async def _topup_get_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """To'lov miqdorini qabul qiladi."""
    text = update.message.text.strip().replace(' ', '').replace(',', '')
    try:
        amount = int(text)
    except ValueError:
        await update.message.reply_text("⚠️ Iltimos, faqat raqam kiriting (masalan: 10000):")
        return
    if amount < MIN_TOPUP:
        await update.message.reply_text(
            f"⚠️ Minimal to'lov miqdori: *{MIN_TOPUP:,} so'm*\nIltimos, qayta kiriting:",
            parse_mode="Markdown"
        )
        return
    _set_topup_amount(context, update.effective_user.id, amount)
    _set_topup_state(context, update.effective_user.id, 'screenshot')
    await update.message.reply_text(
        f"💳 *To'lov miqdori: {amount:,} so'm*\n\n"
        f"🏦 Karta raqami:\n`{CARD_NUMBER}`\n"
        f"👤 Abramatova Madina\n\n"
        f"✅ Ushbu kartaga *{amount:,} so'm* o'tkazing\n"
        f"📸 So'ng to'lov cheki (screenshot) rasmini shu yerga yuboring:",
        parse_mode="Markdown"
    )
    logger.info(f"_topup_get_amount: user {update.effective_user.id} miqdor={amount}")
    return TOPUP_SCREENSHOT

async def chekyubor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/chekyubor buyrug'i - to'g'ridan-to'g'ri chek rasmi yoki PDF so'raydi."""
    user_id = update.effective_user.id
    # Mavjud summani saqlab, faqat state ni 'screenshot' ga o'tkazamiz
    topup_row = db.get_user_topup_state(user_id)
    existing_amount = topup_row['amount'] if topup_row else 0
    _set_topup_state(context, user_id, 'screenshot')
    _set_topup_amount(context, user_id, existing_amount)
    db.set_user_topup_state(user_id, 'screenshot', existing_amount)
    await update.message.reply_text(
        "💳 *To'lov chekini yuborish*\n\n"
        "Chek rasmini yoki PDF faylini yuboring.\n"
        "_(Bekor qilish uchun /start bosing)_",
        parse_mode="Markdown"
    )
    return TOPUP_SCREENSHOT

async def topup_get_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Screenshot (to'lov cheki) qabul qiladi va adminga yuboradi."""
    user_id = update.effective_user.id

    # DB dan to'g'ridan-to'g'ri state va amount olish
    topup_row = db.get_user_topup_state(user_id)
    topup_state = topup_row['state'] if topup_row else None
    amount = topup_row['amount'] if topup_row else 0

    logger.info(f"topup_get_screenshot: user={user_id}, state={topup_state}, amount={amount}")

       # Faqat 'screenshot' holatida ishlash
    if topup_state != 'screenshot':
        logger.info(f"Photo/Doc from user {user_id} ignored (topup_state='{topup_state}')")
        return
    # Rasm yoki PDF hujjat bo'lishi mumkin
    is_photo = bool(update.message.photo)
    is_document = bool(update.message.document)
    if not is_photo and not is_document:
        await update.message.reply_text("⚠️ Iltimos, to'lov cheki rasmini yoki PDF faylini yuboring:")
        return
    user = update.effective_user
    # file_id va fayl turi aniqlash
    if is_photo:
        file_id = update.message.photo[-1].file_id
        file_type = 'photo'
    else:
        file_id = update.message.document.file_id
        file_type = 'document'
    # DB ga saqlash
    try:
        tx_id = await asyncio.to_thread(db.create_topup_request, user.id, amount, file_id)
        logger.info(f"Topup request yaratildi: tx_id={tx_id}, user={user.id}, amount={amount}, type={file_type}")
    except Exception as e:
        logger.error(f"create_topup_request xatolik: {e}")
        await update.message.reply_text(
            "❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.",
            reply_markup=get_main_menu_keyboard()
        )
        return
    full_name = (user.full_name or '').strip() or 'Nomsiz'
    username_str = f"@{user.username}" if user.username else "username yo'q"

    # Markdown maxsus belgilarni escape qilish
    def esc(text):
        """Markdown v1 uchun maxsus belgilarni escape qiladi."""
        for ch in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
            text = text.replace(ch, f'\\{ch}')
        return text

    safe_name = esc(full_name)
    safe_username = esc(username_str)

    # Admin ga bildirishnoma yuborish
    admin_notified = False
    for admin_id in ADMIN_IDS:
        try:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"admin_approve_{tx_id}"),
                 InlineKeyboardButton("❌ Rad etish",  callback_data=f"admin_reject_{tx_id}")],
                [InlineKeyboardButton("✏️ Boshqa summa", callback_data=f"admin_custom_amount_{tx_id}")]
            ])
            amount_line = f"💰 Miqdor: {amount:,} so'm" if amount > 0 else "💰 Miqdor: (ko'rsatilmagan)"
            caption_text = (
                f"💳 Yangi to'lov so'rovi #{tx_id}\n\n"
                f"👤 {full_name} | {username_str}\n"
                f"🆔 ID: {user.id}\n"
                f"{amount_line}\n\n"
                f"✅ Tasdiqlash | ❌ Rad etish | ✏️ Boshqa summa"
            )
            if file_type == 'photo':
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=file_id,
                    caption=caption_text,
                    reply_markup=kb,
                )
            else:
                await context.bot.send_document(
                    chat_id=admin_id,
                    document=file_id,
                    caption=caption_text,
                    reply_markup=kb,
                )
            admin_notified = True
            logger.info(f"✅ Admin {admin_id} ga to'lov #{tx_id} yuborildi (user={user.id}, {amount} so'm)")
        except Exception as e:
            logger.error(f"❌ Admin {admin_id} ga xabar yuborishda xatolik: {type(e).__name__}: {e}")

    if not admin_notified:
        logger.error(f"❌ Hech bir adminga to'lov #{tx_id} yuborilmadi! ADMIN_IDS={ADMIN_IDS}")

    # State tozalash (ham context, ham DB)
    try:
        _set_topup_state(context, user_id, None)
        _set_topup_amount(context, user_id, 0)
        db.set_user_topup_state(user_id, None)
    except Exception as e:
        logger.warning(f"State tozalashda xatolik: {e}")

    # Foydalanuvchiga javob
    if amount > 0:
        amount_text = f"💰 O'tkazilgan summa: *{amount:,} so'm*\n"
    else:
        amount_text = ""
    await update.message.reply_text(
        f"✅ *Chekingiz qabul qilindi!*\n\n"
        f"{amount_text}"
        f"⏳ Admin tekshirib, balansni *10–30 daqiqa* ichida to'ldiradi.\n"
        f"Balans to'ldirilgach, sizga bildirishnoma yuboriladi.",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def admin_custom_amount_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin 'Boshqa summa' tugmasini bosganida yangi summa so'raydi."""
    query = update.callback_query
    await query.answer()
    if update.effective_user.id not in ADMIN_IDS:
        await query.answer("Ruxsat yo'q!", show_alert=True)
        return
    tx_id_str = query.data.replace("admin_custom_amount_", "")
    tx_id = int(tx_id_str)
    # Admin state ni saqlash
    context.user_data["admin_awaiting_custom_tx_id"] = tx_id
    context.user_data["admin_awaiting_custom_msg_id"] = query.message.message_id
    context.user_data["admin_awaiting_custom_chat_id"] = query.message.chat_id
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=f"✏️ To'lov #{tx_id} uchun yangi summani kiriting (faqat raqam, so'mda):"
    )

async def admin_custom_amount_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin yangi summani kiritganda qayta tasdiqlash/rad etish ko'rsatadi."""
    if update.effective_user.id not in ADMIN_IDS:
        return
    if "admin_awaiting_custom_tx_id" not in context.user_data:
        return
    text = update.message.text.strip().replace(' ', '').replace(',', '')
    try:
        new_amount = int(text)
    except ValueError:
        await update.message.reply_text("⚠️ Iltimos, faqat raqam kiriting (masalan: 15000):")
        return
    if new_amount <= 0:
        await update.message.reply_text("⚠️ Summa 0 dan katta bo'lishi kerak:")
        return
    tx_id = context.user_data.pop("admin_awaiting_custom_tx_id")
    msg_id = context.user_data.pop("admin_awaiting_custom_msg_id", None)
    chat_id = context.user_data.pop("admin_awaiting_custom_chat_id", None)
    # DB da summani yangilash
    await asyncio.to_thread(db.update_topup_amount, tx_id, new_amount)
    # Yangi keyboard bilan xabarni yangilash
    new_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"admin_approve_{tx_id}"),
         InlineKeyboardButton("❌ Rad etish",  callback_data=f"admin_reject_{tx_id}")],
        [InlineKeyboardButton("✏️ Boshqa summa", callback_data=f"admin_custom_amount_{tx_id}")]
    ])
    if msg_id and chat_id:
        try:
            await context.bot.edit_message_caption(
                chat_id=chat_id,
                message_id=msg_id,
                caption=(
                    f"💳 To'lov #{tx_id} — SUMMA YANGILANDI\n\n"
                    f"💰 Yangi summa: {new_amount:,} so'm\n\n"
                    f"✅ Tasdiqlash yoki ❌ Rad etish:"
                ),
                reply_markup=new_kb
            )
        except Exception as e:
            logger.warning(f"Caption yangilashda xatolik: {e}")
    await update.message.reply_text(
        f"✅ Summa {new_amount:,} so'm ga yangilandi. Endi tasdiqlash yoki rad etishingiz mumkin."
    )

async def admin_approve_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin to'lovni tasdiqlaydi."""
    query = update.callback_query
    await query.answer()
    if update.effective_user.id not in ADMIN_IDS:
        await query.answer("Ruxsat yo'q!", show_alert=True)
        return
    tx_id_str = query.data.replace("admin_approve_", "")
    tx_id = int(tx_id_str)
    tx = await asyncio.to_thread(db.approve_topup, tx_id)
    if not tx:
        await query.answer("⚠️ Allaqachon qayta ishlangan.", show_alert=True)
        return
    try:
        await query.edit_message_caption(
            caption=f"✅ TASDIQLANDI — {tx['amount']:,} so'm qo'shildi\n👤 Foydalanuvchi ID: {tx['user_id']}"
        )
    except Exception:
        pass
    try:
        await context.bot.send_message(
            chat_id=tx['user_id'],
            text=f"✅ To'lovingiz tasdiqlandi!\n💰 Balansingizga {tx['amount']:,} so'm qo'shildi."
        )
    except Exception as e:
        logger.error(f"Foydalanuvchiga xabar yuborishda xatolik: {e}")

async def admin_reject_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin to'lovni rad etadi."""
    query = update.callback_query
    await query.answer()
    if update.effective_user.id not in ADMIN_IDS:
        await query.answer("Ruxsat yo'q!", show_alert=True)
        return
    tx_id_str = query.data.replace("admin_reject_", "")
    tx_id = int(tx_id_str)
    tx = await asyncio.to_thread(db.reject_topup, tx_id)
    if not tx:
        await query.answer("⚠️ Allaqachon qayta ishlangan.", show_alert=True)
        return
    try:
        await query.edit_message_caption(
            caption="❌ RAD ETILDI"
        )
    except Exception:
        pass
    try:
        await context.bot.send_message(
            chat_id=tx['user_id'],
            text="❌ To'lovingiz rad etildi. Iltimos, admin bilan bog'laning."
        )
    except Exception as e:
        logger.error(f"Foydalanuvchiga xabar yuborishda xatolik: {e}")

# ─────────────────────────────────────────────
# Admin panel handlerlari
# ─────────────────────────────────────────────

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panelini ko'rsatadi."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Sizda admin huquqi yo'q.")
        return
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Statistika",           callback_data="adm_stats"),
         InlineKeyboardButton("👥 Foydalanuvchilar",    callback_data="adm_users")],
        [InlineKeyboardButton("⏳ Kutayotgan to'lovlar", callback_data="adm_pending"),
         InlineKeyboardButton("💰 Balans qo'shish",     callback_data="adm_add_bal")],
        [InlineKeyboardButton("📢 Xabar yuborish",      callback_data="adm_broadcast")],
        [InlineKeyboardButton("🗑️ Foydalanuvchi o'chirish", callback_data="adm_delete_user")],
    ])
    await update.message.reply_text(
        "🔐 *Admin Panel*\n\nQuyidagi bo'limlardan birini tanlang:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel callback handleri."""
    query = update.callback_query
    await query.answer()
    if update.effective_user.id not in ADMIN_IDS:
        await query.answer("Ruxsat yo'q!", show_alert=True)
        return
    data = query.data

    if data == "adm_stats":
        s = await asyncio.to_thread(db.get_stats)
        by_svc = s['by_service']
        text = (
            f"📊 *Statistika*\n\n"
            f"👥 Jami foydalanuvchilar: *{s['total_users']:,}*\n"
            f"🆕 Bugun yangi: *{s['new_today']:,}*\n"
            f"🔗 Referral orqali: *{s['via_referral']:,}*\n\n"
            f"📄 Jami generatsiyalar: *{s['total_generations']:,}*\n"
            f"📅 Bugun: *{s['generations_today']:,}*\n"
            f"  • Slayd: {by_svc.get('slayd', 0)}\n"
            f"  • Mustaqil ish: {by_svc.get('mustaqil_ish', 0)}\n"
            f"  • Referat: {by_svc.get('referat', 0)}\n"
            f"  • Loyiha ishi: {by_svc.get('loyiha_ishi', 0)}\n\n"
            f"💵 Jami tushum: *{s['total_income']:,} so'm*\n"
            f"📅 Bugungi tushum: *{s['income_today']:,} so'm*\n"
            f"⏳ Kutayotgan to'lovlar: *{s['pending_topups']}*"
        )
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="adm_back")]])
        await query.edit_message_text(text, reply_markup=back_kb, parse_mode="Markdown")

    elif data == "adm_users" or data.startswith("adm_users_p_"):
        try:
            PER_PAGE = 15
            # Sahifa raqamini aniqlash
            if data.startswith("adm_users_p_"):
                parts = data.split("_")
                page = int(parts[-1])
                sort_by = parts[-2] if parts[-2] in ('joined_at', 'balance', 'last_active') else 'joined_at'
            else:
                page = 1
                sort_by = 'joined_at'

            total = await asyncio.to_thread(db.count_users)
            users = await asyncio.to_thread(db.get_users_page, page, PER_PAGE, sort_by)
            total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)

            sort_labels = {'joined_at': '🗓 Yangi', 'balance': '💰 Balans', 'last_active': '⏰ Faol'}
            sort_label = sort_labels.get(sort_by, '🗓 Yangi')

            lines = []
            start_num = (page - 1) * PER_PAGE + 1
            for i, u in enumerate(users, start=start_num):
                name = esc_md(u['full_name'] or u['username'] or str(u['user_id']))
                uid = u['user_id']
                bal = u['balance']
                lines.append(f"`{i}.` {name}\n    🆔 `{uid}` | 💰 `{bal:,}` so'm")

            if lines:
                header = (
                    f"👥 *Foydalanuvchilar* ({total} ta) | {sort_label}\n"
                    f"📄 Sahifa {page}/{total_pages}\n"
                    f"──────────────────────────────\n"
                )
                text = header + "\n".join(lines)
                if len(text) > 4000:
                    text = text[:4000] + "\n..."
            else:
                text = "Foydalanuvchilar yo'q."

            # Navigatsiya tugmalari
            nav_buttons = []
            if page > 1:
                nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"adm_users_p_{sort_by}_{page-1}"))
            nav_buttons.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="adm_noop"))
            if page < total_pages:
                nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"adm_users_p_{sort_by}_{page+1}"))

            # Saralash tugmalari
            sort_buttons = [
                InlineKeyboardButton("🗓 Yangi",  callback_data=f"adm_users_p_joined_at_1"),
                InlineKeyboardButton("💰 Balans", callback_data=f"adm_users_p_balance_1"),
                InlineKeyboardButton("⏰ Faol",   callback_data=f"adm_users_p_last_active_1"),
            ]

            kb = InlineKeyboardMarkup([
                nav_buttons,
                sort_buttons,
                [InlineKeyboardButton("⬅️ Orqaga", callback_data="adm_back")],
            ])
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"adm_users xatolik: {e}")
            back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="adm_back")]])
            await query.edit_message_text(f"❌ Xatolik: {str(e)[:200]}", reply_markup=back_kb)

    elif data == "adm_pending":
        pending = await asyncio.to_thread(db.get_pending_topups)
        if not pending:
            back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="adm_back")]])
            await query.edit_message_text("✅ Kutayotgan to'lovlar yo'q.", reply_markup=back_kb)
            return
        for tx in pending[:5]:
            name = tx.get('full_name') or tx.get('username') or str(tx['user_id'])
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"admin_approve_{tx['id']}"),
                 InlineKeyboardButton("❌ Rad etish",  callback_data=f"admin_reject_{tx['id']}")]
            ])
            try:
                await context.bot.send_photo(
                    chat_id=update.effective_user.id,
                    photo=tx['screenshot_id'],
                    caption=(
                        f"💳 To'lov #{tx['id']}\n"
                        f"👤 {name} (`{tx['user_id']}`)\n"
                        f"💰 {tx['amount']:,} so'm"
                    ),
                    reply_markup=kb,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Pending to'lov ko'rsatishda xatolik: {e}")
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="adm_back")]])
        await query.edit_message_text(f"⏳ {len(pending)} ta kutayotgan to'lov yuborildi.", reply_markup=back_kb)

    elif data == "adm_add_bal":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Balans qo'shish",      callback_data="adm_bal_add"),
             InlineKeyboardButton("⚙️ Balans o'rnatish",   callback_data="adm_bal_set")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="adm_back")],
        ])
        await query.edit_message_text(
            "💰 *Balans boshqarish*\n\n"
            "➕ *Qo'shish* \u2014 mavjud balansga qo'shadi\n"
            "⚙️ *O'rnatish* \u2014 balansi to'g'ridan-to'g'ri o'rnatadi (chek bilan farq bo'lganda)",
            reply_markup=kb,
            parse_mode="Markdown"
        )
    elif data == "adm_bal_add":
        await query.edit_message_text(
            "➕ *Balans qo'shish*\n\n"
            "Foydalanuvchi ID va *qo'shish miqdorini* yuboring:\n"
            "Format: `user_id miqdor`\n"
            "Masalan: `123456789 10000`\n\n"
            "⚠️ Bu amal mavjud balansga *qo'shadi*!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="adm_add_bal")]]),
            parse_mode="Markdown"
        )
        context.bot_data.setdefault("admin_modes", {})[update.effective_user.id] = "add_balance"
    elif data == "adm_bal_set":
        await query.edit_message_text(
            "⚙️ *Balans o'rnatish*\n\n"
            "Foydalanuvchi ID va *yangi balans miqdorini* yuboring:\n"
            "Format: `user_id yangi_miqdor`\n"
            "Masalan: `123456789 25000`\n\n"
            "⚠️ Bu amal mavjud balansni *to'liq almashtiradi*!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="adm_add_bal")]]),
            parse_mode="Markdown"
        )
        context.bot_data.setdefault("admin_modes", {})[update.effective_user.id] = "set_balance"

    elif data == "adm_broadcast":
        await query.edit_message_text(
            "📢 *Xabar yuborish*\n\n/broadcast buyrug'ini yuboring.\nFormat: `/broadcast Xabar matni`",
            parse_mode="Markdown"
        )
    elif data == "adm_delete_user":
        await query.edit_message_text(
            "🗑️ *Foydalanuvchi o'chirish*\n\n"
            "O'chirmoqchi bo'lgan foydalanuvchining *Telegram ID* sini yuboring.\n\n"
            "Masalan: `123456789`\n\n"
            "⚠️ Bu amal *qaytarib bo'lmaydi* \u2014 foydalanuvchining barcha ma'lumotlari (balans, tarix) o'chiriladi!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Orqaga", callback_data="adm_back")
            ]]),
            parse_mode="Markdown"
        )
        # bot_data - global dict, ConversationHandler dan mustaqil, barcha handlerlar uchun bir xil
        context.bot_data.setdefault("admin_modes", {})[update.effective_user.id] = "delete_user"
    elif data.startswith("adm_confirm_delete_"):
        target_id = int(data.split("_")[-1])
        # Foydalanuvchi ma'lumotlarini olish
        target_user = await asyncio.to_thread(db.get_user, target_id)
        if not target_user:
            await query.edit_message_text(
                f"❌ Foydalanuvchi `{target_id}` topilmadi.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Orqaga", callback_data="adm_back")
                ]]),
                parse_mode="Markdown"
            )
            return
        name = esc_md(target_user.get('full_name') or target_user.get('username') or str(target_id))
        bal = target_user.get('balance', 0)
        await query.edit_message_text(
            f"⚠️ *Tasdiqlang!*\n\n"
            f"👤 Foydalanuvchi: {name}\n"
            f"🆔 ID: `{target_id}`\n"
            f"💰 Balans: `{bal:,}` so'm\n\n"
            f"Bu foydalanuvchini *to'liq o'chirasizmi?*",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑️ Ha, o'chirish", callback_data=f"adm_do_delete_{target_id}"),
                 InlineKeyboardButton("❌ Bekor qilish", callback_data="adm_back")]
            ]),
            parse_mode="Markdown"
        )
    elif data.startswith("adm_do_delete_"):
        target_id = int(data.split("_")[-1])
        target_user = await asyncio.to_thread(db.get_user, target_id)
        if not target_user:
            await query.edit_message_text(
                f"❌ Foydalanuvchi `{target_id}` topilmadi yoki allaqachon o'chirilgan.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Orqaga", callback_data="adm_back")
                ]]),
                parse_mode="Markdown"
            )
            return
        name = esc_md(target_user.get('full_name') or target_user.get('username') or str(target_id))
        success = await asyncio.to_thread(db.delete_user, target_id)
        if success:
            logger.info(f"Admin {update.effective_user.id} foydalanuvchi {target_id} ni o'chirdi")
            await query.edit_message_text(
                f"✅ *O'chirildi!*\n\n"
                f"👤 {name} (`{target_id}`) bazadan to'liq o'chirildi.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Orqaga", callback_data="adm_back")
                ]]),
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                f"❌ O'chirishda xatolik yuz berdi.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Orqaga", callback_data="adm_back")
                ]]),
                parse_mode="Markdown"
            )
    elif data == "adm_noop":
        await query.answer()
        return
    elif data == "adm_back":
        # Admin mode ni tozalash (agar aktiv bo'lsa)
        context.bot_data.setdefault("admin_modes", {})[update.effective_user.id] = None
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Statistika",           callback_data="adm_stats"),
             InlineKeyboardButton("👥 Foydalanuvchilar",    callback_data="adm_users")],
            [InlineKeyboardButton("⏳ Kutayotgan to'lovlar", callback_data="adm_pending"),
             InlineKeyboardButton("💰 Balans qo'shish",     callback_data="adm_add_bal")],
            [InlineKeyboardButton("📢 Xabar yuborish",      callback_data="adm_broadcast")],
            [InlineKeyboardButton("🗑️ Foydalanuvchi o'chirish", callback_data="adm_delete_user")],
        ])
        await query.edit_message_text(
            "🔐 *Admin Panel*\n\nQuyidagi bo'limlardan birini tanlang:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

async def admin_add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin qo'lda balans qo'shadi: /admin_addbal user_id miqdor"""
    if update.effective_user.id not in ADMIN_IDS:
        return
    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text("Format: /admin_addbal user_id miqdor")
        return
    try:
        target_id = int(args[0])
        amount    = int(args[1])
    except ValueError:
        await update.message.reply_text("⚠️ Noto'g'ri format. Masalan: /admin_addbal 123456 5000")
        return
    # Foydalanuvchi mavjudligini tekshirish
    target_user = await asyncio.to_thread(db.get_user, target_id)
    if not target_user:
        await update.message.reply_text(
            f"❌ Foydalanuvchi `{target_id}` topilmadi.",
            parse_mode="Markdown"
        )
        return
    old_balance = target_user.get('balance', 0)
    await asyncio.to_thread(db.add_balance, target_id, amount)
    # Jami tushum uchun topup transaction yozish
    await asyncio.to_thread(db.create_topup_request_approved, target_id, amount)
    new_balance = old_balance + amount
    await update.message.reply_text(
        f"✅ *Balans qo'shildi!*\n\n"
        f"🆔 ID: `{target_id}`\n"
        f"💰 Eski: `{old_balance:,}` so'm\n"
        f"➕ Qo'shildi: `{amount:,}` so'm\n"
        f"💰 Yangi: `{new_balance:,}` so'm",
        parse_mode="Markdown"
    )
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"✅ Balansingizga *{amount:,} so'm* qo'shildi (admin tomonidan).",
            parse_mode="Markdown"
        )
    except Exception:
        pass

async def admin_delete_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin xabarlarini boshqaradi: foydalanuvchi o'chirish va balans o'rnatish.
    ConversationHandler ichida ham, tashqarisida ham ishlaydi.
    """
    if update.effective_user.id not in ADMIN_IDS:
        return
    adm_mode = context.bot_data.get("admin_modes", {}).get(update.effective_user.id)

    # ── Balans qo'shish rejimi ─────────────────────────────────────────────────
    if adm_mode == "add_balance":
        text = update.message.text.strip()
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text(
                "⚠️ Format: `user_id miqdor`\nMasalan: `123456789 10000`",
                parse_mode="Markdown"
            )
            return
        try:
            target_id = int(parts[0])
            amount    = int(parts[1])
        except ValueError:
            await update.message.reply_text(
                "⚠️ Faqat raqam kiriting. Masalan: `123456789 10000`",
                parse_mode="Markdown"
            )
            return
        if amount <= 0:
            await update.message.reply_text("⚠️ Miqdor 0 dan katta bo'lishi kerak.")
            return
        target_user = await asyncio.to_thread(db.get_user, target_id)
        if not target_user:
            await update.message.reply_text(
                f"❌ Foydalanuvchi `{target_id}` topilmadi.",
                parse_mode="Markdown"
            )
            return
        old_balance = target_user.get('balance', 0)
        name = esc_md(target_user.get('full_name') or target_user.get('username') or str(target_id))
        await asyncio.to_thread(db.add_balance, target_id, amount)
        # Jami tushum uchun topup transaction yozish (status=approved)
        await asyncio.to_thread(db.create_topup_request_approved, target_id, amount)
        context.bot_data.setdefault("admin_modes", {})[update.effective_user.id] = None
        new_balance = old_balance + amount
        logger.info(f"Admin {update.effective_user.id}: {target_id} ga {amount} so'm qo'shildi ({old_balance} -> {new_balance})")
        await update.message.reply_text(
            f"✅ *Balans qo'shildi!*\n\n"
            f"👤 {name} (`{target_id}`)\n"
            f"💰 Eski balans: `{old_balance:,}` so'm\n"
            f"➕ Qo'shildi: `{amount:,}` so'm\n"
            f"💰 Yangi balans: `{new_balance:,}` so'm",
            parse_mode="Markdown"
        )
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"✅ Balansingizga *{amount:,} so'm* qo'shildi (admin tomonidan).",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return

    # ── Balans o'rnatish rejimi ──────────────────────────────────────────────
    if adm_mode == "set_balance":
        text = update.message.text.strip()
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text(
                "⚠️ Format: `user_id yangi_miqdor`\nMasalan: `123456789 25000`",
                parse_mode="Markdown"
            )
            return
        try:
            target_id  = int(parts[0])
            new_balance = int(parts[1])
        except ValueError:
            await update.message.reply_text(
                "⚠️ Faqat raqam kiriting. Masalan: `123456789 25000`",
                parse_mode="Markdown"
            )
            return
        if new_balance < 0:
            await update.message.reply_text("⚠️ Balans manfiy bo'lishi mumkin emas.")
            return
        target_user = await asyncio.to_thread(db.get_user, target_id)
        if not target_user:
            await update.message.reply_text(
                f"❌ Foydalanuvchi `{target_id}` topilmadi.",
                parse_mode="Markdown"
            )
            return
        old_balance = target_user.get('balance', 0)
        name = esc_md(target_user.get('full_name') or target_user.get('username') or str(target_id))
        success = await asyncio.to_thread(db.set_balance, target_id, new_balance)
        context.bot_data.setdefault("admin_modes", {})[update.effective_user.id] = None
        if success:
            logger.info(f"Admin {update.effective_user.id}: {target_id} balansi {old_balance} -> {new_balance}")
            await update.message.reply_text(
                f"✅ *Balans o'rnatildi!*\n\n"
                f"👤 {name} (`{target_id}`)\n"
                f"💰 Eski balans: `{old_balance:,}` so'm\n"
                f"💰 Yangi balans: `{new_balance:,}` so'm",
                parse_mode="Markdown"
            )
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=f"💰 Balansingiz *{new_balance:,} so'm* ga o'rnatildi (admin tomonidan).",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        else:
            await update.message.reply_text("❌ Balansni o'rnatishda xatolik yuz berdi.")
        return

    # ── Foydalanuvchi o'chirish rejimi ───────────────────────────────────────
    if adm_mode == "delete_user":
        text = update.message.text.strip()
        try:
            target_id = int(text)
        except ValueError:
            await update.message.reply_text(
                "⚠️ Faqat raqam kiriting. Masalan: `123456789`",
                parse_mode="Markdown"
            )
            return
        target_user = await asyncio.to_thread(db.get_user, target_id)
        if not target_user:
            await update.message.reply_text(
                f"❌ Foydalanuvchi `{target_id}` topilmadi.",
                parse_mode="Markdown"
            )
            return
        name = esc_md(target_user.get('full_name') or target_user.get('username') or str(target_id))
        bal = target_user.get('balance', 0)
        context.bot_data.setdefault("admin_modes", {})[update.effective_user.id] = None
        await update.message.reply_text(
            f"⚠️ *Tasdiqlang!*\n\n"
            f"👤 Foydalanuvchi: {name}\n"
            f"🆔 ID: `{target_id}`\n"
            f"💰 Balans: `{bal:,}` so'm\n\n"
            f"Bu foydalanuvchini *to'liq o'chirasizmi?*",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑️ Ha, o'chirish", callback_data=f"adm_do_delete_{target_id}"),
                 InlineKeyboardButton("❌ Bekor qilish", callback_data="adm_back")]
            ]),
            parse_mode="Markdown"
        )
        return

    # ── Boshqa xabarlar ─────────────────────────────────────────────────────
    return await handle_main_menu_selection(update, context)


async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Barcha foydalanuvchilarga xabar yuboradi: /broadcast Xabar"""
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not context.args:
        await update.message.reply_text("Format: /broadcast Xabar matni")
        return
    text = " ".join(context.args)
    users = await asyncio.to_thread(db.get_all_users, limit=5000)
    sent = 0
    failed = 0
    for u in users:
        try:
            await context.bot.send_message(chat_id=u['user_id'], text=text)
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(f"📢 Yuborildi: {sent} | Muvaffaqiyatsiz: {failed}")

async def admin_user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi haqida ma'lumot: /user_info user_id"""
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not context.args:
        await update.message.reply_text("Format: /user_info user_id")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ Noto'g'ri ID")
        return
    u = await asyncio.to_thread(db.get_user, target_id)
    if not u:
        await update.message.reply_text("❌ Foydalanuvchi topilmadi.")
        return
    await update.message.reply_text(
        f"👤 *Foydalanuvchi ma'lumotlari*\n\n"
        f"ID: `{u['user_id']}`\n"
        f"Ism: {esc_md(u['full_name'] or 'Nomsiz')}\n"
        f"Username: @{esc_md(u['username'] or 'yoq')}\n"
        f"💰 Balans: *{u['balance']:,} so'm*\n"
        f"🔗 Referral kodi: `{u['referral_code']}`\n"
        f"📅 Qo'shilgan: {u['joined_at']}\n"
        f"⏰ Oxirgi faollik: {u['last_active']}",
        parse_mode="Markdown"
    )

# ─────────────────────────────────────────────
# Asosiy funksiya
# ─────────────────────────────────────────────

def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("BOT_TOKEN topilmadi!")
        return

    application = (
        Application.builder()
        .token(token)
        .concurrent_updates(True)  # Parallel foydalanuvchilar uchun
        .build()
    )

    # ── Slayd yaratish ──
    slayd_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("chekyubor", chekyubor_command),
            MessageHandler(filters.Regex(r"^🪄 Slayd yaratish ✨$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^📄 Mustaqil ish ✨$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^📚 Referat ✨$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^📁 Loyiha ishi ✨$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^📊 Infografika ✨$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^💰 Balans$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^🔗 Referral$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^🤖 AI yordamchi 💬$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^📰 Maqola ✨$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^🎓 Kurs ishi / BMI 📝$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^📜 Tezis ✨$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^💡 Glossary ✨$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^🔠 Test tuzish$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^🧩 Krossvord ✨$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^✍️ Insho / Esse ✨$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^📂 Hujjat & Dizayn ✨$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^📋 Annotatsiya ✨$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^📝 Taqriz ✨$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^📦 Ziplash/Arxivlash 🗜️$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^📄 PDF Konvertatsiya 🔄$"), handle_main_menu_selection),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu_selection),
            CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
        ],
        per_message=False,
        states={
            LANGUAGE_SELECTION: [
                CommandHandler("chekyubor", chekyubor_command),
                CallbackQueryHandler(get_language, pattern=r"^lang_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.Regex(r"^🪄 Slayd yaratish ✨$"), handle_main_menu_selection),
                MessageHandler(filters.Regex(r"^📄 Mustaqil ish ✨$"), handle_main_menu_selection),
                MessageHandler(filters.Regex(r"^📚 Referat ✨$"), handle_main_menu_selection),
                MessageHandler(filters.Regex(r"^📁 Loyiha ishi ✨$"), handle_main_menu_selection),
                MessageHandler(filters.Regex(r"^📊 Infografika ✨$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^💰 Balans$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^🔗 Referral$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^🤖 AI yordamchi 💬$"), handle_main_menu_selection),
            # Boshqa barcha tugmalar
                MessageHandler(filters.Regex(r"^🎓 Kurs ishi / BMI 📝$"), handle_main_menu_selection),
                MessageHandler(filters.Regex(r"^📜 Tezis ✨$"), handle_main_menu_selection),
                MessageHandler(filters.Regex(r"^💡 Glossary ✨$"), handle_main_menu_selection),
                MessageHandler(filters.Regex(r"^🔠 Test tuzish$"), handle_main_menu_selection),
                MessageHandler(filters.Regex(r"^🧩 Krossvord ✨$"), handle_main_menu_selection),
                MessageHandler(filters.Regex(r"^✍️ Insho / Esse ✨$"), handle_main_menu_selection),
                MessageHandler(filters.Regex(r"^📂 Hujjat & Dizayn ✨$"), handle_main_menu_selection),
                MessageHandler(filters.Regex(r"^📰 Maqola ✨$"), handle_main_menu_selection),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & ~MENU_FILTER & filters.User(ADMIN_IDS),
                    admin_delete_user_message
                ),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, handle_main_menu_selection),
            ],
            TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, get_topic),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            NAME_SURNAME: [
                CallbackQueryHandler(get_name_surname, pattern=r"^skip_name_surname$"),
                CallbackQueryHandler(edit_topic_handler, pattern=r"^edit_topic$"),
                CallbackQueryHandler(edit_name_handler, pattern=r"^edit_name$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, get_name_surname),
            ],
            SLIDE_COUNT: [
                CallbackQueryHandler(get_slide_count, pattern=r"^slide_count_"),
                CallbackQueryHandler(edit_topic_handler, pattern=r"^edit_topic$"),
                CallbackQueryHandler(edit_name_handler, pattern=r"^edit_name$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            PLAN_CONFIRMATION: [
                CallbackQueryHandler(plan_confirmation, pattern=r"^plan_confirm_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            TEMPLATE_SELECT: [
                CallbackQueryHandler(template_selected, pattern=r"^template_select_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            IMAGE_SOURCE_SELECT: [
                CallbackQueryHandler(image_source_handler, pattern=r"^img_source_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            USER_IMAGE_COLLECT: [
                MessageHandler(filters.PHOTO, user_image_collect_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, user_image_collect_handler),
                CommandHandler("skip", user_image_collect_handler),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            # ── Mustaqil ish holatlari ──
            MI_LANGUAGE: [
                CallbackQueryHandler(mi_get_language, pattern=r"^mi_lang_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            MI_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, mi_get_topic),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            MI_NAME_SURNAME: [
                CallbackQueryHandler(mi_get_name_surname, pattern=r"^mi_skip_name$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, mi_get_name_surname),
            ],
            MI_PAGE_COUNT: [
                CallbackQueryHandler(mi_get_page_count, pattern=r"^mi_pages_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            MI_UNIVERSITY: [
                CallbackQueryHandler(mi_get_university, pattern=r"^mi_skip_university$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, mi_get_university),
            ],
            MI_TEACHER: [
                CallbackQueryHandler(mi_get_teacher, pattern=r"^mi_skip_teacher$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, mi_get_teacher),
            ],
            # ── Loyiha ishi holatlari ──
            LI_LANGUAGE: [
                CallbackQueryHandler(li_get_language, pattern=r"^li_lang_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            LI_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, li_get_topic),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            LI_NAME_SURNAME: [
                CallbackQueryHandler(li_get_name_surname, pattern=r"^li_skip_name$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, li_get_name_surname),
            ],
            LI_PAGE_COUNT: [
                CallbackQueryHandler(li_get_page_count, pattern=r"^li_pages_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            LI_UNIVERSITY: [
                CallbackQueryHandler(li_get_university, pattern=r"^li_skip_university$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, li_get_university),
            ],
            LI_SUBJECT: [
                CallbackQueryHandler(li_get_subject, pattern=r"^li_skip_subject$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, li_get_subject),
            ],
            LI_TEACHER: [
                CallbackQueryHandler(li_get_teacher, pattern=r"^li_skip_teacher$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, li_get_teacher),
            ],
            # ── Referat holatlari ──
            RF_LANGUAGE: [
                CallbackQueryHandler(rf_get_language, pattern=r"^rf_lang_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            RF_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, rf_get_topic),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            RF_NAME_SURNAME: [
                CallbackQueryHandler(rf_get_name_surname, pattern=r"^rf_skip_name$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, rf_get_name_surname),
            ],
            RF_PAGE_COUNT: [
                CallbackQueryHandler(rf_get_page_count, pattern=r"^rf_pages_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            RF_UNIVERSITY: [
                CallbackQueryHandler(rf_get_university, pattern=r"^rf_skip_university$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, rf_get_university),
            ],
            RF_TEACHER: [
                CallbackQueryHandler(rf_get_teacher, pattern=r"^rf_skip_teacher$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, rf_get_teacher),
            ],
            # ── Infografika holatlari ──
            IG_LANGUAGE: [
                CallbackQueryHandler(ig_get_language, pattern=r"^ig_lang_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            IG_TYPE: [
                CallbackQueryHandler(ig_get_type, pattern=r"^ig_type_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            IG_COLOR: [
                CallbackQueryHandler(ig_get_color, pattern=r"^ig_color_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            IG_QUALITY: [
                CallbackQueryHandler(ig_get_quality, pattern=r"^ig_quality_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            IG_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, ig_get_topic),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            # ── Maqola holatlari ──
            MQ_LANGUAGE: [
                CallbackQueryHandler(mq_get_language, pattern=r"^mq_lang_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            MQ_TYPE: [
                CallbackQueryHandler(mq_get_type, pattern=r"^mq_type_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            MQ_PAGE_COUNT: [
                CallbackQueryHandler(mq_get_page_count, pattern=r"^mq_pages_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            MQ_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, mq_get_topic),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            MQ_NAME_SURNAME: [
                CallbackQueryHandler(mq_get_name_surname, pattern=r"^mq_skip_name$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, mq_get_name_surname),
            ],
            MQ_UNIVERSITY: [
                CallbackQueryHandler(mq_get_university, pattern=r"^mq_skip_university$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, mq_get_university),
            ],
            # ── Kurs ishi / BMI holatlari ──
            KI_TYPE: [
                CallbackQueryHandler(ki_get_type, pattern=r"^ki_type_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            KI_LANGUAGE: [
                CallbackQueryHandler(ki_get_language, pattern=r"^ki_lang_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            KI_PAGE_COUNT: [
                CallbackQueryHandler(ki_get_page_count, pattern=r"^ki_pages_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            KI_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, ki_get_topic),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            KI_NAME_SURNAME: [
                CallbackQueryHandler(ki_get_name_surname, pattern=r"^ki_skip_name$"),
                CallbackQueryHandler(ki_edit_topic, pattern=r"^ki_edit_topic$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, ki_get_name_surname),
            ],
            KI_EDIT_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, ki_edit_topic_save),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            KI_UNIVERSITY: [
                CallbackQueryHandler(ki_get_university, pattern=r"^ki_skip_university$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, ki_get_university),
            ],
            KI_FACULTY: [
                CallbackQueryHandler(ki_get_faculty, pattern=r"^ki_skip_faculty$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, ki_get_faculty),
            ],
            KI_SUBJECT: [
                CallbackQueryHandler(ki_get_subject, pattern=r"^ki_skip_subject$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, ki_get_subject),
            ],
            KI_TEACHER: [
                CallbackQueryHandler(ki_get_teacher, pattern=r"^ki_skip_teacher$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, ki_get_teacher),
            ],
            # ── Tezis holatlari ──
            TZ_TYPE: [
                CallbackQueryHandler(tz_get_type, pattern=r"^tz_type_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            TZ_LANGUAGE: [
                CallbackQueryHandler(tz_get_language, pattern=r"^tz_lang_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            TZ_PAGE_COUNT: [
                CallbackQueryHandler(tz_get_page_count, pattern=r"^tz_pages_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            TZ_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, tz_get_topic),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            TZ_NAME_SURNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, tz_get_name),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            TZ_INSTITUTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, tz_get_institution),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            # ── Test tuzish holatlari ──
            TS_LANGUAGE: [
                CallbackQueryHandler(ts_get_language, pattern=r"^ts_lang_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            TS_COUNT: [
                CallbackQueryHandler(ts_get_count, pattern=r"^ts_count_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            TS_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, ts_get_topic),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            TS_AUTHOR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, ts_get_author),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            # ── Glossary holatlari ──
            GL_LANGUAGE: [
                CallbackQueryHandler(gl_get_language, pattern=r"^gl_lang_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            GL_SIZE: [
                CallbackQueryHandler(gl_get_size, pattern=r"^gl_size_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            GL_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, gl_get_topic),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            GL_AUTHOR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, gl_get_author),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            # ── Krossvord holatlari ──
            KR_LANGUAGE: [
                CallbackQueryHandler(kr_get_language, pattern=r"^kr_lang_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            KR_COUNT: [
                CallbackQueryHandler(kr_get_count, pattern=r"^kr_count_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            KR_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, kr_get_topic),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            KR_AUTHOR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, kr_get_author),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            # ── Insho / Esse holatlari ──
            IN_TYPE: [
                CallbackQueryHandler(in_get_type, pattern=r"^in_type_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            IN_LANGUAGE: [
                CallbackQueryHandler(in_get_language, pattern=r"^in_lang_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            IN_PAGE_COUNT: [
                CallbackQueryHandler(in_get_page_count, pattern=r"^in_pages_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            IN_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, in_get_topic),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            IN_NAME_SURNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, in_get_name_surname),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            IN_INSTITUTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, in_get_institution),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            # ── Hujjat & Dizayn holatlari ──
            HJ_MENU: [
                CallbackQueryHandler(hj_get_menu, pattern=r"^hj_(rezyume|motivatsion|jadval|mindmap)$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            HJ_LANG: [
                CallbackQueryHandler(hj_get_lang, pattern=r"^hj_lang_"),
                CallbackQueryHandler(hj_back_to_menu, pattern=r"^hj_back_to_menu$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            HJ_INPUT1: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, hj_get_input1),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            HJ_INPUT2: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, hj_get_input2),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            HJ_INPUT3: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, hj_get_input3),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            # ── Annotatsiya holatlari ──
            AN_LANGUAGE: [
                CallbackQueryHandler(an_get_language, pattern=r"^an_lang_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            AN_TYPE: [
                CallbackQueryHandler(an_get_type, pattern=r"^an_type_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            AN_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, an_get_title),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            AN_AUTHOR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, an_get_author),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            # ── Taqriz holatlari ──
            TQ_LANGUAGE: [
                CallbackQueryHandler(tq_get_language, pattern=r"^tq_lang_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            TQ_TYPE: [
                CallbackQueryHandler(tq_get_type, pattern=r"^tq_type_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            TQ_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, tq_get_title),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            TQ_AUTHOR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, tq_get_author),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            TQ_REVIEWER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, tq_get_reviewer),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            TQ_SUMMARY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, tq_get_summary),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            # ── Arxivlash holatlari ──
            ARX_RECEIVE: [
                MessageHandler(
                    filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE,
                    arx_receive_file
                ),
                CallbackQueryHandler(arx_done_callback, pattern=r"^arx_done$"),
                CallbackQueryHandler(arx_cancel_callback, pattern=r"^arx_cancel$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            # ── PDF Konvertatsiya holatlari ──
            PDF_RECEIVE: [
                MessageHandler(
                    filters.Document.ALL | filters.PHOTO,
                    pdf_receive_file
                ),
                CallbackQueryHandler(pdf_again_callback, pattern=r"^pdf_again$"),
                CallbackQueryHandler(pdf_cancel_callback, pattern=r"^pdf_cancel$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            # ── AI Yordamchi holatlari ──
            AI_CHAT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, ai_chat_handler),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            # ── Rezyume CV holatlari ──
            CV_LANG: [
                CallbackQueryHandler(cv_get_lang, pattern=r"^cv_lang_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            CV_FULLNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, cv_get_fullname),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            CV_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, cv_get_email),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            CV_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, cv_get_phone),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            CV_LOCATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, cv_get_location),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            CV_LINKS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, cv_get_links),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            CV_PHOTO: [
                MessageHandler(filters.PHOTO | (filters.TEXT & ~filters.COMMAND), cv_get_photo),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            CV_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, cv_get_title),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            CV_REGION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, cv_get_region),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            CV_SUMMARY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, cv_get_summary),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            CV_EXPERIENCE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, cv_get_experience),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            CV_PROJECTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, cv_get_projects),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            CV_EDUCATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, cv_get_education),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            CV_CERTIFICATIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, cv_get_certifications),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            CV_SKILLS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, cv_get_skills),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            CV_TONE: [
                CallbackQueryHandler(cv_get_tone, pattern=r"^cv_tone_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            CV_LENGTH: [
                CallbackQueryHandler(cv_get_length, pattern=r"^cv_length_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            # ── Balans to'ldirish holatlari ──
            TOPUP_AMOUNT: [
                CommandHandler("chekyubor", chekyubor_command),
                MessageHandler(MENU_FILTER, handle_main_menu_selection),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, topup_handle_amount),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            TOPUP_SCREENSHOT: [
                CommandHandler("chekyubor", chekyubor_command),
                MessageHandler(filters.PHOTO, topup_get_screenshot),
                MessageHandler(filters.Document.ALL, topup_get_screenshot),
                MessageHandler(MENU_FILTER, handle_main_menu_selection),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_FILTER, topup_handle_screenshot_text),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("cancel", cancel),
            CommandHandler("chekyubor", chekyubor_command),
            # Admin xabarlari - barcha state larda ishlashi uchun fallbacks da
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.User(ADMIN_IDS),
                admin_delete_user_message
            ),
            MessageHandler(MENU_FILTER, handle_main_menu_selection),
        ],
    )

    application.add_handler(slayd_handler)
    # Admin handlerlari
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("admin_addbal", admin_add_balance))
    application.add_handler(CommandHandler("broadcast", admin_broadcast))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.User(ADMIN_IDS),
        admin_delete_user_message
    ))
    application.add_handler(CommandHandler("user_info", admin_user_info))

    # Admin callback handlerlari
    application.add_handler(CallbackQueryHandler(admin_callback,      pattern=r"^adm_"))
    application.add_handler(CallbackQueryHandler(admin_approve_topup,        pattern=r"^admin_approve_"))
    application.add_handler(CallbackQueryHandler(admin_reject_topup,          pattern=r"^admin_reject_"))
    application.add_handler(CallbackQueryHandler(admin_custom_amount_callback, pattern=r"^admin_custom_amount_"))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.User(ADMIN_IDS),
        admin_custom_amount_text
    ), group=1)
    application.add_handler(CallbackQueryHandler(check_sub_callback,  pattern=r"^check_sub$"))

    # Balans va Referral menyu handlerlari
    application.add_handler(MessageHandler(
        filters.Regex(r"^💰 Balans$"),
        handle_main_menu_selection
    ))
    application.add_handler(MessageHandler(
        filters.Regex(r"^🔗 Referral$"),
        handle_main_menu_selection
    ))

    # ESLATMA: topup_get_screenshot TOPUP_SCREENSHOT state ichida ishlaydi (ConversationHandler)
    # Global handler olib tashlandi — ikki marta chaqirilishni oldini olish uchun

    logger.info("Bot ishga tushmoqda (polling rejimi, concurrent_updates=True)...")
    application.run_polling(
        drop_pending_updates=True,  # Restart paytida eski xabarlarni o'tkazib yuborish
        allowed_updates=["message", "callback_query", "chat_member"],
    )

if __name__ == "__main__":
    main()
