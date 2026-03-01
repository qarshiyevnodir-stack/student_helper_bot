import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from utils import generate_presentation
from dotenv import load_dotenv

load_dotenv()

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Get Token from Environment Variable
TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Assalomu alaykum! Prezentatsiya yaratish uchun mavzu kiriting:")

async def handle_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['topic'] = update.message.text
    
    # Slide count selection with buttons
    keyboard = [
        [InlineKeyboardButton("5", callback_data='5'), InlineKeyboardButton("10", callback_data='10')],
        [InlineKeyboardButton("15", callback_data='15'), InlineKeyboardButton("20", callback_data='20')],
        [InlineKeyboardButton("25", callback_data='25'), InlineKeyboardButton("30", callback_data='30')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"Sizning mavzuingiz: '{update.message.text}'.\nNechta slayd kerak?", reply_markup=reply_markup)

async def handle_slide_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['slide_count'] = int(query.data)
    
    # Template selection with images
    await query.message.reply_text("Iltimos, shablon tanlang:")
    
    for i in range(1, 11):
        photo_path = f"templates/previews/{i}.png"
        keyboard = [[InlineKeyboardButton(f"Shablon {i} ni tanlash", callback_data=f"tmpl_{i}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if os.path.exists(photo_path):
            with open(photo_path, 'rb') as photo:
                await context.bot.send_photo(chat_id=query.message.chat_id, photo=photo, reply_markup=reply_markup)
        else:
            await context.bot.send_message(chat_id=query.message.chat_id, text=f"Shablon {i}", reply_markup=reply_markup)

async def handle_template_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    template_id = query.data.split('_')[1]
    # Simplify template file path
    template_file = f"templates/shablonlar/{template_id}.pptx"
    topic = context.user_data.get('topic')
    slide_count = context.user_data.get('slide_count')
    
    await context.bot.send_message(chat_id=query.message.chat_id, text=f"Shablon {template_id} tanlandi. Prezentatsiya tayyorlanmoqda, iltimos kuting...")
    
    try:
        # Check if template exists
        if not os.path.exists(template_file):
            await context.bot.send_message(chat_id=query.message.chat_id, text=f"Xatolik: {template_file} topilmadi.")
            return

        # Generate the presentation
        output_path = generate_presentation(topic, slide_count, template_file)
        
        # Send the file
        with open(output_path, 'rb') as doc:
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
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topic))
        application.add_handler(CallbackQueryHandler(handle_slide_count, pattern='^(5|10|15|20|25|30)$'))
        application.add_handler(CallbackQueryHandler(handle_template_selection, pattern='^tmpl_'))
        
        application.run_polling()
