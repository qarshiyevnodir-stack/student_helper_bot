"""AI yordamchi — professional akademik suhbat moduli"""
import os
from openai import OpenAI
from bot_core.pricing import AI_FREE_LIMIT, AI_PRICE_PER_MSG

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
)

SYSTEM_PROMPT = """Sen O'zbekistonning eng yaxshi akademik va professional AI yordamchisisisan. 
Sening vazifang — talabalar, o'qituvchilar va mutaxassislarga yuqori sifatli, chuqur va aniq javoblar berish.

QOIDALAR:
1. Har doim professional va akademik uslubda javob ber
2. Javoblarni tuzilgan holda ber: sarlavhalar, ro'yxatlar, jadvallar ishlatish
3. Ilmiy atamalarni to'g'ri ishlatib, kerak bo'lsa tushuntir
4. Misollar va dalillar bilan javobni boyit
5. O'zbek tilida so'ralsa — O'zbek tilida, rus tilida so'ralsa — rus tilida javob ber
6. Qisqa savolga qisqa, murakkab savolga batafsil javob ber
7. Noto'g'ri ma'lumot berma — bilmasang, "Bu haqda aniq ma'lumotim yo'q" de
8. Markdown formatidan foydalanish: **qalin**, _kursiv_, jadvallar, ro'yxatlar

SOHA: Ta'lim, fan, texnologiya, iqtisodiyot, tibbiyot, huquq, tarix va boshqa barcha sohalar."""


async def get_ai_response(messages: list) -> str:
    """GPT dan javob olish — suhbat tarixi bilan."""
    try:
        full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=full_messages,
            max_tokens=1500,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise Exception(f"GPT xatolik: {e}")
