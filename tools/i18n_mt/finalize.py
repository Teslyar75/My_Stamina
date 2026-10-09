import json, re
REPO='/workspace/qs/repo/stamina/i18n'
ru=json.load(open(f'{REPO}/ru.json'))
keys=json.load(open('/workspace/i18n_mt/key_screens.json'))
PH=re.compile(r'\{[^{}]*\}')
EXTRA={
 'en':{'Кадет':'Cadet','Пилот-стажёр':'Pilot trainee','Мичман':'Midshipman','Лейтенант':'Lieutenant','Капитан-лейтенант':'Lieutenant commander','Капитан':'Captain','Коммодор':'Commodore','Адмирал флота':'Fleet admiral','ДОСКА ПОЧЁТА':'HONOR BOARD','ВХОД В КАБИНУ':'COCKPIT ENTRY','ГИПЕРДРАЙВ':'HYPERDRIVE','БИБЛИОТЕКА':'LIBRARY','ТРЕНАЖЁРЫ':'TRAINERS','Библиотека':'Library','ОБЗОР':'OVERVIEW','ЗВЁЗДНЫЕ КАРТЫ':'STAR CARDS','СКАНЕР':'SCANNER','ПРОВЕРКА СИСТЕМ':'SYSTEMS CHECK','ОТСЕКИ':'COMPARTMENTS','ЖУРНАЛ':'LOG','ОТКРЫТЬ ФАЙЛ…':'OPEN FILE…','ОТКРЫТЬ PDF…':'OPEN PDF…','＋ ОТКРЫТЬ PDF':'＋ OPEN PDF','＋ ОТКРЫТЬ .TXT':'＋ OPEN .TXT','русский':'Russian','украинский':'Ukrainian','английский':'English','немецкий':'German','Ё → Е':'Ё → Е (Russian)'},
 'uk':{'Кадет':'Кадет','Пилот-стажёр':'Пілот-стажист','Мичман':'Мічман','Лейтенант':'Лейтенант','Капитан-лейтенант':'Капітан-лейтенант','Капитан':'Капітан','Коммодор':'Коммодор','Адмирал флота':'Адмірал флоту','ДОСКА ПОЧЁТА':'ДОШКА ПОШАНИ','ВХОД В КАБИНУ':'ВХІД ДО КАБІНИ','ГИПЕРДРАЙВ':'ГІПЕРДРАЙВ','БИБЛИОТЕКА':'БІБЛІОТЕКА','ТРЕНАЖЁРЫ':'ТРЕНАЖЕРИ','Библиотека':'Бібліотека','ОБЗОР':'ОГЛЯД','ЗВЁЗДНЫЕ КАРТЫ':'ЗОРЯНІ КАРТИ','СКАНЕР':'СКАНЕР','ПРОВЕРКА СИСТЕМ':'ПЕРЕВІРКА СИСТЕМ','ОТСЕКИ':'ВІДСІКИ','ЖУРНАЛ':'ЖУРНАЛ','ОТКРЫТЬ ФАЙЛ…':'ВІДКРИТИ ФАЙЛ…','ОТКРЫТЬ PDF…':'ВІДКРИТИ PDF…','＋ ОТКРЫТЬ PDF':'＋ ВІДКРИТИ PDF','＋ ОТКРЫТЬ .TXT':'＋ ВІДКРИТИ .TXT','русский':'російська','украинский':'українська','английский':'англійська','немецкий':'німецька'},
 'de':{'Кадет':'Kadett','Пилот-стажёр':'Pilotenanwärter','Мичман':'Fähnrich','Лейтенант':'Leutnant','Капитан-лейтенант':'Kapitänleutnant','Капитан':'Kapitän','Коммодор':'Kommodore','Адмирал флота':'Flottenadmiral','ДОСКА ПОЧЁТА':'EHRENTAFEL','ВХОД В КАБИНУ':'EINSTIEG INS COCKPIT','ГИПЕРДРАЙВ':'HYPERANTRIEB','БИБЛИОТЕКА':'BIBLIOTHEK','ТРЕНАЖЁРЫ':'TRAINER','Библиотека':'Bibliothek','ОБЗОР':'ÜBERSICHT','ЗВЁЗДНЫЕ КАРТЫ':'STERNKARTEN','СКАНЕР':'SCANNER','ПРОВЕРКА СИСТЕМ':'SYSTEMCHECK','ОТСЕКИ':'ABTEILE','ЖУРНАЛ':'LOG','ОТКРЫТЬ ФАЙЛ…':'DATEI ÖFFNEN…','ОТКРЫТЬ PDF…':'PDF ÖFFNEN…','＋ ОТКРЫТЬ PDF':'＋ PDF ÖFFNEN','＋ ОТКРЫТЬ .TXT':'＋ .TXT ÖFFNEN','русский':'Russisch','украинский':'Ukrainisch','английский':'Englisch','немецкий':'Deutsch'},
}
for lang in ('en','uk','de'):
    mt=json.load(open(f'/workspace/i18n_mt/{lang}.json'))
    hand=[l.rstrip('\n').replace('\\n','\n') for l in open(f'/workspace/i18n_mt/hand_{lang}.txt',encoding='utf-8')]
    assert len(hand)==len(keys)
    out={}
    for k in ru:
        v=mt.get(k) or ''
        if v:
            if not k.rstrip().endswith(('.','!','?','…')) and v.rstrip().endswith('.') and not v.rstrip().endswith('...'):
                v=v.rstrip()[:-1]
            lead=len(k)-len(k.lstrip(' ')); trail=len(k)-len(k.rstrip(' '))
            v=' '*lead+v.strip(' ')+' '*trail
            if sorted(PH.findall(v))!=sorted(PH.findall(k)): v=''
        if v: out[k]=v
    out.update({k:v for k,v in zip(keys,hand) if k in ru})
    out.update({k:v for k,v in EXTRA[lang].items() if k in ru})
    json.dump(dict(sorted(out.items())),open(f'{REPO}/{lang}.json','w'),ensure_ascii=False,indent=1)
    print(lang,len(out),'/',len(ru))

