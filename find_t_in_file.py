import re
import sys

filepath = sys.argv[1] if len(sys.argv) > 1 else 'stamina/orion.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

pattern = re.compile(r"_t\(['\"]([^'\"]+)['\"]\)")
for i, match in enumerate(pattern.finditer(content)):
    line = content[:match.start()].count('\n') + 1
    print(f'L{line}: {match.group(1)[:120]}')