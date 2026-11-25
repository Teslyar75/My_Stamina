import re

with open('stamina/orion.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Use regex to find and replace the specific _t() call
# Match _t('...') where the content contains "JSON-массив"
pattern = r"_t\('Ответь одним JSON-массив[^)]+\)"
match = re.search(pattern, content)
if match:
    print(f'Found: {match.group()[:80]}...')
    # Replace _t('...') with just '...'
    replacement = match.group()[3:-1]  # Remove _t( and )
    content = content[:match.start()] + replacement + content[match.end():]
    print('Replaced')
else:
    print('Not found')

remaining = len(re.findall(r'_t\(', content))
print(f'Remaining _t() calls: {remaining}')

with open('stamina/orion.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')