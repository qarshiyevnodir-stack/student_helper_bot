"""
db.py — Slidego bot uchun PostgreSQL ma'lumotlar bazasi moduli
Jadvallar:
  - users             : foydalanuvchilar va ularning balansi
  - transactions      : to'lov operatsiyalari (chek yuborish, tasdiqlash)
  - generations       : har bir yaratilgan fayl logi
  - user_topup_state  : topup holati (restart da yo'qolmaydi)

Muhit o'zgaruvchisi:
  DATABASE_URL — Railway PostgreSQL connection string
  (masalan: postgresql://user:pass@host:5432/dbname)
"""

import os
import random
import string
from datetime import datetime, date

import psycopg2
import psycopg2.extras
from psycopg2 import pool
from bot_core.pricing import OBYEKTIVKA_FREE_LIMIT

# ─────────────────────────────────────────────
# Connection pool
# ─────────────────────────────────────────────

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Railway ba'zan "postgres://" prefiksi bilan beradi, psycopg2 "postgresql://" talab qiladi
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL muhit o'zgaruvchisi topilmadi!\n"
                "Railway da PostgreSQL qo'shib, DATABASE_URL ni bot servisiga ulang."
            )
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=20,
            dsn=DATABASE_URL
        )
    return _pool


def get_conn():
    """Connection pool dan ulanish oladi."""
    conn = _get_pool().getconn()
    return conn


def release_conn(conn):
    """Ulanishni pool ga qaytaradi."""
    _get_pool().putconn(conn)


# ─────────────────────────────────────────────
# DB ni ishga tushirish
# ─────────────────────────────────────────────

