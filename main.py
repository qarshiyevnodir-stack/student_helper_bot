import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from utils import create_presentation, generate_slide_content

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token and OpenAI API key from environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# State management
user_states = {}

async def start(update: Update, context) -> None:
    await update.message.reply_text(
        "Assalomu alaykum! Men sizga taqdimotlar yaratishda yordam beruvchi botman. "
        "Mavzuni yuboring, men sizga slaydlar tayyorlab beraman."
    )

async def help_command(update: Update, context) -> None:
    await update.message.reply_text(
        "Menga taqdimot mavzusini yuboring. Keyin men sizdan slaydlar sonini so'rayman. "
        "Shundan so'ng siz shablon tanlashingiz mumkin bo'ladi."
    )

async def handle_message(update: Update, context) -> None:
    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in user_states or user_states[user_id].get("step") == "start":
        user_states[user_id] = {"step": "ask_slides_count", "topic": text}
        await update.message.reply_text(
            f"Sizning mavzuingiz: '{text}'. Nechta slayd kerak? (Masalan: 5, 10, 15)"
        )
    elif user_states[user_id].get("step") == "ask_slides_count":
        try:
            slides_count = int(text)
            if 1 <= slides_count <= 20:
                user_states[user_id]["slides_count"] = slides_count
                user_states[user_id]["step"] = "ask_template"
                
                keyboard = []
                for i in range(1, 13):
                    keyboard.append([InlineKeyboardButton(f"Shablon {i}", callback_data=f"template_{i}")])
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "Iltimos, shablon tanlang:", reply_markup=reply_markup
                )
            else:
                await update.message.reply_text("Slaydlar soni 1 dan 20 gacha bo'lishi kerak. Qayta kiriting.")
        except ValueError:
            await update.message.reply_text("Iltimos, faqat raqam kiriting. Nechta slayd kerak?")

async def button(update: Update, context) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id in user_states and user_states[user_id].get("step") == "ask_template":
        template_id = int(query.data.split("_")[1])
        user_states[user_id]["template_id"] = template_id
        user_states[user_id]["step"] = "generating"
        
        topic = user_states[user_id]["topic"]
        slides_count = user_states[user_id]["slides_count"]
        
        await query.edit_message_text(text=f"Mavzu: '{topic}', Slaydlar soni: {slides_count}, Tanlangan shablon: {template_id}. Taqdimot tayyorlanmoqda... Bu biroz vaqt olishi mumkin.")
        
        try:
            # Generate slide content using OpenAI
            slide_contents = await generate_slide_content(OPENAI_API_KEY, topic, slides_count)
            
            # Create presentation
            output_path = f"/tmp/presentation_{user_id}.pptx"
            create_presentation(template_id, slide_contents, output_path)
            
            # Send the presentation
            await context.bot.send_document(chat_id=user_id, document=open(output_path, 'rb'))
            await context.bot.send_message(chat_id=user_id, text="Taqdimotingiz tayyor! Yana biror narsa kerak bo'lsa, mavzu yuboring.")
            
            # Clean up
            os.remove(output_path)
            user_states[user_id] = {"step": "start"} # Reset state
            
        except Exception as e:
            logger.error(f"Error generating presentation for user {user_id}: {e}")
            await context.bot.send_message(chat_id=user_id, text=f"Taqdimotni yaratishda xatolik yuz berdi: {e}. Iltimos, qayta urinib ko'ring.")
            user_states[user_id] = {"step": "start"} # Reset state on error
    else:
        await query.edit_message_text(text="Noto'g'ri buyruq yoki holat. Iltimos, /start buyrug'ini bosing.")

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button))

    application.run_polling()

if __name__ == "__main__":
    main()
