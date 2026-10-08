"""Yangi foydalanuvchi top-up e'lonini faqat bir marta olishini sinaydi."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


class FakeUser:
    def __init__(self, user_id=990001, first_name="Yangi foydalanuvchi"):
        self.id = user_id
        self.first_name = first_name
        self.username = "new_user"
        self.full_name = first_name


class FakeMessage:
    def __init__(self):
        self.replies = []

    async def reply_text(self, text, **kwargs):
        self.replies.append((text, kwargs))


class FakeQuery:
    def __init__(self):
        self.answers = []
        self.edits = []

    async def answer(self, **kwargs):
        self.answers.append(kwargs)

    async def edit_message_text(self, text, **kwargs):
        self.edits.append((text, kwargs))


class FakeBot:
    def __init__(self):
        self.messages = []

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)


class FakeContext:
    def __init__(self):
        self.bot = FakeBot()
        self.user_data = {}
        self.args = []


class FakeUpdate:
    def __init__(self, user, message=None, query=None):
        self.effective_user = user
        self.message = message
        self.callback_query = query


async def subscribed(*_args, **_kwargs):
    return True


async def assert_direct_start_shows_promotion_once():
    user = FakeUser(990001)
    message = FakeMessage()
    context = FakeContext()
    update = FakeUpdate(user, message=message)

    await main.start(update, context)

    assert len(message.replies) == 1
    assert "Xush kelibsiz bonusi" in message.replies[0][0]
    assert len(context.bot.messages) == 1
    assert context.bot.messages[0]["text"] == main.NEW_USER_TOPUP_BONUS_ANNOUNCEMENT
    assert "parse_mode" not in context.bot.messages[0]


async def assert_existing_direct_start_skips_promotion_once():
    user = FakeUser(990002)
    message = FakeMessage()
    context = FakeContext()
    update = FakeUpdate(user, message=message)

    await main.start(update, context)

    assert len(message.replies) == 1
    assert "Botga xush kelibsiz" in message.replies[0][0]
    assert context.bot.messages == []


async def assert_subscription_completion_shows_promotion_once():
    user = FakeUser(990003)
    query = FakeQuery()
    context = FakeContext()
    update = FakeUpdate(user, query=query)

    await main.check_sub_callback(update, context)

    assert len(query.answers) == 1
    assert len(context.bot.messages) == 2
    assert "Xush kelibsiz bonusi" in context.bot.messages[0]["text"]
    assert context.bot.messages[1]["text"] == main.NEW_USER_TOPUP_BONUS_ANNOUNCEMENT


async def assert_existing_subscription_completion_skips_promotion_once():
    user = FakeUser(990004)
    query = FakeQuery()
    context = FakeContext()
    update = FakeUpdate(user, query=query)

    await main.check_sub_callback(update, context)

    assert len(query.answers) == 1
    assert len(context.bot.messages) == 1
    assert "Xush kelibsiz bonusi" not in context.bot.messages[0]["text"]


async def run_test():
    originals = {
        "maintenance": main.FINANCIAL_MAINTENANCE_MODE,
        "subscription": main.check_subscription,
        "get_or_create": main.db.get_or_create_user,
        "welcome_bonus": main.db.give_welcome_bonus,
    }
    bonus_results = iter((True, False, True, False))
    main.FINANCIAL_MAINTENANCE_MODE = False
    main.check_subscription = subscribed
    main.db.get_or_create_user = lambda *_args, **_kwargs: {"user_id": _args[0]}
    main.db.give_welcome_bonus = lambda *_args, **_kwargs: next(bonus_results)
    try:
        await assert_direct_start_shows_promotion_once()
        await assert_existing_direct_start_skips_promotion_once()
        await assert_subscription_completion_shows_promotion_once()
        await assert_existing_subscription_completion_skips_promotion_once()
    finally:
        main.FINANCIAL_MAINTENANCE_MODE = originals["maintenance"]
        main.check_subscription = originals["subscription"]
        main.db.get_or_create_user = originals["get_or_create"]
        main.db.give_welcome_bonus = originals["welcome_bonus"]

    assert "admin tekshirganidan" not in main.NEW_USER_TOPUP_BONUS_ANNOUNCEMENT
    assert "to'lov summasi 10% bonus" in main.NEW_USER_TOPUP_BONUS_ANNOUNCEMENT
    assert "*" not in main.NEW_USER_TOPUP_BONUS_ANNOUNCEMENT
    print("NEW_USER_BONUS_ANNOUNCEMENT_TEST_OK")


asyncio.run(run_test())