def init_db():
    """Barcha jadvallarni yaratadi (agar mavjud bo'lmasa)."""
    conn = get_conn()
    try:
        c = conn.cursor()

        # Foydalanuvchilar jadvali
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id             BIGINT PRIMARY KEY,
                username            TEXT,
                full_name           TEXT,
                balance             INTEGER DEFAULT 0,
                referral_code       TEXT UNIQUE,
                referred_by         BIGINT,
                joined_at           TIMESTAMP DEFAULT NOW(),
                last_active         TIMESTAMP DEFAULT NOW(),
                welcome_bonus_given BOOLEAN DEFAULT FALSE
            )
        """)
        # Mavjud DB da ustun bo'lmasa qo'shamiz (migration)
        c.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS welcome_bonus_given BOOLEAN DEFAULT FALSE
        """)

        # To'lov operatsiyalari
        c.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id            SERIAL PRIMARY KEY,
                user_id       BIGINT NOT NULL,
                amount        INTEGER NOT NULL,
                type          TEXT NOT NULL,
                status        TEXT DEFAULT 'pending',
                screenshot_id TEXT,
                note          TEXT,
                created_at    TIMESTAMP DEFAULT NOW(),
                updated_at    TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Generatsiya logi
        c.execute("""
            CREATE TABLE IF NOT EXISTS generations (
                id          SERIAL PRIMARY KEY,
                user_id     BIGINT NOT NULL,
                service     TEXT NOT NULL,
                topic       TEXT,
                cost        INTEGER NOT NULL,
                created_at  TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # generations jadvaliga file_id ustunini qo'shish (migration)
        c.execute("""
            ALTER TABLE generations
            ADD COLUMN IF NOT EXISTS file_id TEXT
        """)
        c.execute("""
            ALTER TABLE generations
            ADD COLUMN IF NOT EXISTS file_name TEXT
        """)

        # AI yordamchi kunlik foydalanish jadvali
        c.execute("""
            CREATE TABLE IF NOT EXISTS ai_daily_usage (
                user_id    BIGINT NOT NULL,
                usage_date DATE NOT NULL DEFAULT CURRENT_DATE,
                count      INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, usage_date),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        # Ma'lumotnoma/Obyektivka uchun umrboqiy bepul foydalanish hisobi.
        # Birlamchi kalit parallel so'rovlar orasida limitning atomik saqlanishini ta'minlaydi.
        c.execute("""
            CREATE TABLE IF NOT EXISTS obyektivka_free_usage (
                user_id    BIGINT PRIMARY KEY,
                count      INTEGER NOT NULL DEFAULT 0 CHECK (count >= 0),
                updated_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # Topup holati jadvali
        c.execute("""
            CREATE TABLE IF NOT EXISTS user_topup_state (
                user_id    BIGINT PRIMARY KEY,
                state      TEXT NOT NULL,
                amount     INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Broadcast xabarlar jadvali
        c.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_messages (
                id         SERIAL PRIMARY KEY,
                user_id    BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                sent_at    TIMESTAMP DEFAULT NOW()
            )
        """)
        # Oxirgi broadcast ID ni saqlash
        c.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_sessions (
                id         SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL UNIQUE,
                sent_at    TIMESTAMP DEFAULT NOW()
            )
        """)

        conn.commit()
    finally:
        release_conn(conn)


# ─────────────────────────────────────────────
# Yordamchi: Row ni dict ga aylantirish
# ─────────────────────────────────────────────

def _row_to_dict(cursor, row):
    """psycopg2 Row ni dict ga aylantiradi."""
    if row is None:
        return None
    cols = [desc[0] for desc in cursor.description]
    return dict(zip(cols, row))


def _rows_to_dicts(cursor, rows):
    cols = [desc[0] for desc in cursor.description]
    return [dict(zip(cols, row)) for row in rows]


# ─────────────────────────────────────────────
# Foydalanuvchi CRUD
# ─────────────────────────────────────────────

def get_or_create_user(user_id: int, username: str = None, full_name: str = None,
                       referred_by: int = None) -> dict:
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        row = c.fetchone()
        if row:
            c.execute("UPDATE users SET last_active = NOW() WHERE user_id = %s", (user_id,))
            conn.commit()
            # UPDATE dan keyin cursor.description None bo'ladi, shuning uchun qayta SELECT qilamiz
            c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            return _row_to_dict(c, c.fetchone())

        # Yangi foydalanuvchi
        ref_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        c.execute("""
            INSERT INTO users (user_id, username, full_name, referral_code, referred_by)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, username, full_name, ref_code, referred_by))
        conn.commit()
        c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        return _row_to_dict(c, c.fetchone())
    finally:
        release_conn(conn)


def get_user(user_id: int) -> dict | None:
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        row = c.fetchone()
        return _row_to_dict(c, row)
    finally:
        release_conn(conn)


def get_balance(user_id: int) -> int:
    user = get_user(user_id)
    return user['balance'] if user else 0


def add_balance(user_id: int, amount: int):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("UPDATE users SET balance = balance + %s WHERE user_id = %s", (amount, user_id))
        conn.commit()
    finally:
        release_conn(conn)


def set_balance(user_id: int, new_balance: int) -> bool:
    """Foydalanuvchi balansini to'g'ridan-to'g'ri o'rnatadi (admin uchun)."""
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute(
            "UPDATE users SET balance = %s WHERE user_id = %s RETURNING user_id",
            (new_balance, user_id)
        )
        updated = c.fetchone()
        conn.commit()
        return updated is not None
    finally:
        release_conn(conn)


def deduct_balance(user_id: int, amount: int) -> bool:
    """Balansdan atomik tarzda yechadi. Yetarli bo'lmasa False qaytaradi.

    `SELECT` va keyingi `UPDATE` alohida bajarilsa, foydalanuvchi bir vaqtda
    ikki buyurtma yuborganda balans manfiy bo'lib qolishi mumkin. Shu sabab
    tekshiruv hamda yechish bitta SQL amali ichida bajariladi.
    """
    if amount <= 0:
        return False
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""
            UPDATE users
            SET balance = balance - %s,
                last_active = NOW()
            WHERE user_id = %s
              AND balance >= %s
            RETURNING balance
        """, (amount, user_id, amount))
        updated = c.fetchone()
        conn.commit()
        return updated is not None
    finally:
        release_conn(conn)


def get_all_users(limit: int = 50, offset: int = 0) -> list:
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT user_id, username, full_name, balance, joined_at, last_active
            FROM users ORDER BY joined_at DESC LIMIT %s OFFSET %s
        """, (limit, offset))
        return _rows_to_dicts(c, c.fetchall())
    finally:
        release_conn(conn)


def count_users() -> int:
    """Jami foydalanuvchilar sonini qaytaradi."""
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        return c.fetchone()[0]
    finally:
        release_conn(conn)


def get_users_page(page: int = 1, per_page: int = 15, sort_by: str = 'joined_at') -> list:
    """Foydalanuvchilarni sahifalab qaytaradi.
    sort_by: 'joined_at' | 'balance' | 'last_active'
    """
    allowed_sorts = {'joined_at', 'balance', 'last_active'}
    if sort_by not in allowed_sorts:
        sort_by = 'joined_at'
    offset = (page - 1) * per_page
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute(f"""
            SELECT user_id, username, full_name, balance, joined_at, last_active
            FROM users ORDER BY {sort_by} DESC LIMIT %s OFFSET %s
        """, (per_page, offset))
        return _rows_to_dicts(c, c.fetchall())
    finally:
        release_conn(conn)


def give_welcome_bonus(user_id: int, amount: int = 6000) -> bool:
    """Yangi foydalanuvchiga bir martalik xush kelibsiz bonusini beradi.
    
    Returns:
        True — bonus berildi (birinchi marta)
        False — bonus allaqachon berilgan
    """
    conn = get_conn()
    try:
        c = conn.cursor()
        # Atomik: faqat welcome_bonus_given=FALSE bo'lsa yangilaydi
        c.execute("""
            UPDATE users
            SET balance = balance + %s,
                welcome_bonus_given = TRUE
            WHERE user_id = %s AND welcome_bonus_given = FALSE
        """, (amount, user_id))
        updated = c.rowcount  # 1 — yangilandi, 0 — allaqachon berilgan
        conn.commit()
        return updated > 0
    finally:
        release_conn(conn)


def get_user_by_ref_code(ref_code: str) -> dict | None:
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE referral_code = %s", (ref_code,))
        row = c.fetchone()
        return _row_to_dict(c, row)
    finally:
        release_conn(conn)


# ─────────────────────────────────────────────
# Tranzaksiyalar
# ─────────────────────────────────────────────

def create_topup_request(user_id: int, amount: int, screenshot_id: str) -> int:
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""
            INSERT INTO transactions (user_id, amount, type, status, screenshot_id)
            VALUES (%s, %s, 'topup', 'pending', %s)
            RETURNING id
        """, (user_id, amount, screenshot_id))
        tx_id = c.fetchone()[0]
        conn.commit()
        return tx_id
    finally:
        release_conn(conn)


def approve_topup(tx_id: int) -> dict | None:
    """Faqat bir marta tasdiqlanadigan to'lovni atomik tarzda balansga qo'shadi."""
    conn = get_conn()
    try:
        c = conn.cursor()
        # `status = pending` sharti aynan UPDATE ichida: ikki admin bir paytda
        # tugmani bossa, faqat birinchi so'rov mablag'ni qo'sha oladi.
        c.execute("""
            UPDATE transactions
            SET status = 'approved', updated_at = NOW()
            WHERE id = %s AND status = 'pending'
            RETURNING user_id, amount, id, type, status, screenshot_id, note, created_at, updated_at
        """, (tx_id,))
        row = c.fetchone()
        if not row:
            conn.rollback()
            return None
        tx = _row_to_dict(c, row)
        c.execute("""
            UPDATE users
            SET balance = balance + %s,
                last_active = NOW()
            WHERE user_id = %s
        """, (tx['amount'], tx['user_id']))
        conn.commit()
        return tx
    finally:
        release_conn(conn)


def update_topup_amount(tx_id: int, new_amount: int) -> bool:
    """To'lov so'rovining summasini yangilaydi (faqat pending holat uchun)."""
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""
            UPDATE transactions SET amount = %s, updated_at = NOW()
            WHERE id = %s AND status = 'pending'
        """, (new_amount, tx_id))
        conn.commit()
        return c.rowcount > 0
    finally:
        release_conn(conn)


def reject_topup(tx_id: int) -> dict | None:
    """Faqat pending chekni bir marta rad etadi."""
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""
            UPDATE transactions
            SET status = 'rejected', updated_at = NOW()
            WHERE id = %s AND status = 'pending'
            RETURNING user_id, amount, id, type, status, screenshot_id, note, created_at, updated_at
        """, (tx_id,))
        row = c.fetchone()
        if not row:
            conn.rollback()
            return None
        tx = _row_to_dict(c, row)
        conn.commit()
        return tx
    finally:
        release_conn(conn)


def get_pending_topups() -> list:
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT t.*, u.username, u.full_name
            FROM transactions t
            JOIN users u ON t.user_id = u.user_id
            WHERE t.type = 'topup' AND t.status = 'pending'
            ORDER BY t.created_at ASC
        """)
        return _rows_to_dicts(c, c.fetchall())
    finally:
        release_conn(conn)


