import logging
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes, ConversationHandler
from utils import generate_presentation, generate_slide_content, generate_template_1_presentation
from pptx import Presentation

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# State management for conversations
TOPIC, SLIDE_COUNT, LANGUAGE_SELECTION, NAME_SURNAME, PLAN_CONFIRMATION = range(5)

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
        [InlineKeyboardButton("5", callback_data="slide_count_5"), InlineKeyboardButton("10", callback_data="slide_count_10"), InlineKeyboardButton("15", callback_data="slide_count_15")],
        [InlineKeyboardButton("20", callback_data="slide_count_20"), InlineKeyboardButton("25", callback_data="slide_count_25"), InlineKeyboardButton("30", callback_data="slide_count_30")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_language_keyboard():
    keyboard = [
        [InlineKeyboardButton("Oʻzbek tili", callback_data="lang_uz"), InlineKeyboardButton("Ingliz tili", callback_data="lang_en")],
        [InlineKeyboardButton("Rus tili", callback_data="lang_ru"), InlineKeyboardButton("Kores tili", callback_data="lang_ko")],
        [InlineKeyboardButton("Xitoy tili", callback_data="lang_zh"), InlineKeyboardButton("Nemis tili", callback_data="lang_de")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_plan_confirmation_keyboard():
    keyboard = [
        [InlineKeyboardButton("✅ Tasdiqlash", callback_data="plan_confirm_yes"), InlineKeyboardButton("❌ Qayta tuzish", callback_data="plan_confirm_no")],
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the bot and show main menu."""
    await update.message.reply_text(
        "Assalomu alaykum! 👋\n\nBotga xush kelibsiz! Quyidagi xizmatlardan birini tanlang:",
        reply_markup=get_main_menu_keyboard()
    )
    return LANGUAGE_SELECTION

async def handle_main_menu_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle main menu selection."""
    text = update.message.text
    
    if text == "🪄 Slayd yaratish ✨":
        await update.message.reply_text(
            "Qaysi tilda slayd yaratmoqchisiz?",
            reply_markup=get_language_keyboard()
        )
        return LANGUAGE_SELECTION
    else:
        await update.message.reply_text(f"'{text}' xizmati tez kunda ishga tushadi! Hozircha faqat 'Slayd yaratish' bo'limi ishlamoqda.", reply_markup=get_main_menu_keyboard())
        return LANGUAGE_SELECTION

async def get_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get language selection."""
    query = update.callback_query
    await query.answer()
    
    language_code = query.data.split("_")[1]
    context.user_data["language"] = language_code
    
    await query.edit_message_text(
        text=f"Tili: {LANGUAGE_NAMES.get(language_code, 'Oʻzbek tili')}\n\nEndi mavzuni kiriting:"
    )
    return TOPIC

async def get_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get topic from user."""
    topic = update.message.text
    context.user_data["topic"] = topic
    
    skip_button = InlineKeyboardMarkup([[InlineKeyboardButton("O'tkazib yuborish", callback_data="skip_name_surname")]])
    await update.message.reply_text(
        f"Mavzu: {topic}\n\nEndi ism va familiyangizni kiriting (yoki o'tkazib yuborish):",
        reply_markup=skip_button
    )
    return NAME_SURNAME

async def get_name_surname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get name and surname from user."""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        context.user_data["name_surname"] = "Noma'lum"
        await query.edit_message_text(text="Slayd sonini tanlang:", reply_markup=get_slide_count_keyboard())
    else:
        name_surname = update.message.text
        context.user_data["name_surname"] = name_surname
        await update.message.reply_text("Slayd sonini tanlang:", reply_markup=get_slide_count_keyboard())
    
    return SLIDE_COUNT

async def get_slide_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get slide count from user."""
    query = update.callback_query
    await query.answer()
    
    slide_count = int(query.data.split("_")[2])
    context.user_data["slide_count"] = slide_count
    
    await query.edit_message_text(text=f"Slaydlar soni: {slide_count}\n\n📝 Reja tuzilmoqda...")
    
    # Generate plan
    topic = context.user_data.get("topic", "")
    language = context.user_data.get("language", "uz")
    
    plan = generate_slide_content(topic, language, "plan", slide_count)
    context.user_data["plan"] = plan
    
    # Show plan for confirmation
    plan_text = plan.get("content", "Reja tayyorlanmadi") if plan else "Reja tayyorlanmadi"
    
    await query.edit_message_text(
        text=f"📋 **Reja:**\n\n{plan_text}\n\nBu rejani tasdiqlaysizmi?",
        reply_markup=get_plan_confirmation_keyboard(),
        parse_mode="Markdown"
    )
    
    return PLAN_CONFIRMATION

async def plan_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirm or reject the plan."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "plan_confirm_yes":
        await query.edit_message_text(text="✅ Reja tasdiqlandi!\n\n🔄 Prezentatsiya tayyorlanmoqda...")
        
        # Generate presentation
        chat_id = query.message.chat_id
        topic = context.user_data.get("topic", "")
        language = context.user_data.get("language", "uz")
        slide_count = context.user_data.get("slide_count", 5)
        name_surname = context.user_data.get("name_surname", "Noma'lum")
        plan = context.user_data.get("plan", {})
        
        try:
            # Generate presentation using the custom template function
            presentation_bytes = generate_template_1_presentation(
                topic=topic,
                language=language,
                slide_count=slide_count,
                name_surname=name_surname,
                plan=plan
            )
            
            # Send presentation to user
            await context.bot.send_document(
                chat_id=chat_id,
                document=presentation_bytes,
                filename=f"{topic[:20]}_presentation.pptx"
            )
            
            await context.bot.send_message(chat_id=chat_id, text="✅ Prezentatsiya tayyor! Yana biror narsa kerakmi?", reply_markup=get_main_menu_keyboard())
        except Exception as e:
            logger.error(f"Error generating presentation: {e}")
            await context.bot.send_message(chat_id=chat_id, text=f"Prezentatsiya yaratishda xatolik yuz berdi: {str(e)}", reply_markup=get_main_menu_keyboard())
        
        return ConversationHandler.END
    else:
        await query.edit_message_text(text="Reja qayta tuzilmoqda...")
        topic = context.user_data.get("topic", "")
        language = context.user_data.get("language", "uz")
        slide_count = context.user_data.get("slide_count", 5)
        
        plan = generate_slide_content(topic, language, "plan", slide_count)
        context.user_data["plan"] = plan
        
        plan_text = plan.get("content", "Reja tayyorlanmadi") if plan else "Reja tayyorlanmadi"
        
        await query.edit_message_text(
            text=f"📋 **Reja:**\n\n{plan_text}\n\nBu rejani tasdiqlaysizmi?",
            reply_markup=get_plan_confirmation_keyboard(),
            parse_mode="Markdown"
        )
        
        return PLAN_CONFIRMATION

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    chat_id = update.message.chat_id
    await context.bot.send_message(chat_id=chat_id, text="Yana yordamim kerakmi?", reply_markup=get_main_menu_keyboard())
    return ConversationHandler.END


def main() -> None:
    """Start the bot using polling mode."""
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("BOT_TOKEN not found in environment variables!")
        return

    application = Application.builder().token(token).build()

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
            PLAN_CONFIRMATION: [
                CallbackQueryHandler(plan_confirmation, pattern="^plan_confirm_")
            ]
        },
        fallbacks=[CommandHandler("start", start)],
    )

    application.add_handler(conv_handler)

    logger.info("Bot is starting in polling mode...")
    application.run_polling()


if __name__ == "__main__":
    main()
