import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from utils import generate_presentation
from dotenv import load_dotenv

load_dotenv()

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Get Token from Environment Variable
TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Assalomu alaykum! Prezentatsiya yaratish uchun mavzu kiriting:")

async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["topic"] = update.message.text
    
    # Slide count selection with buttons (2 per row layout)
    keyboard = [
        ["5", "10"],
        ["15", "20"],
        ["25", "30"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        f"Sizning mavzuingiz: \'{update.message.text}\'.\nNechta slayd kerak? Quyidagilardan birini tanlang:", 
        reply_markup=reply_markup
    )

async def handle_slide_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text in ["5", "10", "15", "20", "25", "30"]:
        context.user_data["slide_count"] = int(text)
        
        # Path to the single image containing all template previews
        all_previews_path = "templates/previews/all_previews.png"
        
        # Template selection buttons (2 per row)
        keyboard = []
        for i in range(1, 11, 2):
            keyboard.append([
                InlineKeyboardButton(f"Shablon {i}", callback_data=f"tmpl_{i}"),
                InlineKeyboardButton(f"Shablon {i+1}", callback_data=f"tmpl_{i+1}")
            ])
        reply_markup = InlineKeyboardMarkup(keyboard)

        if os.path.exists(all_previews_path):
            with open(all_previews_path, "rb") as photo:
                await update.message.reply_photo(
                    photo=photo, 
                    caption="Yuqoridagi rasmdan o'zingizga yoqqan shablonni ko'rib tanlang:", 
                    reply_markup=reply_markup
                )
        else:
            # Fallback if the combined image is not found
            await update.message.reply_text(
                "Iltimos, o'zingizga yoqqan shablonni tanlang:", 
                reply_markup=reply_markup
            )
    else:
        # This handles cases where user input is unexpected
        pass

async def handle_template_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    template_id = query.data.split("_")[1]
    template_file = f"templates/shablonlar/{template_id}.pptx"
    topic = context.user_data.get("topic")
    slide_count = context.user_data.get("slide_count")
    
    if not topic or not slide_count:
        await context.bot.send_message(chat_id=query.message.chat_id, text="Xatolik: Ma'lumotlar yo'qoldi. Iltimos, /start buyrug'idan boshlang.")
        return

    await context.bot.send_message(chat_id=query.message.chat_id, text=f"Shablon {template_id} tanlandi. Prezentatsiya tayyorlanmoqda, iltimos kuting...")
    
    try:
        # Check if template exists
        if not os.path.exists(template_file):
            await context.bot.send_message(chat_id=query.message.chat_id, text=f"Xatolik: Shablon {template_id} topilmadi. Iltimos, fayllar yuklanganini tekshiring.")
            return

        # Generate the presentation
        output_path = generate_presentation(topic, slide_count, template_file)
        
        # Send the file
        with open(output_path, "rb") as doc:
            await context.bot.send_document(chat_id=query.message.chat_id, document=doc, filename=f"{topic}.pptx")
        os.remove(output_path)
    except Exception as e:
        logging.error(f"Error generating presentation: {e}")
        await context.bot.send_message(chat_id=query.message.chat_id, text="Xatolik yuz berdi. Iltimos qaytadan urinib ko'ring.")

if __name__ == '__main__':
    if not TOKEN:
        print("Xatolik: BOT_TOKEN topilmadi!")
    else:
        application = ApplicationBuilder().token(TOKEN).build()
        
        application.add_handler(CommandHandler('start', start))
        # Handle slide count selection (text buttons)
        application.add_handler(MessageHandler(filters.Regex('^(5|10|15|20|25|30)$'), handle_slide_count))
        # Handle initial topic input
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topic))
        # Handle template selection (inline buttons)
        application.add_handler(CallbackQueryHandler(handle_template_selection, pattern='^tmpl_'))
        
        print("Bot ishga tushdi...")
        application.run_polling()
