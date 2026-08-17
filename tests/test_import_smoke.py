from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db
from bot_core.pricing import SERVICE_PRICES, get_slayd_price
from bot_core.reliability import redact_secrets

assert callable(db.init_db)
assert SERVICE_PRICES["rezyume"] == 3000
assert get_slayd_price(38, 30) == 5000
assert "123456789:" not in redact_secrets("bot123456789:AAAbbbbbbbbbbbbbbbbbbbbbbbb")

print("IMPORT_SMOKE_TEST_OK")