def create_topup_request_approved(user_id: int, amount: int, note: str = "Admin qo'lda qo'shdi") -> int:
    """Admin tomonidan to'g'ridan-to'g'ri tasdiqlangan topup yozadi (jami tushum uchun)."""
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""
            INSERT INTO transactions (user_id, amount, type, status, note, updated_at)
            VALUES (%s, %s, 'topup', 'approved', %s, NOW())
            RETURNING id
        """, (user_id, amount, note))
        tx_id = c.fetchone()[0]
        conn.commit()
        return tx_id
    finally:
        release_conn(conn)


def log_deduction(user_id: int, amount: int, note: str = ""):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""
            INSERT INTO transactions (user_id, amount, type, status, note)
            VALUES (%s, %s, 'deduct', 'approved', %s)
        """, (user_id, amount, note))
        conn.commit()
    finally:
        release_conn(conn)


# ─────────────────────────────────────────────
# Generatsiya logi
# ─────────────────────────────────────────────

def log_generation(user_id: int, service: str, topic: str, cost: int, file_id: str = None, file_name: str = None):
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""
            INSERT INTO generations (user_id, service, topic, cost, file_id, file_name)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, service, topic, cost, file_id, file_name))
        conn.commit()
    finally:
        release_conn(conn)


def get_user_generations(user_id: int, limit: int = 10) -> list:
    """Foydalanuvchining so'nggi ishlarini qaytaradi."""
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT id, service, topic, cost, file_id, file_name, created_at
            FROM generations
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (user_id, limit))
        rows = c.fetchall()
        cols = ["id", "service", "topic", "cost", "file_id", "file_name", "created_at"]
        return [dict(zip(cols, row)) for row in rows]
    finally:
        release_conn(conn)


