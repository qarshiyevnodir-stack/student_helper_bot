"""Bot uchun xavfsizlik va barqarorlik yordamchilari.

Bu modul foydalanuvchi oqimlarini o'zgartirmaydi. U faqat:
- maxfiy tokenlar jurnalga chiqishini maskalaydi;
- tashqi HTTP loggerlarining to'liq URL yozishini cheklaydi;
- kutilmagan xatolarni markazlashgan tarzda qayd qiladi.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Optional


_SECRET_PATTERNS = (
    # Telegram bot tokenlari: 123456789:AA... ko'rinishi
    re.compile(r"(?<!\d)\d{6,12}:[A-Za-z0-9_-]{20,}"),
    # Together API tokenlari
    re.compile(r"\btgp_v1_[A-Za-z0-9_-]+\b"),
    # OpenAI kalitlari va Bearer sarlavhalari
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9._-]+"),
)


def redact_secrets(value: object) -> str:
    """Jurnal matnidan token ko'rinishidagi maxfiy qiymatlarni olib tashlaydi."""
    text = str(value)
    for pattern in _SECRET_PATTERNS:
        if pattern.pattern.startswith("(?i)(Bearer"):
            text = pattern.sub(r"\1***", text)
        else:
            text = pattern.sub("***", text)

    # Muhit o'zgaruvchisidagi maxfiy qiymatlar ham jurnalda ko'rinmasin.
    for key in ("BOT_TOKEN", "OPENAI_API_KEY", "TOGETHER_API_KEY_1", "TOGETHER_API_KEY_2"):
        secret = os.getenv(key)
        if secret:
            text = text.replace(secret, "***")
    return text


class RedactingFilter(logging.Filter):
    """Har qanday logger xabarida maxfiy kalitni maskalaydi."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
            record.msg = redact_secrets(rendered)
            record.args = ()
        except Exception:
            # Logging hech qachon bot ishini to'xtatmasligi kerak.
            pass
        return True


def configure_secure_logging() -> None:
    """HTTP client jurnallarini qisqartiradi va barcha mavjud handlerlarga filter qo'yadi."""
    root = logging.getLogger()
    redact_filter = RedactingFilter()

    # httpx INFO loglari to'liq request URLni yozishi mumkin; ayniqsa Telegram tokeni URLda bo'ladi.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext").setLevel(logging.INFO)

    for handler in root.handlers:
        if not any(isinstance(existing, RedactingFilter) for existing in handler.filters):
            handler.addFilter(redact_filter)


def get_safe_logger(name: Optional[str] = None) -> logging.Logger:
    """Maxfiy ma'lumotlar maskalanadigan loggerni qaytaradi."""
    logger = logging.getLogger(name)
    if not any(isinstance(existing, RedactingFilter) for existing in logger.filters):
        logger.addFilter(RedactingFilter())
    return logger


async def global_error_handler(update, context) -> None:
    """Kutilmagan handler xatosini xavfsiz loglaydi va foydalanuvchiga tushunarli javob beradi."""
    logger = get_safe_logger("bot.error")
    user_id = getattr(getattr(update, "effective_user", None), "id", None)
    update_type = type(update).__name__ if update else "unknown"
    error = getattr(context, "error", None)
    error_info = (type(error), error, error.__traceback__) if error else None
    logger.error(
        "Kutilmagan bot xatosi | user_id=%s | update=%s",
        user_id,
        update_type,
        exc_info=error_info,
    )

    message = getattr(update, "effective_message", None) if update else None
    if message:
        try:
            await message.reply_text(
                "❌ Kutilmagan texnik xato yuz berdi. Iltimos, qayta urinib ko'ring."
            )
        except Exception:
            logger.exception("Foydalanuvchiga xato xabarini yuborib bo'lmadi")
