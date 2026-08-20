"""Asosiy modul importida yashirin DB yoki Telegram tarmoq chaqiruvi yo'qligini tekshiradi."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main

assert callable(main.main)
assert callable(main.handle_main_menu_selection)
assert callable(main.admin_broadcast_text_handler)
assert main.SERVICE_PRICES["rezyume"] == 3000
print("MAIN_IMPORT_SMOKE_TEST_OK")
