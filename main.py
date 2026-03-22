import json
import logging
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes, ConversationHandler
from utils import (
    generate_presentation,
    generate_template_1_presentation,
    generate_plan_with_titles,
    generate_all_content,
)
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
# Suhbat holatlari
# ─────────────────────────────────────────────
(
    LANGUAGE_SELECTION,  # 0 — til tanlash
    TOPIC,               # 1 — mavzu kiritish
    NAME_SURNAME,        # 2 — ism-familiya
    SLIDE_COUNT,         # 3 — slayd soni
    PLAN_CONFIRMATION,   # 4 — reja tasdiqlash
) = range(5)

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
    plan_lines = "\n".join(plan_items)
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
# Handlerlar
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
        await update.message.reply_text(
            "Qaysi tilda slayd yaratmoqchisiz?",
            reply_markup=get_language_keyboard()
        )
        return LANGUAGE_SELECTION
    else:
        await update.message.reply_text(
            f"'{text}' xizmati tez kunda ishga tushadi!\nHozircha faqat 'Slayd yaratish' bo'limi ishlamoqda.",
            reply_markup=get_main_menu_keyboard()
        )
        return LANGUAGE_SELECTION


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
    """
    Slayd sonini qabul qiladi va 1-BOSQICH ni ishga tushiradi:
    GPT dan reja + sarlavhalar so'raladi, foydalanuvchiga ko'rsatiladi.
    """
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

    # ── 1-BOSQICH: GPT dan reja + sarlavhalar ──
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
    """
    Reja tasdiqlash yoki qayta tuzish.
    Tasdiqlansa — 2-BOSQICH ishga tushadi: barcha kontent bitta GPT so'rovida yaratiladi.
    """
    query = update.callback_query
    await query.answer()

    topic       = context.user_data.get("topic", "")
    language    = context.user_data.get("language", "uz")
    slide_count = context.user_data.get("slide_count", 5)
    name_surname = context.user_data.get("name_surname", "")
    lang_name   = LANGUAGE_NAMES.get(language, "O'zbek tili")

    if query.data == "plan_confirm_no":
        # Qayta tuzish
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

    # plan dict (fill_slide_2_plan uchun)
    plan_dict = {"title": "Reja", "content": plan_items}

    chat_id = query.message.chat_id

    try:
        # ── 2-BOSQICH: Barcha kontent bitta GPT so'rovida ──
        content_data_list = await asyncio.get_event_loop().run_in_executor(
            None,
            generate_all_content,
            topic, slide_count, language, slide_titles
        )

        if not content_data_list:
            raise ValueError("generate_all_content bo'sh qaytdi")

        # ── Prezentatsiya yaratish ──
        template_path = os.path.join(os.path.dirname(__file__), "templates", "shablonlar", "1.pptx")
        prs = Presentation(template_path)

        presentation_bytes = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: generate_template_1_presentation(
                prs=prs,
                topic=topic,
                requested_slide_count=slide_count,
                language=language,
                name_surname=name_surname,
                plan=plan_dict,
                content_data_list=content_data_list,
            )
        )

        # ── Foydalanuvchiga yuborish ──
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

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex(r"^🪄 Slayd yaratish ✨$"), handle_main_menu_selection),
        ],
        per_message=False,
        states={
            LANGUAGE_SELECTION: [
                CallbackQueryHandler(get_language, pattern=r"^lang_"),
                MessageHandler(filters.Regex(r"^🪄 Slayd yaratish ✨$"), handle_main_menu_selection),
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
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("cancel", cancel),
        ],
    )

    application.add_handler(conv_handler)

    logger.info("Bot ishga tushmoqda (polling rejimi)...")
    application.run_polling()


if __name__ == "__main__":
    main()
