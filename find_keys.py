import re
from pathlib import Path

# Find all _t() calls in stamina/ source
pattern = re.compile(r"_t\(['\"]([^'\"]+)['\"]\)")
all_keys = set()

for py_file in Path('stamina').rglob('*.py'):
    try:
        content = py_file.read_text(encoding='utf-8')
        for match in pattern.finditer(content):
            all_keys.add(match.group(1))
    except:
        pass

print(f'Total _t() keys in source: {len(all_keys)}')

# Load current ru.json
import json
ru = json.loads(Path('stamina/i18n/ru.json').read_text(encoding='utf-8'))
print(f'Keys in ru.json: {len(ru)}')

# Keys in source but not in ru.json
missing_in_ru = all_keys - set(ru.keys())
print(f'Keys in source but not in ru.json: {len(missing_in_ru)}')

# Keys in ru.json but not in source
extra_in_ru = set(ru.keys()) - all_keys
print(f'Keys in ru.json but not in source: {len(extra_in_ru)}')
if extra_in_ru:
    print("Extra keys:", sorted(extra_in_ru)[:20])