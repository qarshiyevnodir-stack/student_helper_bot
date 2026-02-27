import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from utils import generate_presentation

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Get Token from Environment Variable
TOKEN = os.getenv("BOT_TOKEN")

# Mapping of templates
TEMPLATES = {
    "1": "1 Blue & white company profile presentation.pptx",
    "2": "2 Blue Modern Futuristic Presentation.pptx",
    "3": "3 Bulletin Board Prenuptial Photoshoot Album.pptx",
    "4": "4 Cute Doodle Notebook Photocard Journal, копия.pptx",
    "5": "5 Dasturlarni-sinovdan-otkazish-va-tuzatish-8-sinflar-uchun-Google-Classroom-qollanmasi.pptx",
    "6": "6 Green Blue and White Modern Project History Presentation.pptx",
    "7": "7 Havo-Harorati-Inversiyalari-va-Ularning-Kelib-Chiqishi.pptx",
    "8": "8 Modern Apartments Brochure, копия.pptx",
    "9": "9 Ozbekiston-Respublikasi-Mustaqilligining-33-yilligi.pptx",
    "10": "10 Vibrant Green Leaves by Slidesgo.pptx",
    "11": "11 Кремовый и Розовый Пастельный Градиент Разнообразие Мастер-класс Вебинар Программная презентация.pptx",
    "12": "12 Черная Современная Технология Основная Мысль Презентация.pptx"
}

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
    await query.edit_message_text("Iltimos, shablon tanlang:")
    
    for i in range(1, 13):
        photo_path = f"templates/previews/{i}.png"
        keyboard = [[InlineKeyboardButton(f"Shablon {i} ni tanlash", callback_data=f"tmpl_{i}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if os.path.exists(photo_path):
            await context.bot.send_photo(chat_id=query.message.chat_id, photo=open(photo_path, 'rb'), reply_markup=reply_markup)
        else:
            await context.bot.send_message(chat_id=query.message.chat_id, text=f"Shablon {i}", reply_markup=reply_markup)

async def handle_template_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    template_id = query.data.split('_')[1]
    template_file = TEMPLATES.get(template_id)
    topic = context.user_data.get('topic')
    slide_count = context.user_data.get('slide_count')
    
    await context.bot.send_message(chat_id=query.message.chat_id, text="Prezentatsiya tayyorlanmoqda, iltimos kuting...")
    
    try:
        # Generate the presentation
        output_path = generate_presentation(topic, slide_count, template_file)
        
        # Send the file
        await context.bot.send_document(chat_id=query.message.chat_id, document=open(output_path, 'rb'), filename=f"{topic}.pptx")
        os.remove(output_path)
    except Exception as e:
        logging.error(f"Error generating presentation: {e}")
        await context.bot.send_message(chat_id=query.message.chat_id, text="Xatolik yuz berdi. Iltimos qaytadan urinib ko'ring.")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_topic))
    application.add_handler(CallbackQueryHandler(handle_slide_count, pattern='^(5|10|15|20|25|30)$'))
    application.add_handler(CallbackQueryHandler(handle_template_selection, pattern='^tmpl_'))
    
    application.run_polling()
