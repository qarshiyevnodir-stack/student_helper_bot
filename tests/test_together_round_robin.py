"""Together.ai uch kalitli round-robin navbatini API chaqiruvisiz sinaydi."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["TOGETHER_API_KEY_1"] = "test-key-one"
os.environ["TOGETHER_API_KEY_2"] = "test-key-two"
os.environ["TOGETHER_API_KEY_3"] = "test-key-three"

import utils

utils._together_key_idx[0] = 0
sequence = [utils._get_next_together_key() for _ in range(6)]
expected = [
    "test-key-one", "test-key-two", "test-key-three",
    "test-key-one", "test-key-two", "test-key-three",
]
assert sequence == expected, sequence
print("TOGETHER_THREE_KEY_ROUND_ROBIN_TEST_OK")
