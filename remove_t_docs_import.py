import re

with open('stamina/docs_import.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the import
content = content.replace('from stamina.i18n import t as _t\n', '')

# Replace all _t("text") with "text" - line by line for safety
lines = content.split('\n')
new_lines = []
for line in lines:
    new_line = re.sub(r'_t\((["\'])((?:(?!\1).|\\.)*)\1\)', r'\1\2\1', line)
    new_lines.append(new_line)

content = '\n'.join(new_lines)

remaining = len(re.findall(r'_t\(', content))
print(f'Remaining _t() calls: {remaining}')

with open('stamina/docs_import.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')