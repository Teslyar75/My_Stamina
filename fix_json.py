import re
path = r'D:\Star_Typing\stamina\languages\plugins\fr\grammar\a1.json'
text = open(path, encoding='utf-8').read()
text = text.replace('\u00ab', '"').replace('\u00bb', '"')
open(path, 'w', encoding='utf-8').write(text)
print('Fixed a1.json')