# ─────────────────────────────────────────────
# Statistika
# ─────────────────────────────────────────────

def get_stats() -> dict:
    conn = get_conn()
    try:
        c = conn.cursor()
        today = date.today().isoformat()

        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM users WHERE joined_at::date = %s", (today,))
        new_today = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM users WHERE referred_by IS NOT NULL")
        via_referral = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM generations")
        total_generations = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM generations WHERE created_at::date = %s", (today,))
        generations_today = c.fetchone()[0]

        c.execute("SELECT service, COUNT(*) FROM generations GROUP BY service")
        by_service = {row[0]: row[1] for row in c.fetchall()}

        c.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions WHERE type = 'topup' AND status = 'approved'
        """)
        total_income = c.fetchone()[0]

        c.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions WHERE type = 'topup' AND status = 'approved'
            AND updated_at::date = %s
        """, (today,))
        income_today = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM transactions WHERE type='topup' AND status='pending'")
        pending_topups = c.fetchone()[0]

        return {
            "total_users":        total_users,
            "new_today":          new_today,
            "via_referral":       via_referral,
            "total_generations":  total_generations,
            "generations_today":  generations_today,
            "by_service":         by_service,
            "total_income":       total_income,
            "income_today":       income_today,
            "pending_topups":     pending_topups,
        }
    finally:
        release_conn(conn)


# ─────────────────────────────────────────────
# Topup holati (DB da saqlanadi — restart da yo'qolmaydi)
# ─────────────────────────────────────────────

def set_user_topup_state(user_id: int, state: str | None, amount: int = 0):
    """Foydalanuvchining topup holatini DB ga saqlaydi."""
    conn = get_conn()
    try:
        c = conn.cursor()
        if state is None:
            c.execute("DELETE FROM user_topup_state WHERE user_id = %s", (user_id,))
        else:
            c.execute("""
                INSERT INTO user_topup_state (user_id, state, amount, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    state = EXCLUDED.state,
                    amount = EXCLUDED.amount,
                    updated_at = NOW()
            """, (user_id, state, amount))
        conn.commit()
    finally:
        release_conn(conn)


def get_user_topup_state(user_id: int) -> dict | None:
    """Foydalanuvchining topup holatini DB dan oladi."""
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT state, amount FROM user_topup_state WHERE user_id = %s", (user_id,))
        row = c.fetchone()
        if row:
            return {"state": row[0], "amount": row[1]}
        return None
    finally:
        release_conn(conn)


# DB boshlang'ich sozlamasi import vaqtida emas, ilova ishga tushishida `main()` tomonidan chaqiriladi.
# Bu testlar, lokal utilitalar va xavfsiz restartlar uchun import side-effect'ini yo'q qiladi.

def get_ai_daily_count(user_id: int) -> int:
    """Bugungi AI savol sonini qaytaradi."""
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT count FROM ai_daily_usage
            WHERE user_id = %s AND usage_date = CURRENT_DATE
        """, (user_id,))
        row = c.fetchone()
        return row[0] if row else 0
    finally:
        release_conn(conn)

def get_obyektivka_free_remaining(user_id: int) -> int:
    """Foydalanuvchining obyektivka bo'yicha qolgan bepul foydalanish sonini qaytaradi."""
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""
            SELECT count FROM obyektivka_free_usage
            WHERE user_id = %s
        """, (user_id,))
        row = c.fetchone()
        used = int(row[0]) if row else 0
        return max(0, OBYEKTIVKA_FREE_LIMIT - used)
    finally:
        release_conn(conn)


def claim_obyektivka_free_use(user_id: int) -> bool:
    """Bitta bepul obyektivka yaratishni atomik rezerv qiladi.

    True faqat ikki bepul imkoniyatdan biri muvaffaqiyatli rezerv qilinganda qaytadi.
    """
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""
            INSERT INTO obyektivka_free_usage (user_id, count, updated_at)
            VALUES (%s, 1, NOW())
            ON CONFLICT (user_id) DO UPDATE
            SET count = obyektivka_free_usage.count + 1,
                updated_at = NOW()
            WHERE obyektivka_free_usage.count < %s
            RETURNING count
        """, (user_id, OBYEKTIVKA_FREE_LIMIT))
        claimed = c.fetchone() is not None
        conn.commit()
        return claimed
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)


