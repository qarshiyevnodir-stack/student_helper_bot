import json
import logging
import os
import asyncio
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
    generate_plan_with_titles,
    generate_all_content,
    SLIDE_TYPE_NAMES,
    SLIDE_TYPE_NAMES_T3,
    SLIDE_TYPE_NAMES_T4,
    SLIDE_TYPE_NAMES_T5,
)
from mustaqil_ish_utils import generate_mustaqil_ish
from loyiha_ishi_utils import generate_loyiha_ishi
from infografika_utils import generate_infografika, generate_infografika_hd
from maqola_utils import generate_maqola
from pptx import Presentation

# ─────────────────────────────────────────────
# Admin va narx sozlamalari
# ─────────────────────────────────────────────
ADMIN_IDS = {6813160650}
ARCHIVE_CHANNEL = -1003599976854  # Arxiv kanal ID
CARD_NUMBER = "9860 1606 3105 8700"  # Abramatova Madina
SERVICE_PRICES = {
    "slayd":        3000,
    "mustaqil_ish": 3000,
    "referat":      3000,
    "loyiha_ishi":  3000,
    "infografika":      1500,
    "infografika_hd":   3000,
    "maqola":           3000,
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
(
    LANGUAGE_SELECTION,  # 0 — til tanlash
    TOPIC,               # 1 — mavzu kiritish
    NAME_SURNAME,        # 2 — ism-familiya
    SLIDE_COUNT,         # 3 — slayd soni
    PLAN_CONFIRMATION,   # 4 — reja tasdiqlash
) = range(5)

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
        [KeyboardButton("🎓 Kurs ishi 📝"),    KeyboardButton("📚 Referat ✨")],
        [KeyboardButton("📜 Tezis ✨"),         KeyboardButton("💡 Glossary ✨")],
        [KeyboardButton("🧩 Krossvord ✨"),     KeyboardButton("🔠 Test tuzish")],
        [KeyboardButton("💰 Balans & Referral 🔗")],
        [KeyboardButton("🖼️ Rasm yaratish"),   KeyboardButton("🎬 Video yaratish")],
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
        [InlineKeyboardButton("10", callback_data="rf_pages_10"),
         InlineKeyboardButton("15", callback_data="rf_pages_15"),
         InlineKeyboardButton("20", callback_data="rf_pages_20")],
        [InlineKeyboardButton("25", callback_data="rf_pages_25"),
         InlineKeyboardButton("30", callback_data="rf_pages_30")],
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
        [InlineKeyboardButton("10", callback_data="mi_pages_10"),
         InlineKeyboardButton("15", callback_data="mi_pages_15"),
         InlineKeyboardButton("20", callback_data="mi_pages_20")],
        [InlineKeyboardButton("25", callback_data="mi_pages_25"),
         InlineKeyboardButton("30", callback_data="mi_pages_30")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_plan_confirmation_keyboard():
    keyboard = [
        [InlineKeyboardButton("✅ Tasdiqlash",   callback_data="plan_confirm_yes"),
         InlineKeyboardButton("🔄 Qayta tuzish", callback_data="plan_confirm_no")],
    ]
    return InlineKeyboardMarkup(keyboard)


# ─────────────────────────────────────────────
# Yordamchi: reja matnini chiroyli formatlash
# ─────────────────────────────────────────────

def format_plan_message(topic, slide_count, language_name, plan_items):
    """Foydalanuvchiga ko'rsatiladigan reja xabarini formatlaydi."""
    import re
    clean_lines = []
    for idx, item in enumerate(plan_items):
        text = re.sub(r'^[\d]+[\d\.]*\.?\s*', '', str(item)).strip()
        clean_lines.append(f"{idx+1}. {text}")
    plan_lines = "\n".join(clean_lines)
    return (
        f"📋 *Reja tayyor!*\n\n"
        f"📌 *Mavzu:* {topic}\n"
        f"🌐 *Til:* {language_name}\n"
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
        # BytesIO bo'lsa, o'qish pozitsiyasini boshiga qaytarish
        if hasattr(document_bytes, 'seek'):
            document_bytes.seek(0)
            archive_doc = BytesIO(document_bytes.read())
            archive_doc.seek(0)
        else:
            archive_doc = document_bytes
        await bot.send_document(
            chat_id=ARCHIVE_CHANNEL,
            document=archive_doc,
            filename=filename,
            caption=caption
        )
    except Exception as e:
        logger.warning(f"Arxiv kanalga yuborishda xatolik: {e}")


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
# Handlerlar — Umumiy
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Botni ishga tushiradi va asosiy menyu ko'rsatadi."""
    context.user_data.clear()
    user = update.effective_user
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
    bonus_given = await asyncio.to_thread(db.give_welcome_bonus, user.id, 6000)

    if bonus_given:
        await update.message.reply_text(
            f"Assalomu alaykum, {user.first_name}! 👋\n\n"
            f"🎁 *Xush kelibsiz bonusi:* `6,000 so'm` balansingizga qo'shildi!\n"
            f"Bu bonus faqat bir marta beriladi.\n\n"
            f"Quyidagi xizmatlardan birini tanlang:",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
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
    # Har qanday menyu tugmasi bosilganda topup holatini tozalash
    # (foydalanuvchi topup oqimini bekor qilib boshqa xizmatga o'tgan bo'lishi mumkin)
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

    elif text == "💰 Balans & Referral 🔗":
        user_data = await asyncio.to_thread(db.get_user, user.id)
        balance = user_data['balance'] if user_data else 0
        ref_code = user_data['referral_code'] if user_data else ''
        bot_username = (await context.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start=ref_{ref_code}"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Balans to'ldirish", callback_data="topup_start")]
        ])
        await update.message.reply_text(
            f"💰 *Balansingiz:* `{balance:,}` so'm\n\n"
            f"🔗 *Referral havolangiz:*\n`{ref_link}`\n\n"
            f"Do'stlaringizni taklif qiling va bonuslar oling!",
            reply_markup=keyboard,
            parse_mode="Markdown"
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
        text=f"✅ Til: *{lang_name}*\n\nEndi taqdimot mavzusini kiriting:",
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

    skip_button = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ O'tkazib yuborish", callback_data="skip_name_surname")]
    ])
    await update.message.reply_text(
        f"📌 *Mavzu:* {topic}\n\nIsm va familiyangizni kiriting (ixtiyoriy):",
        reply_markup=skip_button,
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
        await query.edit_message_text(
            text="Nechta slayd kerak?",
            reply_markup=get_slide_count_keyboard()
        )
    else:
        name_surname = update.message.text.strip()
        context.user_data["name_surname"] = name_surname
        await update.message.reply_text(
            "Nechta slayd kerak?",
            reply_markup=get_slide_count_keyboard()
        )
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
            "plan": [f"1. {topic} haqida umumiy ma'lumot",
                     f"2. {topic} ning asosiy jihatlari",
                     f"3. {topic} ning ahamiyati"],
            "slide_titles": [f"{topic} — {i+1}" for i in range(slide_count)]
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
                "plan": [f"1. {topic} haqida umumiy ma'lumot",
                         f"2. {topic} ning asosiy jihatlari",
                         f"3. {topic} ning ahamiyati"],
                "slide_titles": [f"{topic} — {i+1}" for i in range(slide_count)]
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
    await query.edit_message_text(
        text="✅ Reja tasdiqlandi!\n\n⏳ Kontent yaratilmoqda, biroz kuting...",
        parse_mode="Markdown"
    )

    stage1 = context.user_data.get("stage1_result", {})
    plan_items   = stage1.get("plan", [])
    slide_titles = stage1.get("slide_titles", [])
    plan_dict = {"title": "Reja", "content": plan_items}
    chat_id = query.message.chat_id

    # ── Tasodifiy shablon tanlash (1-5) ──
    template_num = random.randint(1, 5)
    template_slide_type_names = {
        1: SLIDE_TYPE_NAMES,
        2: SLIDE_TYPE_NAMES,
        3: SLIDE_TYPE_NAMES_T3,
        4: SLIDE_TYPE_NAMES_T4,
        5: SLIDE_TYPE_NAMES_T5,
    }[template_num]
    template_generate_func = {
        1: generate_template_1_presentation,
        2: generate_template_2_presentation,
        3: generate_template_3_presentation,
        4: generate_template_4_presentation,
        5: generate_template_5_presentation,
    }[template_num]
    logger.info(f"Tasodifiy tanlangan shablon: {template_num}")

    try:
        content_data_list = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: generate_all_content(topic, slide_count, language, slide_titles, template_slide_type_names)
        )

        if not content_data_list:
            raise ValueError("generate_all_content bo'sh qaytdi")

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
            )
        )

        safe_topic = "".join(c for c in topic[:30] if c.isalnum() or c in " _-").strip()
        filename = f"{safe_topic or 'taqdimot'}.pptx"

        # Fayl yuborildi — faqat shundan keyin balansdan yechish
        await context.bot.send_document(
            chat_id=chat_id,
            document=presentation_bytes,
            filename=filename,
            caption=(
                f"✅ *{topic}* — taqdimot tayyor!\n"
                f"📊 {slide_count} ta slayd | 📎 PPTX\n\n"
                f"📚 Biz bilan ishingiz oson!\n"
                f"🤖 @slidego\_bot\n"
                f"📢 t.me/slidego"
            ),
            parse_mode="Markdown"
        )
        # Arxiv kanalga yuborish
        _lang_name = context.user_data.get('language_name', language)
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
        await asyncio.to_thread(db.log_generation, user_id, 'slayd', topic, price)
        new_balance = await asyncio.to_thread(db.get_balance, user_id)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"💰 Balans: *{new_balance:,} so'm*\n\nYana biror narsa kerakmi?",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Prezentatsiya yaratishda xatolik: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Prezentatsiya yaratishda xatolik yuz berdi:\n`{str(e)}`\n\nIltimos, qayta urinib ko'ring. Balans yechilmadi.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )

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
        f"📌 *Mavzu:* {topic}\n\n"
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
        await context.bot.send_document(
            chat_id=chat_id,
            document=doc_bytes,
            filename=filename,
            caption=(
                f"✅ *{topic}* — loyiha ishi tayyor!\n"
                f"📄 Taxminiy {page_count} sahifa | 📎 DOCX\n\n"
                f"📚 Biz bilan ishingiz oson!\n"
                f"🤖 @slidego\_bot\n"
                f"📢 t.me/slidego"
            ),
            parse_mode="Markdown"
        )
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
        await asyncio.to_thread(db.log_generation, user_id, 'loyiha_ishi', topic, price)
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
        f"⏳ *{topic}* mavzusida *{quality_label}* infografika yaratilmoqda...\n"
        f"Bu biroz vaqt olishi mumkin, kuting!",
        parse_mode="Markdown"
    )
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
        await asyncio.to_thread(db.log_deduction, user_id, price, f"{service_label}: {topic}")
        # PNG yuborish
        with open(out_path, "rb") as f:
            await update.message.reply_photo(
                photo=f,
                caption=(
                    f"✅ *{topic}* — {quality_label} infografika tayyor!\n"
                    f"🖼 PNG\n\n"
                    f"📚 Biz bilan ishingiz oson!\n"
                    f"🤖 @slidego\_bot\n"
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
        f"📌 *Mavzu:* {topic}\n\n"
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
        await context.bot.send_document(
            chat_id=chat_id,
            document=doc_bytes,
            filename=filename,
            caption=(
                f"✅ *{topic}* — referat tayyor!\n"
                f"📄 Taxminiy {page_count} sahifa | 📎 DOCX\n\n"
                f"📚 Biz bilan ishingiz oson!\n"
                f"🤖 @slidego\_bot\n"
                f"📢 t.me/slidego"
            ),
            parse_mode="Markdown"
        )
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
        await asyncio.to_thread(db.log_generation, user_id, 'referat', topic, price)
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
        f"📌 *Mavzu:* {topic}\n\n"
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
        await context.bot.send_document(
            chat_id=chat_id,
            document=doc_bytes,
            filename=filename,
            caption=(
                f"✅ *{topic}* — mustaqil ish tayyor!\n"
                f"📄 Taxminiy {page_count} sahifa | 📎 DOCX\n\n"
                f"📚 Biz bilan ishingiz oson!\n"
                f"🤖 @slidego\_bot\n"
                f"📢 t.me/slidego"
            ),
            parse_mode="Markdown"
        )
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
        await asyncio.to_thread(db.log_generation, user_id, 'mustaqil_ish', topic, price)
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
        f"📌 *Mavzu:* {topic}\n\n"
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

        await context.bot.send_document(
            chat_id=chat_id,
            document=doc_bytes,
            filename=filename,
            caption=(
                f"✅ *{topic}* — maqola tayyor!\n"
                f"📰 Taxminiy {page_count} sahifa | 📎 DOCX\n\n"
                f"📚 Biz bilan ishingiz oson!\n"
                f"🤖 @slidego\_bot\n"
                f"📢 t.me/slidego"
            ),
            parse_mode="Markdown"
        )
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
        await asyncio.to_thread(db.log_generation, user_id, 'maqola', topic, price)
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


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Suhbatni bekor qiladi."""
    await update.message.reply_text(
        "Bekor qilindi. Yana yordamim kerakmi?",
        reply_markup=get_main_menu_keyboard()
    )
    return ConversationHandler.END


# ─────────────────────────────────────────────
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
async def topup_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Balans to'ldirish boshlaydi — callback yoki message orqali."""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            f"💳 *Balans to'ldirish*\n\n"
            f"Karta raqami: `{CARD_NUMBER}`\n\n"
            f"Minimal to'lov: *{MIN_TOPUP:,} so'm*\n\n"
            f"Qancha so'm to'lamoqchisiz? (raqam kiriting, masalan: 10000)",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"💳 *Balans to'ldirish*\n\n"
            f"Karta raqami: `{CARD_NUMBER}`\n\n"
            f"Minimal to'lov: *{MIN_TOPUP:,} so'm*\n\n"
            f"Qancha so'm to'lamoqchisiz? (raqam kiriting, masalan: 10000)",
            parse_mode="Markdown"
        )
    _set_topup_state(context, update.effective_user.id, 'amount')
    _set_topup_amount(context, update.effective_user.id, 0)
    logger.info(f"topup_start: user {update.effective_user.id} topup boshladi")
    return TOPUP_AMOUNT


async def topup_message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Routes text messages based on the user's top-up state.
    
    Returns:
        int or None: TOPUP_AMOUNT, TOPUP_SCREENSHOT yoki None (topup aktiv emas)
    """
    # This router now only handles TEXT messages during the top-up flow.
    # Photo messages are handled by the global topup_get_screenshot handler.
    topup_state = _get_topup_state(context, update.effective_user.id)
    if topup_state == 'amount':
        await _topup_get_amount(update, context)
        return TOPUP_SCREENSHOT
    # If the user sends text when we expect a screenshot, we remind them.
    elif topup_state == 'screenshot':
        await update.message.reply_text("⚠️ Iltimos, to'lov cheki rasmini (screenshot) yuboring:")
        return TOPUP_SCREENSHOT
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
        f"💳 To'lov miqdori: *{amount:,} so'm*\n\n"
        f"Karta raqami: `{CARD_NUMBER}`\n\n"
        f"Ushbu kartaga *{amount:,} so'm* o'tkazing va chek (screenshot) rasmini yuboring:",
        parse_mode="Markdown"
    )
    logger.info(f"_topup_get_amount: user {update.effective_user.id} miqdor={amount}")


async def topup_get_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles photo submissions globally. Only processes if the user is in 'screenshot' state."""
    user_id = update.effective_user.id
    topup_state = _get_topup_state(context, user_id)

    # Only process if the user is expecting to send a screenshot
    if topup_state != 'screenshot':
        # Not in a topup flow — ignore silently to avoid interfering with other flows.
        logger.info(f"Photo from user {user_id} ignored, topup_state is '{topup_state}'.")
        return

    if not update.message.photo:
        await update.message.reply_text("⚠️ Iltimos, to'lov cheki rasmini (screenshot) yuboring:")
        return
    user = update.effective_user
    amount = _get_topup_amount(context, user.id)
    photo_id = update.message.photo[-1].file_id
    tx_id = await asyncio.to_thread(db.create_topup_request, user.id, amount, photo_id)
    full_name = (user.full_name or '').strip() or 'Nomsiz'
    username_str = f"@{user.username}" if user.username else "username yo'q"
    admin_notified = False
    for admin_id in ADMIN_IDS:
        try:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"admin_approve_{tx_id}"),
                 InlineKeyboardButton("❌ Rad etish",  callback_data=f"admin_reject_{tx_id}")]
            ])
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=photo_id,
                caption=(
                    f"💳 *Yangi to'lov so'rovi* #{tx_id}\n\n"
                    f"👤 Ism: {full_name}\n"
                    f"📱 {username_str} | ID: `{user.id}`\n"
                    f"💰 Miqdor: *{amount:,} so'm*\n\n"
                    f"Tasdiqlash yoki rad etish uchun tugmani bosing:"
                ),
                reply_markup=kb,
                parse_mode="Markdown"
            )
            admin_notified = True
            logger.info(f"Admin {admin_id} ga to'lov #{tx_id} yuborildi (user: {user.id}, {amount} so'm)")
        except Exception as e:
            logger.error(f"Admin {admin_id} ga xabar yuborishda xatolik: {e}")
    if not admin_notified:
        logger.error(f"Hech bir adminga to'lov #{tx_id} yuborilmadi!")
    _set_topup_state(context, user.id, None)
    _set_topup_amount(context, user.id, 0)
    await update.message.reply_text(
        f"✅ *Chekingiz qabul qilindi!*\n\n"
        f"💰 So'ralgan miqdor: *{amount:,} so'm*\n"
        f"🔢 So'rov raqami: #{tx_id}\n\n"
        f"Admin tekshirib, balansni tez orada to'ldiradi. ⏳",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )







