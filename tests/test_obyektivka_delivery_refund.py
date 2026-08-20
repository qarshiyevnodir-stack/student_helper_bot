"""Ma'lumotnoma fayli yuborilmasa atomik refund bo'lishini sinaydi."""
import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
from telegram.ext import ConversationHandler


class FakeUser:
    id = 901


class FakeQuery:
    data = "ob_fmt_docx"
    from_user = FakeUser()

    def __init__(self):
        self.edits = []

    async def answer(self):
        return None

    async def edit_message_text(self, text, **kwargs):
        self.edits.append((text, kwargs))


class FakeUpdate:
    def __init__(self):
        self.callback_query = FakeQuery()


class FailingBot:
    def __init__(self):
        self.messages = []

    async def send_document(self, **kwargs):
        raise RuntimeError("Telegram hujjat yuborish sinov xatosi")

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)


class FakeContext:
    def __init__(self):
        self.bot = FailingBot()
        self.user_data = {
            "ob_fish": "Test Foydalanuvchi",
            "ob_mehnat": [],
            "ob_qarindoshlar": [],
        }


async def run_test():
    calls = {"deduct": 0, "refund": 0}
    originals = {
        "get_balance": main.db.get_balance,
        "deduct_balance": main.db.deduct_balance,
        "add_balance": main.db.add_balance,
        "generate": main.generate_obyektivka,
    }
    main.db.get_balance = lambda _user_id: 5000
    main.db.deduct_balance = lambda _user_id, _amount: calls.__setitem__("deduct", calls["deduct"] + 1) or True
    main.db.add_balance = lambda _user_id, _amount: calls.__setitem__("refund", calls["refund"] + 1)
    main.generate_obyektivka = lambda _data: b"docx-test"
    try:
        result = await main.ob_format_handler(FakeUpdate(), FakeContext())
        assert result == ConversationHandler.END
        assert calls == {"deduct": 1, "refund": 1}, calls
        print("OBYEKTVKA_DELIVERY_REFUND_TEST_OK")
    finally:
        main.db.get_balance = originals["get_balance"]
        main.db.deduct_balance = originals["deduct_balance"]
        main.db.add_balance = originals["add_balance"]
        main.generate_obyektivka = originals["generate"]


asyncio.run(run_test())
