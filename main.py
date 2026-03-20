import logging
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes, ConversationHandler
from utils import generate_presentation, generate_slide_content

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# State management for conversations
TOPIC, SLIDE_COUNT, TEMPLATE_SELECTION, LANGUAGE_SELECTION, NAME_SURNAME, PLAN_CONFIRMATION = range(6)

# --- Language Mapping ---
LANGUAGE_NAMES = {
    "uz": "Oʻzbek tili",
    "en": "Ingliz tili",
    "ru": "Rus tili",
    "ko": "Kores tili",
    "zh": "Xitoy tili",
    "de": "Nemis tili",
    "kaa": "Qoraqalpoq tili",
    "tk": "Turkman tili",
    "tg": "Tojik tili"
}

# --- Keyboards ---

def get_main_menu_keyboard():
    keyboard = [
        [KeyboardButton("🪄 Slayd yaratish ✨"), KeyboardButton("📄 Mustaqil ish ✨")],
        [KeyboardButton("🤖 AI yordamchi 💬"), KeyboardButton("📰 Maqola ✨")],
        [KeyboardButton("🎓 Kurs ishi 📝"), KeyboardButton("📚 Referat ✨")],
        [KeyboardButton("📜 Tezis ✨"), KeyboardButton("💡 Glossary ✨")],
        [KeyboardButton("🧩 Krossvord ✨"), KeyboardButton("🔠 Test tuzish")],
        [KeyboardButton("💰 Balans & Referral 🔗")],
        [KeyboardButton("🖼️ Rasm yaratish"), KeyboardButton("🎬 Video yaratish")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_slide_count_keyboard():
    keyboard = [
        [InlineKeyboardButton("5", callback_data="slide_count_5"), InlineKeyboardButton("10", callback_data="slide_count_10")],
        [InlineKeyboardButton("15", callback_data="slide_count_15"), InlineKeyboardButton("20", callback_data="slide_count_20")],
        [InlineKeyboardButton("25", callback_data="slide_count_25"), InlineKeyboardButton("30", callback_data="slide_count_30")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_template_selection_keyboard():
    keyboard = [
        [InlineKeyboardButton("1", callback_data="tmpl_1"), InlineKeyboardButton("2", callback_data="tmpl_2"), InlineKeyboardButton("3", callback_data="tmpl_3"), InlineKeyboardButton("4", callback_data="tmpl_4"), InlineKeyboardButton("5", callback_data="tmpl_5")],
        [InlineKeyboardButton("6", callback_data="tmpl_6"), InlineKeyboardButton("7", callback_data="tmpl_7"), InlineKeyboardButton("8", callback_data="tmpl_8"), InlineKeyboardButton("9", callback_data="tmpl_9"), InlineKeyboardButton("10", callback_data="tmpl_10")],
        [InlineKeyboardButton("11", callback_data="tmpl_11"), InlineKeyboardButton("12", callback_data="tmpl_12")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_language_selection_keyboard():
    keyboard = [
        [InlineKeyboardButton("Oʻzbek tili", callback_data="lang_uz"), InlineKeyboardButton("Ingliz tili", callback_data="lang_en")],
        [InlineKeyboardButton("Rus tili", callback_data="lang_ru"), InlineKeyboardButton("Kores tili", callback_data="lang_ko")],
        [InlineKeyboardButton("Xitoy tili", callback_data="lang_zh"), InlineKeyboardButton("Nemis tili", callback_data="lang_de")],
        [InlineKeyboardButton("Qoraqalpoq tili", callback_data="lang_kaa"), InlineKeyboardButton("Turkman tili", callback_data="lang_tk")],
        [InlineKeyboardButton("Tojik tili", callback_data="lang_tg")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_name_surname_skip_keyboard():
    keyboard = [
        [InlineKeyboardButton("Ism kiritish shart emas", callback_data="skip_name_surname")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    logger.info(f"User {user.id} started the bot.")
    context.user_data.clear()
    await update.message.reply_html(
        f"Assalomu alaykum, {user.mention_html()}! 👋\n\nMen sizning oʻquv ishlaringizda yordam beruvchi aqlli botman. Quyidagi xizmatlardan foydalanishingiz mumkin:",
        reply_markup=get_main_menu_keyboard()
    )
    return ConversationHandler.END

async def handle_main_menu_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text

    if text == "🪄 Slayd yaratish ✨":
        await update.message.reply_text(
            "Endi prezentatsiya tilini tanlang:",
            reply_markup=get_language_selection_keyboard()
        )
        return LANGUAGE_SELECTION
    else:
        await update.message.reply_text(f"'{text}' xizmati tez kunda ishga tushadi! Hozircha faqat 'Slayd yaratish' bo'limi ishlamoqda.", reply_markup=get_main_menu_keyboard())
        return ConversationHandler.END

async def get_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    logger.info(f"get_language: Callback data received for language selection: {query.data}")
    try:
        language_code = query.data.split("_")[1]
        context.user_data["language"] = language_code
        full_language_name = LANGUAGE_NAMES.get(language_code, language_code)
        logger.info(f"get_language: Language code extracted: {language_code}")
    except (IndexError, ValueError) as e:
        logger.error(f"get_language: Error parsing language code from callback data '{query.data}': {e}")
        await context.bot.send_message(chat_id=query.message.chat_id, text="Til tanlashda xatolik yuz berdi. Iltimos, qayta urinib koʻring.")
        return LANGUAGE_SELECTION

    await context.bot.send_message(chat_id=query.message.chat_id, text=f"Siz {full_language_name} tilini tanladingiz. Endi prezentatsiya uchun mavzuni kiriting:")
    return TOPIC

async def get_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["topic"] = update.message.text
    await update.message.reply_text(
        "Ajoyib! Endi ism va familiyangizni kiriting (masalan: Ali Valiyev):",
        reply_markup=get_name_surname_skip_keyboard()
    )
    return NAME_SURNAME

async def get_name_surname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        if query.data == "skip_name_surname":
            context.user_data["name_surname"] = ""
            await query.edit_message_text(text="Ism kiritish shart emas deb belgilandi.")
            chat_id = query.message.chat_id
        else:
            await query.edit_message_text(text="Xatolik yuz berdi. Iltimos, qayta urinib koʻring.")
            return NAME_SURNAME
    else:
        context.user_data["name_surname"] = update.message.text
        await update.message.reply_text(f"Ism va familiya qabul qilindi: {update.message.text}")
        chat_id = update.effective_chat.id

    await context.bot.send_message(
        chat_id=chat_id,
        text="Rahmat! Endi nechta slayd kerakligini tanlang:",
        reply_markup=get_slide_count_keyboard()
    )
    return SLIDE_COUNT

async def get_slide_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    logger.info(f"get_slide_count: Callback data received: {query.data}")
    try:
        slide_count = int(query.data.split("_")[2])
        context.user_data["slide_count"] = slide_count
        logger.info(f"get_slide_count: Slide count extracted: {slide_count}")
    except (IndexError, ValueError) as e:
        logger.error(f"get_slide_count: Error parsing slide count from callback data '{query.data}': {e}")
        await query.edit_message_text(text="Slayd sonini tanlashda xatolik yuz berdi. Iltimos, qayta urinib koʻring.")
        return SLIDE_COUNT

    await query.edit_message_text(text=f"Siz {slide_count} ta slayd tanladingiz.")

    # Send template preview images as media group
    try:
        from telegram import InputMediaPhoto
        media_group = []
        for i in range(1, 13):
            preview_path = f"templates/previews/{i}.png"
            if os.path.exists(preview_path):
                media_group.append(InputMediaPhoto(media=open(preview_path, "rb"), caption=f"Shablon {i}"))
        
        if media_group:
            # Send first 10 images as media group (Telegram limit)
            await context.bot.send_media_group(chat_id=query.message.chat_id, media=media_group[:10])
            # Send remaining 2 images separately if needed
            for media in media_group[10:]:
                await context.bot.send_photo(chat_id=query.message.chat_id, photo=media.media, caption=media.caption)
    except Exception as e:
        logger.error(f"Error sending template previews: {e}")
    
    # Send inline keyboard for template selection
    keyboard = [
        [InlineKeyboardButton("1", callback_data="tmpl_1"), InlineKeyboardButton("2", callback_data="tmpl_2"), InlineKeyboardButton("3", callback_data="tmpl_3"), InlineKeyboardButton("4", callback_data="tmpl_4"), InlineKeyboardButton("5", callback_data="tmpl_5")],
        [InlineKeyboardButton("6", callback_data="tmpl_6"), InlineKeyboardButton("7", callback_data="tmpl_7"), InlineKeyboardButton("8", callback_data="tmpl_8"), InlineKeyboardButton("9", callback_data="tmpl_9"), InlineKeyboardButton("10", callback_data="tmpl_10")],
        [InlineKeyboardButton("11", callback_data="tmpl_11"), InlineKeyboardButton("12", callback_data="tmpl_12")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=query.message.chat_id, text="Shablon raqamini tanlang:", reply_markup=reply_markup)

    return TEMPLATE_SELECTION

async def get_template(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    logger.info(f"get_template: Callback data received for template selection: {query.data}")
    try:
        template_id = int(query.data.split("_")[1])
        context.user_data["template_id"] = template_id
        logger.info(f"get_template: Template ID extracted: {template_id}")
    except (IndexError, ValueError) as e:
        logger.error(f"get_template: Error parsing template ID from callback data '{query.data}': {e}")
        await context.bot.send_message(chat_id=query.message.chat_id, text="Shablon tanlashda xatolik yuz berdi. Iltimos, qayta urinib koʻring.")
        return TEMPLATE_SELECTION

    topic = context.user_data.get("topic")
    slide_count = context.user_data.get("slide_count")
    language = context.user_data.get("language", "uz")

    try:
        plan_content = generate_slide_content(topic, slide_count, slide_count, language, is_plan=True)
        context.user_data["plan"] = plan_content
        plan_text = "\n".join(plan_content.get("content", []))
        keyboard = [
            [InlineKeyboardButton("Ha, ma'qul", callback_data="plan_confirm_yes")],
            [InlineKeyboardButton("Yo'q, qayta tuz", callback_data="plan_confirm_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=query.message.chat_id, text=f"**Reja:**\n{plan_text}\n\nShu reja ma'qulmi?", reply_markup=reply_markup, parse_mode="Markdown")
        return PLAN_CONFIRMATION
    except Exception as e:
        logger.error(f"get_template: Error generating plan: {e}")
        await context.bot.send_message(chat_id=query.message.chat_id, text="Reja tuzishda xatolik yuz berdi. Iltimos, qayta urinib koʻring.")
        return ConversationHandler.END

async def plan_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "plan_confirm_yes":
        return await generate_final_presentation(update, context)
    elif query.data == "plan_confirm_no":
        return await get_template(update, context)

async def generate_final_presentation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    topic = context.user_data.get("topic")
    slide_count = context.user_data.get("slide_count")
    template_id = context.user_data.get("template_id")
    template_path = f"templates/shablonlar/{template_id}.pptx"
    language = context.user_data.get("language", "uz")
    name_surname = context.user_data.get("name_surname", "")
    plan = context.user_data.get("plan")

    try:
        output_path = generate_presentation(topic, slide_count, template_path, language, name_surname, plan)
        with open(output_path, "rb") as doc_file:
            await context.bot.send_document(chat_id=chat_id, document=doc_file, filename=f"{topic}.pptx", caption="Prezentatsiyangiz tayyor!")
        if os.path.exists(output_path):
            os.remove(output_path)
    except Exception as e:
        logger.error(f"generate_final_presentation: Error in generate_presentation call: {e}")
        await context.bot.send_message(chat_id=chat_id, text="Xatolik yuz berdi. Iltimos, boshqa shablon bilan yoki boshqa mavzuda qayta urinib koʻring.")

    await context.bot.send_message(chat_id=chat_id, text="Yana yordamim kerakmi?", reply_markup=get_main_menu_keyboard())
    return ConversationHandler.END


def main() -> None:
    """Start the bot."""
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("BOT_TOKEN not found in environment variables!")
        return

    application = Application.builder().token(token).build()

    # Get webhook URL and port from environment variables
    webhook_url = os.getenv("WEBHOOK_URL")
    port = int(os.getenv("PORT", 8080))

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^🪄 Slayd yaratish ✨$"), handle_main_menu_selection)
        ],
        states={
            LANGUAGE_SELECTION: [
                CallbackQueryHandler(get_language, pattern="^lang_"),
            ],
            TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_topic)],
            NAME_SURNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_name_surname),
                CallbackQueryHandler(get_name_surname, pattern="^skip_name_surname$")
            ],
            SLIDE_COUNT: [
                CallbackQueryHandler(get_slide_count, pattern="^slide_count_"),
            ],
            TEMPLATE_SELECTION: [
                CallbackQueryHandler(get_template, pattern="^tmpl_"),
            ],
            PLAN_CONFIRMATION: [
                CallbackQueryHandler(plan_confirmation, pattern="^plan_confirm_")
            ]
        },
        fallbacks=[CommandHandler("start", start)],
    )

    application.add_handler(conv_handler)

    logger.info(f"WEBHOOK_URL: {webhook_url}")
    logger.info(f"PORT: {port}")
    logger.info("Bot is running...")
    if not webhook_url:
        logger.error("WEBHOOK_URL not found in environment variables!")
        return

    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=token,
        webhook_url=webhook_url
    )


if __name__ == "__main__":
    main()