async def admin_approve_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin to'lovni tasdiqlaydi."""
    query = update.callback_query
    await query.answer()
    if update.effective_user.id not in ADMIN_IDS:
        await query.answer("Ruxsat yo'q!", show_alert=True)
        return
    tx_id = int(query.data.split("_")[2])
    tx = await asyncio.to_thread(db.approve_topup, tx_id)
    if not tx:
        await query.edit_message_caption(caption=query.message.caption + "\n\n⚠️ Allaqachon qayta ishlangan.")
        return
    await query.edit_message_caption(
        caption=query.message.caption + f"\n\n✅ *TASDIQLANDI* — {tx['amount']:,} so'm qo'shildi",
        parse_mode="Markdown"
    )
    try:
        await context.bot.send_message(
            chat_id=tx['user_id'],
            text=f"✅ To'lovingiz tasdiqlandi!\n💰 Balansingizga *{tx['amount']:,} so'm* qo'shildi.",
            parse_mode="Markdown"
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
    tx_id = int(query.data.split("_")[2])
    tx = await asyncio.to_thread(db.reject_topup, tx_id)
    if not tx:
        await query.edit_message_caption(caption=query.message.caption + "\n\n⚠️ Allaqachon qayta ishlangan.")
        return
    await query.edit_message_caption(
        caption=query.message.caption + "\n\n❌ *RAD ETILDI*",
        parse_mode="Markdown"
    )
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

    elif data == "adm_users":
        users = await asyncio.to_thread(db.get_all_users, limit=10)
        lines = []
        for u in users:
            name = u['full_name'] or u['username'] or str(u['user_id'])
            lines.append(f"• {name} | 💰 {u['balance']:,} so'm")
        text = "👥 *So'nggi 10 foydalanuvchi:*\n\n" + "\n".join(lines) if lines else "Foydalanuvchilar yo'q."
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Orqaga", callback_data="adm_back")]])
        await query.edit_message_text(text, reply_markup=back_kb, parse_mode="Markdown")

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
        await query.edit_message_text(
            "💰 *Balans qo'shish*\n\nFormat: `user_id miqdor`\nMasalan: `123456789 10000`\n\n/admin_addbal buyrug'ini yuboring.",
            parse_mode="Markdown"
        )

    elif data == "adm_broadcast":
        await query.edit_message_text(
            "📢 *Xabar yuborish*\n\n/broadcast buyrug'ini yuboring.\nFormat: `/broadcast Xabar matni`",
            parse_mode="Markdown"
        )

    elif data == "adm_back":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Statistika",           callback_data="adm_stats"),
             InlineKeyboardButton("👥 Foydalanuvchilar",    callback_data="adm_users")],
            [InlineKeyboardButton("⏳ Kutayotgan to'lovlar", callback_data="adm_pending"),
             InlineKeyboardButton("💰 Balans qo'shish",     callback_data="adm_add_bal")],
            [InlineKeyboardButton("📢 Xabar yuborish",      callback_data="adm_broadcast")],
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
    await asyncio.to_thread(db.add_balance, target_id, amount)
    await asyncio.to_thread(db.log_deduction, target_id, amount, note="Admin qo'lda qo'shdi")
    await update.message.reply_text(f"✅ {target_id} ga {amount:,} so'm qo'shildi.")
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"✅ Balansingizga *{amount:,} so'm* qo'shildi (admin tomonidan).",
            parse_mode="Markdown"
        )
    except Exception:
        pass


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
        f"Ism: {u['full_name'] or 'Nomsiz'}\n"
        f"Username: @{u['username'] or 'yoq'}\n"
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

    application = Application.builder().token(token).build()

    # ── Slayd yaratish ──
    slayd_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex(r"^🪄 Slayd yaratish ✨$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^📄 Mustaqil ish ✨$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^📚 Referat ✨$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^📁 Loyiha ishi ✨$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^📊 Infografika ✨$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^💰 Balans & Referral 🔗$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^🤖 AI yordamchi 💬$"), handle_main_menu_selection),
            MessageHandler(filters.Regex(r"^📰 Maqola ✨$"), handle_main_menu_selection),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu_selection),
            CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
        ],
        per_message=False,
        states={
            LANGUAGE_SELECTION: [
                CallbackQueryHandler(get_language, pattern=r"^lang_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.Regex(r"^🪄 Slayd yaratish ✨$"), handle_main_menu_selection),
                MessageHandler(filters.Regex(r"^📄 Mustaqil ish ✨$"), handle_main_menu_selection),
                MessageHandler(filters.Regex(r"^📚 Referat ✨$"), handle_main_menu_selection),
                MessageHandler(filters.Regex(r"^📁 Loyiha ishi ✨$"), handle_main_menu_selection),
                MessageHandler(filters.Regex(r"^📊 Infografika ✨$"), handle_main_menu_selection),
                MessageHandler(filters.Regex(r"^💰 Balans & Referral 🔗$"), handle_main_menu_selection),
                MessageHandler(filters.Regex(r"^🤖 AI yordamchi 💬$"), handle_main_menu_selection),
                # Boshqa barcha tugmalar (ishga tushirilmagan xizmatlar ham)
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu_selection),
            ],
            TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_topic),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            NAME_SURNAME: [
                CallbackQueryHandler(get_name_surname, pattern=r"^skip_name_surname$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_name_surname),
            ],
            SLIDE_COUNT: [
                CallbackQueryHandler(get_slide_count, pattern=r"^slide_count_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            PLAN_CONFIRMATION: [
                CallbackQueryHandler(plan_confirmation, pattern=r"^plan_confirm_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            # ── Mustaqil ish holatlari ──
            MI_LANGUAGE: [
                CallbackQueryHandler(mi_get_language, pattern=r"^mi_lang_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            MI_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, mi_get_topic),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            MI_NAME_SURNAME: [
                CallbackQueryHandler(mi_get_name_surname, pattern=r"^mi_skip_name$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, mi_get_name_surname),
            ],
            MI_PAGE_COUNT: [
                CallbackQueryHandler(mi_get_page_count, pattern=r"^mi_pages_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            MI_UNIVERSITY: [
                CallbackQueryHandler(mi_get_university, pattern=r"^mi_skip_university$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, mi_get_university),
            ],
            MI_TEACHER: [
                CallbackQueryHandler(mi_get_teacher, pattern=r"^mi_skip_teacher$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, mi_get_teacher),
            ],
            # ── Loyiha ishi holatlari ──
            LI_LANGUAGE: [
                CallbackQueryHandler(li_get_language, pattern=r"^li_lang_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            LI_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, li_get_topic),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            LI_NAME_SURNAME: [
                CallbackQueryHandler(li_get_name_surname, pattern=r"^li_skip_name$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, li_get_name_surname),
            ],
            LI_PAGE_COUNT: [
                CallbackQueryHandler(li_get_page_count, pattern=r"^li_pages_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            LI_UNIVERSITY: [
                CallbackQueryHandler(li_get_university, pattern=r"^li_skip_university$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, li_get_university),
            ],
            LI_SUBJECT: [
                CallbackQueryHandler(li_get_subject, pattern=r"^li_skip_subject$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, li_get_subject),
            ],
            LI_TEACHER: [
                CallbackQueryHandler(li_get_teacher, pattern=r"^li_skip_teacher$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, li_get_teacher),
            ],
            # ── Referat holatlari ──
            RF_LANGUAGE: [
                CallbackQueryHandler(rf_get_language, pattern=r"^rf_lang_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            RF_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, rf_get_topic),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            RF_NAME_SURNAME: [
                CallbackQueryHandler(rf_get_name_surname, pattern=r"^rf_skip_name$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, rf_get_name_surname),
            ],
            RF_PAGE_COUNT: [
                CallbackQueryHandler(rf_get_page_count, pattern=r"^rf_pages_"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            RF_UNIVERSITY: [
                CallbackQueryHandler(rf_get_university, pattern=r"^rf_skip_university$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, rf_get_university),
            ],
            RF_TEACHER: [
                CallbackQueryHandler(rf_get_teacher, pattern=r"^rf_skip_teacher$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, rf_get_teacher),
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
                MessageHandler(filters.TEXT & ~filters.COMMAND, ig_get_topic),
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
                MessageHandler(filters.TEXT & ~filters.COMMAND, mq_get_topic),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            MQ_NAME_SURNAME: [
                CallbackQueryHandler(mq_get_name_surname, pattern=r"^mq_skip_name$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, mq_get_name_surname),
            ],
            MQ_UNIVERSITY: [
                CallbackQueryHandler(mq_get_university, pattern=r"^mq_skip_university$"),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, mq_get_university),
            ],
            # ── Balans to'ldirish holatlari ──
            TOPUP_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, topup_message_router),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
            TOPUP_SCREENSHOT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, topup_message_router),
                CallbackQueryHandler(topup_start, pattern=r"^topup_start$"),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("cancel", cancel),
        ],
    )

    application.add_handler(slayd_handler)

    # Admin handlerlari
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("admin_addbal", admin_add_balance))
    application.add_handler(CommandHandler("broadcast", admin_broadcast))
    application.add_handler(CommandHandler("user_info", admin_user_info))

    # Admin callback handlerlari
    application.add_handler(CallbackQueryHandler(admin_callback,      pattern=r"^adm_"))
    application.add_handler(CallbackQueryHandler(admin_approve_topup, pattern=r"^admin_approve_"))
    application.add_handler(CallbackQueryHandler(admin_reject_topup,  pattern=r"^admin_reject_"))

    # Balans & Referral menyu handleri
    application.add_handler(MessageHandler(
        filters.Regex(r"^💰 Balans & Referral 🔗$"),
        handle_main_menu_selection
    ))

    # Global handler for photo submissions for top-up
    application.add_handler(MessageHandler(filters.PHOTO, topup_get_screenshot), group=-1)

    logger.info("Bot ishga tushmoqda (polling rejimi)...")
    application.run_polling()


if __name__ == "__main__":
    main()
