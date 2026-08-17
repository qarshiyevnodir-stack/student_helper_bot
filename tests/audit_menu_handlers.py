from pathlib import Path
import re

source = Path('main.py').read_text(encoding='utf-8')

# Asosiy ReplyKeyboard tugmalari aniq satrlarini topamiz.
labels = []
for match in re.finditer(r'KeyboardButton\("([^"\\]+)"\)', source):
    label = match.group(1)
    if label not in labels:
        labels.append(label)

# handle_main_menu_selection funksiyasi chegarasini ajratamiz.
start = source.find('async def handle_main_menu_selection')
end = source.find('\nasync def ', start + 1)
handler = source[start:end if end != -1 else len(source)]

print('MENU_LABELS', len(labels))
for label in labels:
    full_count = source.count(label)
    handler_count = handler.count(label)
    status = 'OK' if handler_count else 'MISSING_HANDLER'
    print(f'{status}\t{full_count}\t{label}')

print('\nGLOBAL_HANDLER_DUPLICATES')
for name in ('admin_broadcast_text_handler', 'admin_delete_user_message', 'handle_main_menu_selection'):
    print(f'{name}: {source.count(name)} occurrences')

print('\nRISKY_RUNTIME_OPTIONS')
for needle in ('drop_pending_updates=True', 'logging.basicConfig(', 'add_error_handler('):
    print(f'{needle}: {source.count(needle)}')
