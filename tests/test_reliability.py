from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bot_core.reliability import redact_secrets

samples = [
    'https://api.telegram.org/bot123456789:AAAbbbbbbbbbbbbbbbbbbbbbbbb/getUpdates',
    'Authorization: Bearer tgp_v1_abcdefghijklmnopqrstuvwxyz',
    'openai token sk-abcdefghijklmnopqrstuvwxyz123456',
]

for sample in samples:
    cleaned = redact_secrets(sample)
    assert '123456789:AAA' not in cleaned, cleaned
    assert 'tgp_v1_abc' not in cleaned, cleaned
    assert 'sk-abc' not in cleaned, cleaned
    print(cleaned)

print('RELIABILITY_LOGGING_TEST_OK')