# --- второй проход: глоссарий корабельных/печатных терминов ---
RULES = [
 # (условие по русскому ключу, язык, что, на что)
 (r'(?i)печат', 'en', r'\bPRINTING\b', 'TYPING'), (r'(?i)печат', 'en', r'\bPRINT\b', 'TYPE'),
 (r'(?i)печат', 'en', r'\bPrinting\b', 'Typing'), (r'(?i)печат', 'en', r'\bPrint\b', 'Typing'),
 (r'(?i)печат', 'en', r'\bprinting\b', 'typing'), (r'(?i)печат', 'en', r'\bprint\b', 'typing'),
 (r'(?i)печат', 'en', r'SEAL', 'TYPING'),
 (r'(?i)печат', 'de', r'AUSDRUCKEN|DRUCKEN', 'TIPPEN'), (r'(?i)печат', 'de', r'Ausdrucken|Drucken', 'Tippen'),
 (r'(?i)печат', 'de', r'\bDruck von\b', 'Tippen mit'), (r'(?i)печат', 'de', r'Drucktext', 'Übungstext'),
 (r'(?i)печат', 'de', r'SIEGELS', 'TIPPENS'), (r'(?i)печат', 'de', r'DRUCKEREI', 'TIPP-POSITION'),
 (r'зн/мин|ЗН/МИН', 'en', r'(?i)\b(nm|ft|w|z)/min\b', 'cpm'), (r'зн/мин', 'de', r'(?i)\b(nm|ft|w)/min\b', 'Z/min'),
 (r'зн/мин', 'en', r'Z/min', 'cpm'),
 (r'сл/мин|СЛ/МИН', 'en', r'(?i)\b(l|s|sl|cf)/min\b', 'wpm'), (r'сл/мин|СЛ/МИН', 'de', r'(?i)\b(l|s|sl|cf)/min\b', 'W/min'),
 (r'(?i)клавиш', 'de', r'Schlüssel\b', 'Tasten'), (r'(?i)клавиш', 'de', r'SCHLÜSSEL\b', 'TASTEN'),
 (r'(?i)клавиш', 'de', r'Schlüssels\b', 'Taste'),
 (r'РЕКОРД|Рекорд', 'de', r'DATENSATZ|AUFZEICHNUNG|AKKORD', 'REKORD'), (r'РЕКОРД', 'en', r'CHORD', 'RECORD'),
 (r'(?i)знаю', 'en', r'I know\.?', 'known'), (r'(?i)знаю', 'de', r'Ich weiß\.?', 'bekannt'), (r'(?i)знаю', 'uk', r'Я знаю', 'знаю'),
 (r'«знаю»', 'en', r'"know"', '"known"'), (r'«знаю»', 'de', r'"wissen"', '„bekannt“'),
 (r'(?i)серия', 'en', r'(?i)\bseries\b', 'STREAK'), (r'(?i)серия', 'de', r'\bREIHE\b', 'SERIE'), (r'(?i)серия', 'de', r'\bReihe\b', 'Serie'),
 (r'//', 'en', r'/ /', '//'), (r'//', 'de', r'/ /', '//'), (r'//', 'uk', r'/ /', '//'),
 (r'(?i)звание', 'de', r'\bTITEL\b', 'DIENSTGRAD'), (r'(?i)звание', 'en', r'\bTITLE\b', 'RANK'),
]
MORE = {
 'en': {'Стыковка':'Docking','Притяжение':'Gravity','Домашний ряд':'Home row','Нижний отсек I':'Lower bay I','Нижний отсек II':'Lower bay II','Гиперпрыжок':'Hyperjump','Цифры':'Digits','новые клавиши: {0}':'new keys: {0}','Каждая миссия добавляет новые клавиши. Пройдите с точностью от {0:.0f}%, чтобы открыть следующую. Звёзды дают за точность и скорость.':'Each mission adds new keys. Finish with at least {0:.0f}% accuracy to unlock the next one. Stars are awarded for accuracy and speed.','Пока мало данных: пройдите пару миссий,\nи бортовой компьютер найдёт слабые клавиши.':'Not enough data yet: fly a couple of missions,\nand the onboard computer will find your weak keys.','РЕКОРДА ЕЩЁ НЕТ':'NO RECORD YET','ЧТЕНИЕ  слово {0:,} / {1:,} · {2}\nПЕЧАТЬ  ':'READING  word {0:,} / {1:,} · {2}\nTYPING  ','\nСКОРОСТЬ СТАРТА  {0} сл/мин':'\nSTART SPEED  {0} wpm','ОРИГИНАЛ ПРИВЯЗАН — позиции чтения и печати сохранены':'ORIGINAL ATTACHED — reading and typing positions kept','В ПЕЧАТИ ВЫ ДАЛЬШЕ: {0:.0f}% · S — ПРОДОЛЖИТЬ С ЭТОГО МЕСТА':'YOU ARE FURTHER IN TYPING: {0:.0f}% · S — CONTINUE FROM HERE','Ведущая строка без возвратов':'Guided line without regressions','Распознаю речь…':'Recognizing speech…','◌ Распознаю…':'◌ Recognizing…','● скорость, зн/мин':'● speed, cpm','⚙ РЕМОНТ СЛАБЫХ КЛАВИШ':'⚙ REPAIR WEAK KEYS','СЕРИЯ ДНЕЙ / ЛУЧШАЯ':'DAY STREAK / BEST','ЗВЁЗДНАЯ КАРТА МИССИЙ':'MISSION STAR MAP','РУССКИЙ  ЙЦУКЕН':'RUSSIAN  ЙЦУКЕН','ЭФФЕКТИВНАЯ СКОРОСТЬ':'EFFECTIVE SPEED','эфф. сл/мин':'eff. wpm','Чтение 500 сл/мин с пониманием':'Reading 500 wpm with comprehension','Данных пока мало.\nПечатайте —\nкомпьютер считает\nошибки по каждой\nклавише.':'Not enough data yet.\nKeep typing —\nthe computer counts\nerrors for every\nkey.','не начат':'not started','слов: {0}, карточек: {1}, XP: {2}':'words: {0}, cards: {1}, XP: {2}','слов · речь {0} %':'words · speech {0} %','ИТОГ: {0} сл. за {1} мс · верно {2}/{3}  {4}{5}  +{6} XP':'RESULT: {0} words in {1} ms · correct {2}/{3}  {4}{5}  +{6} XP'},
 'de': {'Стыковка':'Andocken','Притяжение':'Schwerkraft','Домашний ряд':'Grundreihe','Верхний ряд':'Obere Reihe','Нижний ряд':'Untere Reihe','Нижний отсек I':'Unterdeck I','Нижний отсек II':'Unterdeck II','Гиперпрыжок':'Hypersprung','Цифры':'Ziffern','новые клавиши: {0}':'neue Tasten: {0}','Каждая миссия добавляет новые клавиши. Пройдите с точностью от {0:.0f}%, чтобы открыть следующую. Звёзды дают за точность и скорость.':'Jede Mission bringt neue Tasten. Schließe sie mit mindestens {0:.0f}% Genauigkeit ab, um die nächste freizuschalten. Sterne gibt es für Genauigkeit und Tempo.','Пока мало данных: пройдите пару миссий,\nи бортовой компьютер найдёт слабые клавиши.':'Noch zu wenige Daten: fliege ein paar Missionen,\ndann findet der Bordcomputer deine schwachen Tasten.','РЕКОРДА ЕЩЁ НЕТ':'NOCH KEIN REKORD','ЧТЕНИЕ  слово {0:,} / {1:,} · {2}\nПЕЧАТЬ  ':'LESEN  Wort {0:,} / {1:,} · {2}\nTIPPEN  ','\nСКОРОСТЬ СТАРТА  {0} сл/мин':'\nSTARTTEMPO  {0} W/min','ОРИГИНАЛ ПРИВЯЗАН — позиции чтения и печати сохранены':'ORIGINAL VERKNÜPFT — Lese- und Tipp-Position bleiben erhalten','В ПЕЧАТИ ВЫ ДАЛЬШЕ: {0:.0f}% · S — ПРОДОЛЖИТЬ С ЭТОГО МЕСТА':'BEIM TIPPEN BIST DU WEITER: {0:.0f}% · S — HIER WEITERMACHEN','Ведущая строка без возвратов':'Führungszeile ohne Rücksprünge','Распознаю речь…':'Sprache wird erkannt…','◌ Распознаю…':'◌ Erkenne…','● скорость, зн/мин':'● Tempo, Z/min','⚙ РЕМОНТ СЛАБЫХ КЛАВИШ':'⚙ SCHWACHE TASTEN REPARIEREN','СЕРИЯ ДНЕЙ / ЛУЧШАЯ':'TAGESSERIE / BESTE','ЗВЁЗДНАЯ КАРТА МИССИЙ':'STERNKARTE DER MISSIONEN','РУССКИЙ  ЙЦУКЕН':'RUSSISCH  ЙЦУКЕН','ЭФФЕКТИВНАЯ СКОРОСТЬ':'EFFEKTIVES TEMPO','эфф. сл/мин':'eff. W/min','Чтение 500 сл/мин с пониманием':'Lesen mit 500 W/min und Verständnis','ЛУЧШАЯ СКОРОСТЬ':'BESTES TEMPO','ЛУЧШЕЕ: ':'BESTWERT: ','Данных пока мало.\nПечатайте —\nкомпьютер считает\nошибки по каждой\nклавише.':'Noch zu wenige Daten.\nTippe weiter —\nder Computer zählt\nFehler für jede\nTaste.','цифра на клавише — % ошибок; зелёный — хорошо, красный — нужен ремонт':'Zahl auf der Taste — % Fehler; grün — gut, rot — Reparatur nötig','Слабые клавиши: {0}\nУпражнение из слов с этими буквами.':'Schwache Tasten: {0}\nÜbung aus Wörtern mit diesen Buchstaben.','Ремонт систем':'Systemreparatur','не начат':'nicht begonnen','НАЧАТЬ ЗАНЯТИЕ':'TRAINING STARTEN','УРОВЕНЬ':'STUFE','слов: {0}, карточек: {1}, XP: {2}':'Wörter: {0}, Karten: {1}, XP: {2}','слов · речь {0} %':'Wörter · Sprechen {0} %','{0} сл · {1} мс':'{0} W · {1} ms','ИТОГ: {0} сл. за {1} мс · верно {2}/{3}  {4}{5}  +{6} XP':'ERGEBNIS: {0} W in {1} ms · richtig {2}/{3}  {4}{5}  +{6} XP',' · ↗ К {0}':' · ↗ ZU {0}','{0} · {1} · {2} сл.':'{0} · {1} · {2} W.'},
 'uk': {'Стыковка':'Стикування','Притяжение':'Тяжіння','Домашний ряд':'Основний ряд','Гиперпрыжок':'Гіперстрибок','не начат':'не розпочато','сл/мин':'сл/хв','{0} сл/мин':'{0} сл/хв',' сл/мин':' сл/хв','зн/мин':'зн/хв',' зн/мин':' зн/хв','цель {0} зн/мин':'мета {0} зн/хв','РЕКОРДА ЕЩЁ НЕТ':'РЕКОРДУ ЩЕ НЕМАЄ','Распознаю речь…':'Розпізнаю мовлення…','◌ Распознаю…':'◌ Розпізнаю…','ШИРИНА ПОЛЯ: {0} знаков  {1}{2}  +{3} XP':'ШИРИНА ПОЛЯ: {0} знаків  {1}{2}  +{3} XP'},
}
FINGERS={'en': {'левый мизинец': 'left pinky', 'левый безымянный': 'left ring finger', 'левый средний': 'left middle finger', 'левый указательный': 'left index finger', 'правый указательный': 'right index finger', 'правый средний': 'right middle finger', 'правый безымянный': 'right ring finger', 'правый мизинец': 'right pinky', 'большой палец': 'thumb'}, 'de': {'левый мизинец': 'linker kleiner Finger', 'левый безымянный': 'linker Ringfinger', 'левый средний': 'linker Mittelfinger', 'левый указательный': 'linker Zeigefinger', 'правый указательный': 'rechter Zeigefinger', 'правый средний': 'rechter Mittelfinger', 'правый безымянный': 'rechter Ringfinger', 'правый мизинец': 'rechter kleiner Finger', 'большой палец': 'Daumen'}, 'uk': {'левый мизинец': 'лівий мізинець', 'левый безымянный': 'лівий безіменний', 'левый средний': 'лівий середній', 'левый указательный': 'лівий вказівний', 'правый указательный': 'правий вказівний', 'правый средний': 'правий середній', 'правый безымянный': 'правий безіменний', 'правый мизинец': 'правий мізинець', 'большой палец': 'великий палець'}}
for lang in ('en','uk','de'):
    MORE[lang].update(FINGERS[lang])
    p=f'{REPO}/{lang}.json'; d=json.load(open(p))
    for cond, lg, a, b in RULES:
        if lg != lang: continue
        for k in list(d):
            if re.search(cond, k): d[k]=re.sub(a, b, d[k])
    d.update({k:v for k,v in MORE[lang].items() if k in ru})
    json.dump(dict(sorted(d.items())),open(p,'w'),ensure_ascii=False,indent=1)
print('glossary ok')
