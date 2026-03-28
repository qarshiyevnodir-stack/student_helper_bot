import json
import logging
import os
import asyncio
import random
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
from pptx import Presentation

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

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
        [KeyboardButton("📁 Loyiha ishi ✨")],
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
        [InlineKeyboardButton("10", callback_data="li_pages_10"),
         InlineKeyboardButton("15", callback_data="li_pages_15"),
         InlineKeyboardButton("20", callback_data="li_pages_20")],
        [InlineKeyboardButton("25", callback_data="li_pages_25"),
         InlineKeyboardButton("30", callback_data="li_pages_30")],
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
# Handlerlar — Umumiy
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Botni ishga tushiradi va asosiy menyu ko'rsatadi."""
    context.user_data.clear()
    await update.message.reply_text(
        "Assalomu alaykum! 👋\n\nBotga xush kelibsiz! Quyidagi xizmatlardan birini tanlang:",
        reply_markup=get_main_menu_keyboard()
    )
    return LANGUAGE_SELECTION


async def handle_main_menu_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asosiy menyu tugmasini qayta ishlaydi."""
    text = update.message.text

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

    elif text == "📚 Referat ✨":
        context.user_data.clear()
        context.user_data["mode"] = "referat"
        await update.message.reply_text(
            "📚 *Referat* bo'limiga xush kelibsiz!\n\nQaysi tilda yozmoqchisiz?",
            reply_markup=get_rf_language_keyboard(),
            parse_mode="Markdown"
        )
        return RF_LANGUAGE

    else:
        await update.message.reply_text(
            f"'{text}' xizmati tez kunda ishga tushadi!\nHozircha faqat 'Slayd yaratish' va 'Mustaqil ish' bo'limlari ishlamoqda.",
            reply_markup=get_main_menu_keyboard()
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

        await context.bot.send_document(
            chat_id=chat_id,
            document=presentation_bytes,
            filename=filename,
            caption=f"✅ *{topic}* mavzusidagi taqdimot tayyor!\n📊 {slide_count} ta slayd",
            parse_mode="Markdown"
        )
        await context.bot.send_message(
            chat_id=chat_id,
            text="Yana biror narsa kerakmi?",
            reply_markup=get_main_menu_keyboard()
        )

    except Exception as e:
        logger.error(f"Prezentatsiya yaratishda xatolik: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Prezentatsiya yaratishda xatolik yuz berdi:\n`{str(e)}`\n\nIltimos, qayta urinib ko'ring.",
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
    topic = update.message.text.strip()
    if not topic:
        await update.message.reply_text("Iltimos, mavzuni kiriting:")
        return LI_TOPIC
    context.user_data["li_topic"] = topic
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Shart emas", callback_data="li_skip_name")]])
    await update.message.reply_text(
        f"📌 *Mavzu:* {topic}\n\nIsm-familiyangizni kiriting:\n_(Hujjatda 'Bajardi:' qatorida yoziladi)_",
        reply_markup=keyboard, parse_mode="Markdown"
    )
    return LI_NAME_SURNAME


async def li_get_name_surname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        context.user_data["li_name_surname"] = ""
        await query.edit_message_text(
            text="Hujjat nechta sahifadan iborat bo'lsin?",
            reply_markup=get_li_page_count_keyboard()
        )
    else:
        context.user_data["li_name_surname"] = update.message.text.strip()
        await update.message.reply_text(
            "Hujjat nechta sahifadan iborat bo'lsin?",
            reply_markup=get_li_page_count_keyboard()
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
            f"Universitet yoki muassasa nomini kiriting:\n"
            f"_(Kiritilsa, muqova sahifasiga qo'shiladi)_"
        ),
        reply_markup=keyboard, parse_mode="Markdown"
    )
    return LI_UNIVERSITY


async def li_get_university(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    skip_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Shart emas", callback_data="li_skip_subject")]])
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        context.user_data["li_university"] = ""
        await query.edit_message_text(
            text="Fan nomini kiriting:\n_(Masalan: Biologiya fanidan)_",
            reply_markup=skip_kb, parse_mode="Markdown"
        )
    else:
        context.user_data["li_university"] = update.message.text.strip()
        await update.message.reply_text(
            "Fan nomini kiriting:\n_(Masalan: Biologiya fanidan)_",
            reply_markup=skip_kb, parse_mode="Markdown"
        )
    return LI_SUBJECT


async def li_get_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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

    topic        = context.user_data.get("li_topic", "")
    page_count   = context.user_data.get("li_page_count", 15)
    language     = context.user_data.get("li_language", "uz")
    name_surname = context.user_data.get("li_name_surname", "")
    university   = context.user_data.get("li_university", "")
    subject      = context.user_data.get("li_subject", "")
    teacher      = context.user_data.get("li_teacher", "")

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
        await context.bot.send_document(
            chat_id=chat_id,
            document=doc_bytes,
            filename=filename,
            caption=(
                f"✅ *{topic}* mavzusidagi loyiha ishi tayyor!\n"
                f"📄 Taxminiy {page_count} sahifa"
            ),
            parse_mode="Markdown"
        )
        await context.bot.send_message(
            chat_id=chat_id,
            text="Yana biror narsa kerakmi?",
            reply_markup=get_main_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Loyiha ishi yaratishda xatolik: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Loyiha ishi yaratishda xatolik:\n`{str(e)}`\n\nIltimos, qayta urinib ko'ring.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
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

    topic        = context.user_data.get("rf_topic", "")
    page_count   = context.user_data.get("rf_page_count", 15)
    language     = context.user_data.get("rf_language", "uz")
    name_surname = context.user_data.get("rf_name_surname", "")
    university   = context.user_data.get("rf_university", "")
    teacher      = context.user_data.get("rf_teacher", "")

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
        await context.bot.send_document(
            chat_id=chat_id,
            document=doc_bytes,
            filename=filename,
            caption=(
                f"✅ *{topic}* mavzusidagi referat tayyor!\n"
                f"📄 Taxminiy {page_count} sahifa"
            ),
            parse_mode="Markdown"
        )
        await context.bot.send_message(
            chat_id=chat_id,
            text="Yana biror narsa kerakmi?",
            reply_markup=get_main_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Referat yaratishda xatolik: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Referat yaratishda xatolik:\n`{str(e)}`\n\nIltimos, qayta urinib ko'ring.",
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
    topic         = context.user_data.get("mi_topic", "")
    page_count    = context.user_data.get("mi_page_count", 15)
    language      = context.user_data.get("mi_language", "uz")
    name_surname  = context.user_data.get("mi_name_surname", "")
    university    = context.user_data.get("mi_university", "")
    teacher       = context.user_data.get("mi_teacher", "")

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

        await context.bot.send_document(
            chat_id=chat_id,
            document=doc_bytes,
            filename=filename,
            caption=(
                f"✅ *{topic}* mavzusidagi mustaqil ish tayyor!\n"
                f"📄 Taxminiy {page_count} sahifa"
            ),
            parse_mode="Markdown"
        )
        await context.bot.send_message(
            chat_id=chat_id,
            text="Yana biror narsa kerakmi?",
            reply_markup=get_main_menu_keyboard()
        )

    except Exception as e:
        logger.error(f"Mustaqil ish yaratishda xatolik: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Mustaqil ish yaratishda xatolik:\n`{str(e)}`\n\nIltimos, qayta urinib ko'ring.",
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
        ],
        per_message=False,
        states={
            LANGUAGE_SELECTION: [
                CallbackQueryHandler(get_language, pattern=r"^lang_"),
                MessageHandler(filters.Regex(r"^🪄 Slayd yaratish ✨$"), handle_main_menu_selection),
                MessageHandler(filters.Regex(r"^📄 Mustaqil ish ✨$"), handle_main_menu_selection),
                MessageHandler(filters.Regex(r"^📚 Referat ✨$"), handle_main_menu_selection),
                MessageHandler(filters.Regex(r"^📁 Loyiha ishi ✨$"), handle_main_menu_selection),
            ],
            TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_topic),
            ],
            NAME_SURNAME: [
                CallbackQueryHandler(get_name_surname, pattern=r"^skip_name_surname$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_name_surname),
            ],
            SLIDE_COUNT: [
                CallbackQueryHandler(get_slide_count, pattern=r"^slide_count_"),
            ],
            PLAN_CONFIRMATION: [
                CallbackQueryHandler(plan_confirmation, pattern=r"^plan_confirm_"),
            ],
            # ── Mustaqil ish holatlari ──
            MI_LANGUAGE: [
                CallbackQueryHandler(mi_get_language, pattern=r"^mi_lang_"),
            ],
            MI_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, mi_get_topic),
            ],
            MI_NAME_SURNAME: [
                CallbackQueryHandler(mi_get_name_surname, pattern=r"^mi_skip_name$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, mi_get_name_surname),
            ],
            MI_PAGE_COUNT: [
                CallbackQueryHandler(mi_get_page_count, pattern=r"^mi_pages_"),
            ],
            MI_UNIVERSITY: [
                CallbackQueryHandler(mi_get_university, pattern=r"^mi_skip_university$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, mi_get_university),
            ],
            MI_TEACHER: [
                CallbackQueryHandler(mi_get_teacher, pattern=r"^mi_skip_teacher$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, mi_get_teacher),
            ],
            # ── Loyiha ishi holatlari ──
            LI_LANGUAGE: [
                CallbackQueryHandler(li_get_language, pattern=r"^li_lang_"),
            ],
            LI_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, li_get_topic),
            ],
            LI_NAME_SURNAME: [
                CallbackQueryHandler(li_get_name_surname, pattern=r"^li_skip_name$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, li_get_name_surname),
            ],
            LI_PAGE_COUNT: [
                CallbackQueryHandler(li_get_page_count, pattern=r"^li_pages_"),
            ],
            LI_UNIVERSITY: [
                CallbackQueryHandler(li_get_university, pattern=r"^li_skip_university$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, li_get_university),
            ],
            LI_SUBJECT: [
                CallbackQueryHandler(li_get_subject, pattern=r"^li_skip_subject$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, li_get_subject),
            ],
            LI_TEACHER: [
                CallbackQueryHandler(li_get_teacher, pattern=r"^li_skip_teacher$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, li_get_teacher),
            ],
            # ── Referat holatlari ──
            RF_LANGUAGE: [
                CallbackQueryHandler(rf_get_language, pattern=r"^rf_lang_"),
            ],
            RF_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, rf_get_topic),
            ],
            RF_NAME_SURNAME: [
                CallbackQueryHandler(rf_get_name_surname, pattern=r"^rf_skip_name$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, rf_get_name_surname),
            ],
            RF_PAGE_COUNT: [
                CallbackQueryHandler(rf_get_page_count, pattern=r"^rf_pages_"),
            ],
            RF_UNIVERSITY: [
                CallbackQueryHandler(rf_get_university, pattern=r"^rf_skip_university$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, rf_get_university),
            ],
            RF_TEACHER: [
                CallbackQueryHandler(rf_get_teacher, pattern=r"^rf_skip_teacher$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, rf_get_teacher),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("cancel", cancel),
        ],
    )

    application.add_handler(slayd_handler)

    logger.info("Bot ishga tushmoqda (polling rejimi)...")
    application.run_polling()


if __name__ == "__main__":
    main()
