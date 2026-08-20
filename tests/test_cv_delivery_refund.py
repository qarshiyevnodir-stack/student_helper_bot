"""CV yetkazib berish xatosida refund bo'lishini handler darajasida sinaydi."""
import asyncio
from io import BytesIO
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
from telegram.ext import ConversationHandler


class FakeUser:
    id = 902


class FakeQuery:
    data = "cv_format_pdf"

    async def answer(self):
        return None

    async def edit_message_text(self, *_args, **_kwargs):
        return None


class FakeUpdate:
    callback_query = FakeQuery()
    effective_user = FakeUser()


class FailingBot:
    def __init__(self):
        self.messages = []

    async def send_chat_action(self, **_kwargs):
        return None

    async def send_document(self, **_kwargs):
        raise RuntimeError("Telegram CV yuborish sinov xatosi")

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)


class FakeContext:
    def __init__(self):
        self.bot = FailingBot()
        self.user_data = {
            "cv_data": {"fullname": "Test CV", "lang": "uz", "length": 1},
        }


async def fake_generate(_data):
    return BytesIO(b"cv-pdf-test")


async def run_test():
    calls = {"deduct": 0, "refund": 0}
    originals = {
        "get_user": main.db.get_user,
        "deduct_balance": main.db.deduct_balance,
        "add_balance": main.db.add_balance,
        "generate_pdf": main.generate_cv_full,
    }
    main.db.get_user = lambda _user_id: {"balance": 3000}
    main.db.deduct_balance = lambda _user_id, _amount: calls.__setitem__("deduct", calls["deduct"] + 1) or True
    main.db.add_balance = lambda _user_id, _amount: calls.__setitem__("refund", calls["refund"] + 1)
    main.generate_cv_full = fake_generate
    try:
        result = await main.cv_format_handler(FakeUpdate(), FakeContext())
        assert result == ConversationHandler.END
        assert calls == {"deduct": 1, "refund": 1}, calls
        print("CV_DELIVERY_REFUND_TEST_OK")
    finally:
        main.db.get_user = originals["get_user"]
        main.db.deduct_balance = originals["deduct_balance"]
        main.db.add_balance = originals["add_balance"]
        main.generate_cv_full = originals["generate_pdf"]


asyncio.run(run_test())
