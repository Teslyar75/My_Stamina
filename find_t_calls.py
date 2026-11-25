import re
from pathlib import Path
import pickle

# Find all _t() calls with their file and line
pattern = re.compile(r'_t\([\'"]([^\'"]+)[\'"]\)')
all_calls = []

for py_file in Path('stamina').rglob('*.py'):
    try:
        content = py_file.read_text(encoding='utf-8')
        lines = content.split('\n')
        for i, line in enumerate(lines):
            for match in pattern.finditer(line):
                all_calls.append({
                    'file': str(py_file.relative_to(Path('stamina'))),
                    'line': i + 1,
                    'key': match.group(1),
                    'context': line.strip()[:120]
                })
    except:
        pass

print(f'Total _t() calls: {len(all_calls)}')

# Load master keys
with open('master_keys.pkl', 'rb') as f:
    master_keys = pickle.load(f)

# Find calls with keys NOT in master (these are the added ones)
added_calls = [c for c in all_calls if c['key'] not in master_keys]
print(f'Added _t() calls (not in master): {len(added_calls)}')

# Group by file
from collections import defaultdict
by_file = defaultdict(list)
for c in added_calls:
    by_file[c['file']].append(c)

for file, calls in sorted(by_file.items(), key=lambda x: -len(x[1])):
    print(f'{file}: {len(calls)} calls')
    for c in calls[:5]:
        print(f'  L{c["line"]}: {c["key"][:80]}')
    if len(calls) > 5:
        print(f'  ... and {len(calls) - 5} more')