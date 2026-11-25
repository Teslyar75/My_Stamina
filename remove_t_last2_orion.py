with open('stamina/orion.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Line 674-675 (multiline)
old = '_t(\'Ответь одним JSON-массивом без пояснений: [{"bad": "как в тексте", \n' \
      '           \'"good": "как должно быть"}]. Если правок нет — ответь [].\')'
new = '("Ответь одним JSON-массивом без пояснений: [{\\"bad\\": \\"как в тексте\\", ' \
      '\\"good\\": \\"как должно быть\\"}] Если правок нет — ответь [].")'
content = content.replace(old, new)

import re
remaining = len(re.findall(r'_t\(', content))
print(f'Remaining _t() calls: {remaining}')

with open('stamina/orion.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')