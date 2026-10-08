"""Yangi foydalanuvchi reklamasi Telegram Markdown parse xatosini bermasligini sinaydi."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
from telegram.error import BadRequest


class FakeBot:
    def __init__(self):
        self.message = None

    async def send_message(self, **kwargs):
        self.message = kwargs


class RejectingBot:
    async def send_message(self, **_kwargs):
        raise BadRequest("test message rejection")


async def run_test():
    bot = FakeBot()
    await main.send_new_user_topup_bonus_announcement(bot, 1)

    assert bot.message is not None
    assert bot.message["text"] == main.NEW_USER_TOPUP_BONUS_ANNOUNCEMENT
    assert "parse_mode" not in bot.message
    assert "*" not in bot.message["text"]
    assert "@slidego_bot" in bot.message["text"]

    # Promotional notice is optional and must not abort onboarding on rejection.
    await main.send_new_user_topup_bonus_announcement(RejectingBot(), 1)
    print("NEW_USER_BONUS_PLAIN_TEXT_TEST_OK")


asyncio.run(run_test())
