"""Broadcast rejimidagi matn ConversationHandler oqimiga o'tmasligini sinaydi."""
import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
from telegram.ext import ApplicationHandlerStop

ADMIN_ID = next(iter(main.ADMIN_IDS))


class FakeUser:
    id = ADMIN_ID


class FakeMessage:
    text = "*Test e'lon*\n\nYangi qator"

    async def reply_text(self, *_args, **_kwargs):
        return None


class FakeUpdate:
    effective_user = FakeUser()
    message = FakeMessage()


class FakeBot:
    async def send_message(self, **_kwargs):
        return type("SentMessage", (), {"message_id": 101})()


class FakeContext:
    def __init__(self):
        self.user_data = {"admin_broadcast_waiting": True}
        self.bot = FakeBot()


async def run_test():
    saved = []
    originals = {
        "users": main.db.get_all_users,
        "clear": main.db.clear_broadcast_messages,
        "save": main.db.save_broadcast_message,
    }
    main.db.get_all_users = lambda limit=5000: [{"user_id": 701}, {"user_id": 702}]
    main.db.clear_broadcast_messages = lambda: None
    main.db.save_broadcast_message = lambda session, user_id, message_id: saved.append((user_id, message_id))
    try:
        try:
            await main.admin_broadcast_text_handler(FakeUpdate(), FakeContext())
            raise AssertionError("ApplicationHandlerStop kutilgan edi")
        except ApplicationHandlerStop:
            pass
        assert saved == [(701, 101), (702, 101)], saved
        print("BROADCAST_HANDLER_STOP_TEST_OK")
    finally:
        main.db.get_all_users = originals["users"]
        main.db.clear_broadcast_messages = originals["clear"]
        main.db.save_broadcast_message = originals["save"]


asyncio.run(run_test())
