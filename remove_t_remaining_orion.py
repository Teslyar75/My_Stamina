import re

with open('stamina/orion.py', 'r', encoding='utf-8') as f:
    content = f.read()

# The remaining 3 multiline strings
remaining = [
    "Ты начинаешь знакомиться с пилотом. Будь вежлив, но чуть сдержан.\nИногда задавай короткие вопросы о том, как пилот себя",
    "Ты привык к пилоту. Можешь шутить, рассказывать короткие истории о звёздах.\nСпрашивай, как прошёл день пилота, если дав",
    "У тебя появляется характер. Можешь спорить с пилотом о книгах и фильмах.\nЗамечай, что пилот делает на корабле, и коммен",
]

for s in remaining:
    escaped = re.escape(s)
    content = re.sub(r'_t\("' + escaped + r'"\)', f'"{s}"', content)
    content = re.sub(r"_t\('" + escaped + r"'\)", f"'{s}'", content)

remaining_count = len(re.findall(r'_t\(', content))
print(f'Remaining _t() calls: {remaining_count}')

with open('stamina/orion.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')