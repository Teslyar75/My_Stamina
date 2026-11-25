import re

with open('stamina/lounge/docker_reference.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace all _t("...") with just "..." - handling multiline and escaped quotes
# Use a function to handle the replacement
def replace_t(match):
    inner = match.group(1)
    # Handle escaped quotes inside the string
    return inner

# Pattern to match _t("...") or _t('...') - handles escaped quotes
pattern = r'_t\((["\'])(.*?)(?<!\\)\1\)'
# This is tricky with nested quotes. Let's do a more careful approach.

# Better: replace _t("text") with "text" for all occurrences
# We'll use a more robust approach - find all _t(...) and process them

# Actually, let's just do simple string replacement for the common patterns
# The file uses _t("text") consistently

# First remove the import line
content = content.replace('from stamina.i18n import t as _t\n', '')

# Then replace _t("...") with "..." - use regex with DOTALL for multiline
# This pattern matches _t("...") where ... can contain escaped quotes
def replace_t_call(m):
    quote = m.group(1)
    inner = m.group(2)
    return quote + inner + quote

# Use a more precise pattern that handles escaped quotes
# _t("text with \"quotes\"") 
pattern = r'_t\((["\'])((?:(?!\1).|\\.)*)\1\)'

# Since this is complex with regex, let's do iterative replacement for known patterns
# Most are single-line _t("text")

# For now, let's use a simple approach: replace _t(" with " and ") with "
# But we need to be careful about context.

# Actually, let's do a line-by-line approach for safety
lines = content.split('\n')
new_lines = []
for line in lines:
    # Replace _t("text") with "text" 
    # Handle cases like: something = _t("text")
    # We'll replace _t(" with " and ") with " when it's the function call
    new_line = line
    # Replace _t("text") -> "text"  (but careful with nested)
    # Use regex on each line
    new_line = re.sub(r'_t\((["\'])((?:(?!\1).|\\.)*)\1\)', r'\1\2\1', new_line)
    new_lines.append(new_line)

content = '\n'.join(new_lines)

# Also handle multiline _t calls that span multiple lines
# These would not be caught by line-by-line

remaining = len(re.findall(r'_t\(', content))
print(f'Remaining _t() calls: {remaining}')

with open('stamina/lounge/docker_reference.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')