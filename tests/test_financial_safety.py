from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import db


class FakeCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.calls = []
        self.description = [
            ('user_id',), ('amount',), ('id',), ('type',), ('status',),
            ('screenshot_id',), ('note',), ('created_at',), ('updated_at',),
        ]

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class FakeConn:
    def __init__(self, cursor):
        self.cursor_obj = cursor
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def with_fake_db(cursor, fn):
    conn = FakeConn(cursor)
    original_get = db.get_conn
    original_release = db.release_conn
    db.get_conn = lambda: conn
    db.release_conn = lambda _conn: None
    try:
        return fn(), conn
    finally:
        db.get_conn = original_get
        db.release_conn = original_release


# Balans yechish SQL'i bitta atomik UPDATE bo'lishi kerak.
cursor = FakeCursor([(4500,)])
result, conn = with_fake_db(cursor, lambda: db.deduct_balance(10, 500))
assert result is True and conn.committed
sql, params = cursor.calls[0]
assert 'UPDATE users' in sql and 'AND balance >=' in sql and params == (500, 10, 500)

# Ikkinchi parallel so'rovda RETURNING qator bermasa, mablag' yechilmagan deb qaytadi.
cursor = FakeCursor([None])
result, conn = with_fake_db(cursor, lambda: db.deduct_balance(10, 500))
assert result is False and conn.committed

# Chek tasdiqlash UPDATE ichida pending shartini saqlashi kerak.
tx_row = (55, 5000, 99, 'topup', 'approved', 'fileid', None, None, None)
cursor = FakeCursor([tx_row])
result, conn = with_fake_db(cursor, lambda: db.approve_topup(99))
assert result['user_id'] == 55 and conn.committed
approve_sql = cursor.calls[0][0]
assert "WHERE id = %s AND status = 'pending'" in approve_sql
assert 'UPDATE users' in cursor.calls[1][0]

print('FINANCIAL_SAFETY_TEST_OK')
