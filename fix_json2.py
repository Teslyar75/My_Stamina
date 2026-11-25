import json
path = r'D:\Star_Typing\stamina\languages\plugins\fr\grammar\a1.json'
text = open(path, encoding='utf-8').read()

# Fix various problematic quotes
text = text.replace('"собираюсь/поеду делать"', "'собираюсь/поеду делать'")
text = text.replace('"собираюсь/поеду делать"', "'собираюсь/поеду делать'")
text = text.replace('"собираюсь/поеду делать"', "'собираюсь/поеду делать'")

# More systematic: replace any bare double quotes inside JSON string values
# This is tricky - let me just fix the specific known lines
lines = text.split('\n')
for i, line in enumerate(lines):
    # Fix line 263
    if '"subtitle": "Ближайшее будущее: "собираюсь/поеду делать""' in line:
        lines[i] = line.replace('"Ближайшее будущее: "собираюсь/поеду делать""', '"Ближайшее будущее: \'собираюсь/поеду делать\'"')
    # Fix line 268
    if '"text": "Futur proche = aller (présent) + infinitif. Аналог русского "собираюсь/поеду делать". Je vais manger = Я собираюсь есть / Я поем."' in line:
        lines[i] = line.replace('Аналог русского "собираюсь/поеду делать"', "Аналог русского 'собираюсь/поеду делать'")
    # Fix line 271
    if 'Я собираюсь есть. Мы уходим. Они приедут.", "note": "Aller спрягается, второй глагол — инфинитив."' in line and 'example' in line:
        pass  # This one looks OK

text = '\n'.join(lines)
open(path, 'w', encoding='utf-8').write(text)
print('Fixed a1.json more')
"