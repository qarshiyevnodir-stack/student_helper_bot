"""
db.py — Slidego bot uchun SQLite ma'lumotlar bazasi moduli
Jadvallar:
  - users          : foydalanuvchilar va ularning balansi
  - transactions   : to'lov operatsiyalari (chek yuborish, tasdiqlash)
  - generations    : har bir yaratilgan fayl logi
"""

import sqlite3
import os
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(__file__), "slidego.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Barcha jadvallarni yaratadi (agar mavjud bo'lmasa)."""
    conn = get_conn()
    c = conn.cursor()

    # Foydalanuvchilar jadvali
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY,
            username      TEXT,
            full_name     TEXT,
            balance       INTEGER DEFAULT 0,
            referral_code TEXT UNIQUE,
            referred_by   INTEGER,
            joined_at     TEXT DEFAULT (datetime('now','localtime')),
            last_active   TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    # To'lov operatsiyalari
    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            amount        INTEGER NOT NULL,
            type          TEXT NOT NULL,   -- 'topup' | 'deduct'
            status        TEXT DEFAULT 'pending',  -- 'pending'|'approved'|'rejected'
            screenshot_id TEXT,            -- Telegram file_id
            note          TEXT,
            created_at    TEXT DEFAULT (datetime('now','localtime')),
            updated_at    TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # Generatsiya logi
    c.execute("""
        CREATE TABLE IF NOT EXISTS generations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            service     TEXT NOT NULL,   -- 'slayd'|'mustaqil_ish'|'referat'|'loyiha_ishi'
            topic       TEXT,
            cost        INTEGER NOT NULL,
            created_at  TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # Topup holati jadvali (restart bo'lsa ham yo'qolmaydi)
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_topup_state (
            user_id    INTEGER PRIMARY KEY,
            state      TEXT NOT NULL,
            amount     INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)

    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# Foydalanuvchi CRUD
# ─────────────────────────────────────────────

def get_or_create_user(user_id: int, username: str = None, full_name: str = None,
                       referred_by: int = None) -> dict:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row:
        # last_active yangilash
        c.execute("UPDATE users SET last_active = datetime('now','localtime') WHERE user_id = ?",
                  (user_id,))
        conn.commit()
        result = dict(row)
        conn.close()
        return result

    # Yangi foydalanuvchi
    import random, string
    ref_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    c.execute("""
        INSERT INTO users (user_id, username, full_name, referral_code, referred_by)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, username, full_name, ref_code, referred_by))
    conn.commit()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    result = dict(c.fetchone())
    conn.close()
    return result


def get_user(user_id: int) -> dict | None:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_balance(user_id: int) -> int:
    user = get_user(user_id)
    return user['balance'] if user else 0


def add_balance(user_id: int, amount: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()


def deduct_balance(user_id: int, amount: int) -> bool:
    """Balansdan yechadi. Yetarli bo'lmasa False qaytaradi."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if not row or row['balance'] < amount:
        conn.close()
        return False
    c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()
    return True


def get_all_users(limit: int = 50, offset: int = 0) -> list:
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT user_id, username, full_name, balance, joined_at, last_active
        FROM users ORDER BY joined_at DESC LIMIT ? OFFSET ?
    """, (limit, offset))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_user_by_ref_code(ref_code: str) -> dict | None:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE referral_code = ?", (ref_code,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


# ─────────────────────────────────────────────
# Tranzaksiyalar
# ─────────────────────────────────────────────