def release_obyektivka_free_use(user_id: int) -> None:
    """Yetkazib berilmagan bepul obyektivka uchun avvalgi rezervni qaytaradi."""
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""
            UPDATE obyektivka_free_usage
            SET count = GREATEST(0, count - 1), updated_at = NOW()
            WHERE user_id = %s AND count > 0
        """, (user_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)


def increment_ai_daily_count(user_id: int) -> int:
    """AI savol sonini +1 qiladi va yangi sonni qaytaradi."""
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("""
            INSERT INTO ai_daily_usage (user_id, usage_date, count)
            VALUES (%s, CURRENT_DATE, 1)
            ON CONFLICT (user_id, usage_date)
            DO UPDATE SET count = ai_daily_usage.count + 1
            RETURNING count
        """, (user_id,))
        row = c.fetchone()
        conn.commit()
        return row[0] if row else 1
    finally:
        release_conn(conn)


def delete_user(user_id: int) -> bool:
    """Foydalanuvchini va uning barcha ma'lumotlarini bazadan to'liq o'chiradi."""
    conn = get_conn()
    try:
        c = conn.cursor()
        # Bog'liq jadvallardan o'chirish (FOREIGN KEY CASCADE bo'lmagan hollarda qo'lda)
        c.execute("DELETE FROM ai_daily_usage WHERE user_id = %s", (user_id,))
        c.execute("DELETE FROM generations WHERE user_id = %s", (user_id,))
        c.execute("DELETE FROM transactions WHERE user_id = %s", (user_id,))
        c.execute("DELETE FROM user_topup_state WHERE user_id = %s", (user_id,))
        # Asosiy foydalanuvchi yozuvini o'chirish
        c.execute("DELETE FROM users WHERE user_id = %s RETURNING user_id", (user_id,))
        deleted = c.fetchone()
        conn.commit()
        return deleted is not None
    finally:
        release_conn(conn)


# ─────────────────────────────────────────────
# Broadcast funksiyalari
# ─────────────────────────────────────────────

def save_broadcast_message(session_id: str, user_id: int, message_id: int):
    """Broadcast xabarining message_id sini saqlaydi."""
    conn = get_conn()
    try:
        c = conn.cursor()
        # Session ni qo'shish (agar yo'q bo'lsa)
        c.execute("""
            INSERT INTO broadcast_sessions (session_id)
            VALUES (%s)
            ON CONFLICT (session_id) DO NOTHING
        """, (session_id,))
        # Xabar ID ni saqlash
        c.execute("""
            INSERT INTO broadcast_messages (user_id, message_id)
            VALUES (%s, %s)
        """, (user_id, message_id))
        conn.commit()
    finally:
        release_conn(conn)

def get_last_broadcast_messages():
    """Oxirgi broadcast sessiyasidagi barcha xabarlarni qaytaradi."""
    conn = get_conn()
    try:
        c = conn.cursor()
        # Oxirgi session_id ni topish
        c.execute("SELECT session_id FROM broadcast_sessions ORDER BY sent_at DESC LIMIT 1")
        row = c.fetchone()
        if not row:
            return []
        session_id = row[0]
        # Shu sessiondagi barcha xabarlarni olish
        c.execute("""
            SELECT bm.user_id, bm.message_id
            FROM broadcast_messages bm
            JOIN broadcast_sessions bs ON bs.session_id = %s
            WHERE bm.sent_at >= bs.sent_at - INTERVAL '1 minute'
            ORDER BY bm.id
        """, (session_id,))
        rows = c.fetchall()
        return [{"user_id": r[0], "message_id": r[1]} for r in rows]
    finally:
        release_conn(conn)

def clear_broadcast_messages():
    """Barcha broadcast xabarlarini bazadan tozalaydi."""
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM broadcast_messages")
        c.execute("DELETE FROM broadcast_sessions")
        conn.commit()
    finally:
        release_conn(conn)
