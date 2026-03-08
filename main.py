import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes, ConversationHandler
from utils import generate_presentation

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# State management for conversations
TOPIC, SLIDE_COUNT, TEMPLATE_SELECTION = range(3)

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
        [InlineKeyboardButton("6", callback_data="tmpl_6"), InlineKeyboardButton("7", callback_data="tmpl_7"), InlineKeyboardButton("8", callback_data="tmpl_8"), InlineKeyboardButton("9", callback_data="tmpl_9"), InlineKeyboardButton("10", callback_data="tmpl_10")]
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
        await update.message.reply_text("Prezentatsiya uchun mavzuni kiriting:")
        return TOPIC
    else:
        await update.message.reply_text(f"'{text}' xizmati tez kunda ishga tushadi! Hozircha faqat 'Slayd yaratish' bo'limi ishlamoqda.", reply_markup=get_main_menu_keyboard())
        return ConversationHandler.END

async def get_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["topic"] = update.message.text
    await update.message.reply_text(
        "Ajoyib! Endi nechta slayd kerakligini tanlang:",
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
        return SLIDE_COUNT # Stay in the same state to allow re-selection

    await query.edit_message_text(text=f"Siz {slide_count} ta slayd tanladingiz.")

    try:
        all_previews_path = "templates/previews/all_previews.png"
        if os.path.exists(all_previews_path):
            with open(all_previews_path, "rb") as photo_file:
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=photo_file,
                    caption="Endi quyidagi shablonlardan birini tanlang:",
                    reply_markup=get_template_selection_keyboard()
                )
        else:
            await query.message.reply_text("Shablon rasmlari topilmadi. Quyidagi raqamlardan birini tanlang:", reply_markup=get_template_selection_keyboard())
    except Exception as e:
        logger.error(f"get_slide_count: Error sending photo or template selection: {e}")
        await query.message.reply_text("Shablon rasmlari topilmadi. Quyidagi raqamlardan birini tanlang:", reply_markup=get_template_selection_keyboard())
    
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
        return TEMPLATE_SELECTION # Stay in the same state to allow re-selection

    # Changed from edit_message_text to send_message to avoid 400 Bad Request after sending photo
    await context.bot.send_message(chat_id=query.message.chat_id, text=f"Shablon {template_id} tanlandi. Prezentatsiya tayyorlanmoqda, bu bir necha daqiqa vaqt olishi mumkin...")

    topic = context.user_data.get("topic")
    slide_count = context.user_data.get("slide_count")
    template_path = f"templates/shablonlar/{template_id}.pptx"

    try:
        output_path = generate_presentation(topic, slide_count, template_path)
        with open(output_path, "rb") as doc_file:
            await context.bot.send_document(chat_id=query.message.chat_id, document=doc_file, filename=f"{topic}.pptx", caption="Prezentatsiyangiz tayyor!")
        os.remove(output_path)
    except Exception as e:
        logger.error(f"get_template: Error in generate_presentation call: {e}")
        await context.bot.send_message(chat_id=query.message.chat_id, text="Xatolik yuz berdi. Iltimos, boshqa shablon bilan yoki boshqa mavzuda qayta urinib koʻring.")

    await context.bot.send_message(chat_id=query.message.chat_id, text="Yana yordamim kerakmi?", reply_markup=get_main_menu_keyboard())
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
            TOPIC: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_topic)],
            SLIDE_COUNT: [
                CallbackQueryHandler(get_slide_count, pattern="^slide_count_"),
                MessageHandler(filters.ALL, lambda u, c: ConversationHandler.END) # Fallback for unexpected messages
            ],
            TEMPLATE_SELECTION: [
                CallbackQueryHandler(get_template, pattern="^tmpl_"),
                MessageHandler(filters.ALL, lambda u, c: ConversationHandler.END) # Fallback for unexpected messages
            ]
        },
        fallbacks=[CommandHandler("start", start)],
    )

    application.add_handler(conv_handler)

    logger.info("Bot is running...")
    if webhook_url:
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=token,
            webhook_url=f"{webhook_url}/{token}"
        )
        logger.info(f"Bot running with webhook at {webhook_url}/{token}")
    else:
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
        logger.info("Bot running with polling")

if __name__ == "__main__":
    main()