def create_topup_request(user_id: int, amount: int, screenshot_id: str) -> int:
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO transactions (user_id, amount, type, status, screenshot_id)
        VALUES (?, ?, 'topup', 'pending', ?)
    """, (user_id, amount, screenshot_id))
    conn.commit()
    tx_id = c.lastrowid
    conn.close()
    return tx_id


def approve_topup(tx_id: int) -> dict | None:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM transactions WHERE id = ? AND status = 'pending'", (tx_id,))
    tx = c.fetchone()
    if not tx:
        conn.close()
        return None
    c.execute("""
        UPDATE transactions SET status = 'approved', updated_at = datetime('now','localtime')
        WHERE id = ?
    """, (tx_id,))
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?",
              (tx['amount'], tx['user_id']))
    conn.commit()
    result = dict(tx)
    conn.close()
    return result


def reject_topup(tx_id: int) -> dict | None:
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM transactions WHERE id = ? AND status = 'pending'", (tx_id,))
    tx = c.fetchone()
    if not tx:
        conn.close()
        return None
    c.execute("""
        UPDATE transactions SET status = 'rejected', updated_at = datetime('now','localtime')
        WHERE id = ?
    """, (tx_id,))
    conn.commit()
    result = dict(tx)
    conn.close()
    return result


def get_pending_topups() -> list:
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT t.*, u.username, u.full_name
        FROM transactions t
        JOIN users u ON t.user_id = u.user_id
        WHERE t.type = 'topup' AND t.status = 'pending'
        ORDER BY t.created_at ASC
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def log_deduction(user_id: int, amount: int, note: str = ""):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO transactions (user_id, amount, type, status, note)
        VALUES (?, ?, 'deduct', 'approved', ?)
    """, (user_id, amount, note))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# Generatsiya logi
# ─────────────────────────────────────────────

def log_generation(user_id: int, service: str, topic: str, cost: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO generations (user_id, service, topic, cost)
        VALUES (?, ?, ?, ?)
    """, (user_id, service, topic, cost))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# Statistika
# ─────────────────────────────────────────────

def get_stats() -> dict:
    conn = get_conn()
    c = conn.cursor()

    today = date.today().isoformat()

    c.execute("SELECT COUNT(*) as cnt FROM users")
    total_users = c.fetchone()['cnt']

    c.execute("SELECT COUNT(*) as cnt FROM users WHERE DATE(joined_at) = ?", (today,))
    new_today = c.fetchone()['cnt']

    c.execute("SELECT COUNT(*) as cnt FROM users WHERE referred_by IS NOT NULL")
    via_referral = c.fetchone()['cnt']

    c.execute("SELECT COUNT(*) as cnt FROM generations")
    total_generations = c.fetchone()['cnt']

    c.execute("SELECT COUNT(*) as cnt FROM generations WHERE DATE(created_at) = ?", (today,))
    generations_today = c.fetchone()['cnt']

    c.execute("""
        SELECT service, COUNT(*) as cnt FROM generations GROUP BY service
    """)
    by_service = {row['service']: row['cnt'] for row in c.fetchall()}

    c.execute("""
        SELECT COALESCE(SUM(amount), 0) as total
        FROM transactions WHERE type = 'topup' AND status = 'approved'
    """)
    total_income = c.fetchone()['total']

    c.execute("""
        SELECT COALESCE(SUM(amount), 0) as total
        FROM transactions WHERE type = 'topup' AND status = 'approved'
        AND DATE(updated_at) = ?
    """, (today,))
    income_today = c.fetchone()['total']

    c.execute("SELECT COUNT(*) as cnt FROM transactions WHERE type='topup' AND status='pending'")
    pending_topups = c.fetchone()['cnt']

    conn.close()
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


# ─────────────────────────────────────────────
# Topup holati (DB da saqlanadi — restart da yo'qolmaydi)
# ─────────────────────────────────────────────

def set_user_topup_state(user_id: int, state: str | None, amount: int = 0):
    """Foydalanuvchining topup holatini DB ga saqlaydi."""
    conn = get_conn()
    c = conn.cursor()
    if state is None:
        c.execute("DELETE FROM user_topup_state WHERE user_id = ?", (user_id,))
    else:
        c.execute("""
            INSERT INTO user_topup_state (user_id, state, amount, updated_at)
            VALUES (?, ?, ?, datetime('now','localtime'))
            ON CONFLICT(user_id) DO UPDATE SET
                state = excluded.state,
                amount = excluded.amount,
                updated_at = datetime('now','localtime')
        """, (user_id, state, amount))
    conn.commit()
    conn.close()


def get_user_topup_state(user_id: int) -> dict | None:
    """Foydalanuvchining topup holatini DB dan oladi."""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT state, amount FROM user_topup_state WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"state": row["state"], "amount": row["amount"]}
    return None


# Modulni import qilganda DB ni ishga tushir
init_db()
