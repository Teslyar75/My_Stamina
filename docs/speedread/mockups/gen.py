HEAD='''<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>{title}</title><link rel="stylesheet" href="hud.css"><link rel="stylesheet" href="sr.css"><style>{css}</style></head><body>
<div class="hdr">
 <div class="logo"><div class="hex"><i>★</i></div><div><b>STAR TYPING</b><small>ПУЛЬТ ПИЛОТА · ТРЕНАЖЁР ПЕЧАТИ</small></div></div>
 <span class="btn"><span>Мостик</span></span><span class="btn"><span>Миссии</span></span><span class="btn"><span>Свой текст</span></span><span class="btn"><span>Бортжурнал</span></span><span class="btn"><span>Английский</span></span><span class="btn act"><span>Скорочтение</span></span><span class="btn"><span>Настройки</span></span>
 <div class="sp"></div><div class="rank">★ МИЧМАН<br><span class="mono">404 / 700 XP</span></div><span class="btn amber"><span>? F1</span></span><span class="btn"><span>♪ Звук вкл</span></span><span class="clock">18:40</span>
</div>
<div class="hline"></div>
<div class="subtabs">{sub}</div>
'''
TABS=["Обзор","Гипердрайв","Тренажёры","Библиотека","Журнал","Настройки"]
def sub(active):
    return "".join(f'<span class="btn{" act" if t==active else ""}"><span>{t}</span></span>' for t in TABS)
def page(fn,title,active,css,body,note="Макет · отсек «СКОРОЧТЕНИЕ» · палитра и шрифты Star Typing"):
    h=HEAD.format(title=title,css=css,sub=sub(active)) if active else HEAD.split('<div class="hdr">')[0].format(title=title,css=css)
    open(fn,"w").write(h+body+f'<div class="note">{note}</div></body></html>')

# ---------- 1. reader running (focus mode, header hidden) ----------
page("sr-1-reader-running.html","Гипердрайв — чтение",None,'''
body{height:800px}
.top{display:flex;align-items:center;gap:14px;padding:12px 20px;opacity:.55}
.top .t{font:700 9pt var(--font-hud);letter-spacing:.06em;text-transform:uppercase;color:var(--cyan)}
.view{position:absolute;left:40px;right:40px;top:120px;height:470px}
.view .in{background:var(--bg-2)}
.wpm{position:absolute;right:30px;bottom:26px;text-align:right}
.wpm b{font:700 26pt var(--font-mono);color:var(--cyan)}.wpm small{display:block;font:700 8pt var(--font-hud);color:var(--muted);letter-spacing:.06em}
.foot{position:absolute;left:40px;right:40px;bottom:120px}
.hint{position:absolute;left:0;right:0;bottom:44px;text-align:center;font:700 9pt var(--font-hud);color:var(--faint);letter-spacing:.08em}
''','''
<div class="top"><div class="hex" style="width:26px;height:26px"><i style="width:22px;height:22px;font-size:11pt">★</i></div><span class="t">Гипердрайв · Свой текст · «1984» (рус.)</span><div class="sp"></div><span class="t" style="color:var(--muted)">режим фокуса · шапка скрыта</span></div>
<div class="pnl view dim"><span class="tl"></span><span class="br"></span><div class="in"><div class="stage">
 <span class="tick" style="top:120px;height:44px;background:var(--cyan)"></span>
 <span class="hairline" style="top:166px"></span>
 <div class="orp" style="--fs:66pt"><span class="l">хо</span><span class="c">л</span><span class="r">одный</span></div>
 <span class="hairline" style="bottom:166px"></span>
 <span class="tick" style="bottom:120px;height:44px;background:var(--cyan)"></span>
 <div class="wpm"><b>452</b><small>СЛОВ / МИН · ↗ К 600</small></div>
</div></div></div>
<div class="foot">
 <div class="ramp"><span>Маршрут</span><span class="mono" style="color:var(--cyan)">1 248 / 9 806 слов · 13%</span><div class="sp"></div><span>Разгон</span><span class="mono" style="color:var(--amber)">+10 слов/мин каждые 30 с</span></div>
 <div class="bar" style="margin-top:6px"><i style="width:13%"></i></div>
</div>
<div class="hint">ПРОБЕЛ — ПАУЗА · ↑ ↓ — СКОРОСТЬ · ← — НАЗАД НА ПРЕДЛОЖЕНИЕ · ESC — ВЫХОД</div>
''')

# ---------- 2. reader paused ----------
page("sr-2-reader-paused.html","Гипердрайв — пауза","Гипердрайв",'''
.grid{display:grid;grid-template-columns:1fr 330px;gap:12px}
.ctx .in{background:var(--bg-2);padding:34px 40px 18px}
.ctx p{font:13.5pt/1.5 var(--font-hud);color:var(--muted)}
.ctx p.dim{color:var(--faint)}
.cur{color:var(--text);background:color-mix(in srgb,var(--red) 18%,var(--bg));border-bottom:2px solid var(--red);padding:0 4px}
.cur em{font-style:normal;color:var(--red)}
.paused{font:700 11pt var(--font-hud);color:var(--amber);letter-spacing:.12em;text-align:center;margin:10px 0 12px}
.spd{display:flex;align-items:center;justify-content:center;gap:12px;margin:6px 0 4px}
.spd .btn{width:52px;height:52px;font-size:16pt;padding:0}
.spd .val{text-align:center}.spd .val b{display:block;font:700 34pt var(--font-mono);color:var(--cyan);line-height:1}.spd .val small{font:700 8pt var(--font-hud);color:var(--muted)}
.row{display:flex;align-items:center;justify-content:space-between;margin:6px 0}
.fs{display:flex;align-items:center;gap:8px}.fs .btn{height:28px;padding:0 9px}
.fs b{font:700 13pt var(--font-mono);color:var(--cyan);min-width:42px;text-align:center}
.tog{display:inline-block;width:36px;height:16px;border:1px solid var(--green);background:var(--green-dim);position:relative}.tog::after{content:"";position:absolute;right:2px;top:2px;width:10px;height:10px;background:var(--green)}
.tog.off{border-color:var(--line-hi);background:var(--bg-2)}.tog.off::after{left:2px;right:auto;background:var(--faint)}
.acts{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
''','''
<div class="wrap"><div class="grid">
 <div class="pnl ctx amber" style="height:560px"><span class="tl"></span><span class="br"></span><span class="ttl">Обзор контекста · пауза</span><span class="st muted">Свой текст · «1984» (рус.) · 13%</span><div class="in">
  <p class="dim">…Уинстон Смит, прижав подбородок к груди и ёжась от омерзительного ветра, быстро шмыгнул в стеклянную дверь жилого дома «Победа», но всё же вихрь песка и пыли успел ворваться вместе с ним.</p>
  <p style="margin-top:14px">В вестибюле пахло варёной капустой и старыми половиками. Против входа на стене висел цветной плакат, слишком большой для помещения.</p>
  <div class="paused">❚❚ &nbsp;ПАУЗА · ОСТАНОВКА НА СЛОВЕ 1 248</div>
  <p style="color:var(--text)">Был яркий <span class="cur">хо<em>л</em>одный</span> апрельский день, и часы пробили тринадцать.</p>
  <p style="margin-top:14px">На плакате было изображено громадное, больше метра в ширину, лицо: лицо человека лет сорока пяти, с густыми чёрными усами, грубое, но по-мужски привлекательное.</p>
  <p class="dim" style="margin-top:14px">Уинстон направился к лестнице. К лифту не стоило и подходить. Он даже в лучшие времена редко работал…</p>
 </div></div>
 <div style="display:grid;gap:12px;align-content:start">
  <div class="pnl" style="height:170px"><span class="tl"></span><span class="br"></span><span class="ttl">Скорость</span><span class="st" style="color:var(--amber)">разгон вкл</span><div class="in">
   <div class="spd"><span class="btn"><span>▼</span></span><div class="val"><b>450</b><small>СЛОВ / МИН</small></div><span class="btn act"><span>▲</span></span></div>
   <div class="ramp" style="justify-content:center;margin-top:8px"><span>старт 300</span><span class="mono" style="color:var(--amber)">→ цель 600</span><span>· шаг ±25 <span class="kbd">↑</span><span class="kbd">↓</span></span></div>
  </div></div>
  <div class="pnl" style="height:252px"><span class="tl"></span><span class="br"></span><span class="ttl">Настройки полёта</span><div class="in">
   <div class="row"><span class="lbl">Шрифт</span><div class="fs"><span class="btn"><span>A−</span></span><b>66</b><span class="btn"><span>A+</span></span></div></div>
   <div class="row"><span class="lbl">Слов за кадр</span><div class="seg2"><span class="btn act"><span>1</span></span><span class="btn"><span>2</span></span><span class="btn"><span>3</span></span><span class="btn"><span>4</span></span><span class="btn"><span>5</span></span></div></div>
   <div class="row"><span class="lbl">Красная буква (ORP)</span><span class="tog"></span></div>
   <div class="row"><span class="lbl">Паузы на знаках препинания</span><span class="tog"></span></div>
   <div class="row"><span class="lbl">Плавный разгон</span><span class="tog"></span></div>
   <div class="row"><span class="lbl">Озвучка слов</span><span class="tog off"></span></div>
  </div></div>
  <div class="pnl dim" style="height:114px"><span class="tl"></span><span class="br"></span><span class="ttl">Телеметрия сессии</span><div class="in" style="padding-top:24px">
   <div class="ro"><span class="l">Время в полёте</span><span class="v">02:51</span></div>
   <div class="ro" style="--c:var(--amber)"><span class="l">Средняя скорость</span><span class="v">402</span></div>
  </div></div>
 </div>
</div>
<div class="acts" style="margin-top:0;flex-wrap:nowrap"><span class="btn amber big act"><span>▶ Продолжить</span><span class="k">Пробел</span></span><span class="btn big"><span>⟲ Назад</span><span class="k">←</span></span><span class="btn big"><span>⇤ В начало</span><span class="k">Home</span></span><span class="btn big green"><span>✓ Финиш + тест</span><span class="k">Enter</span></span><span class="btn big red"><span>Выход</span><span class="k">Esc</span></span></div>
</div>
''')

# ---------- 3. Schulte 5x5 ----------
import random
random.seed(7); nums=list(range(1,26)); random.shuffle(nums)
found=set(range(1,9))
cells="".join(f'<div class="cell{" ok" if n in found else ""}">{n}</div>' for n in nums)
page("sr-3-schulte-5x5.html","Тренажёр — таблица Шульте 5×5","Тренажёры",'''
.strip{display:flex;align-items:center;gap:12px;margin:0 14px 12px;padding-left:12px;border-left:5px solid var(--amber)}
.strip h1{font:700 14pt var(--font-hud);text-transform:uppercase}
.grid{display:grid;grid-template-columns:260px 1fr 260px;gap:12px}
.board .in{display:grid;place-items:center;background:var(--bg-2)}
.tbl{position:relative;display:grid;grid-template-columns:repeat(5,92px);grid-template-rows:repeat(5,92px);gap:4px}
.cell{display:grid;place-items:center;font:700 30pt var(--font-mono);color:var(--text);background:var(--panel);border:1px solid var(--line-hi)}
.cell.ok{color:var(--faint);border-color:var(--line)}
.dot{position:absolute;left:50%;top:50%;width:10px;height:10px;margin:-5px;border-radius:50%;background:var(--red);box-shadow:0 0 12px var(--red)}
.target{text-align:center;margin-top:4px}.target b{display:block;font:700 54pt var(--font-mono);color:var(--amber);line-height:1}
.timer{font:700 34pt var(--font-mono);color:var(--cyan);text-align:center;margin:6px 0}
.lvl{display:grid;grid-template-columns:repeat(5,1fr);gap:4px;margin-top:6px}.lvl .btn{height:28px;padding:0;font-size:8.5pt}
.rule{font:9.5pt/1.45 var(--font-hud);color:var(--muted)}
''',f'''
<div class="strip"><div><h1>Тренажёр E-SHL · Таблица Шульте 5×5</h1><span class="muted" style="font-size:8pt">← тренажёры обзора · найди числа 1→25 по порядку, взгляд держи на красной точке в центре</span></div></div>
<div class="wrap"><div class="grid">
 <div style="display:grid;gap:12px;align-content:start">
  <div class="pnl amber" style="height:230px"><span class="tl"></span><span class="br"></span><span class="ttl">Найди</span><div class="in"><div class="target"><b>9</b><span class="lbl">следующее: 10</span></div>
   <div class="bar" style="margin-top:16px"><i style="width:32%;background:var(--amber)"></i></div><div class="ramp" style="margin-top:6px"><span>найдено</span><div class="sp"></div><span class="mono" style="color:var(--amber)">8 / 25</span></div></div></div>
  <div class="pnl dim" style="height:250px"><span class="tl"></span><span class="br"></span><span class="ttl">Режим</span><div class="in">
   <div class="lbl">Размер</div><div class="lvl"><span class="btn"><span>3×3</span></span><span class="btn"><span>4×4</span></span><span class="btn act"><span>5×5</span></span><span class="btn"><span>6×6</span></span><span class="btn"><span>7×7</span></span></div>
   <div class="lbl" style="margin-top:12px">Символы</div><div class="lvl" style="grid-template-columns:repeat(3,1fr)"><span class="btn act"><span>1–25</span></span><span class="btn"><span>А–Я</span></span><span class="btn"><span>A–Z</span></span></div>
   <div class="lbl" style="margin-top:12px">Вариант</div><div class="lvl" style="grid-template-columns:repeat(2,1fr)"><span class="btn act"><span>Классика</span></span><span class="btn red"><span>Горбов</span></span></div>
  </div></div>
 </div>
 <div class="pnl board" style="height:530px"><span class="tl"></span><span class="br"></span><span class="ttl">Поле обзора</span><span class="st" style="color:var(--green)">● идёт · без ошибок</span><div class="in"><div class="tbl">{cells}<span class="dot"></span></div></div></div>
 <div style="display:grid;gap:12px;align-content:start">
  <div class="pnl" style="height:150px"><span class="tl"></span><span class="br"></span><span class="ttl">Таймер</span><div class="in"><div class="timer">00:12.4</div><div class="ramp" style="justify-content:center"><span>рекорд 5×5</span><span class="mono" style="color:var(--green)">00:31.8</span></div></div></div>
  <div class="pnl dim" style="height:200px"><span class="tl"></span><span class="br"></span><span class="ttl">Телеметрия</span><div class="in">
   <div class="ro" style="--c:var(--red)"><span class="l">Ошибки</span><span class="v">0</span></div>
   <div class="ro" style="--c:var(--amber)"><span class="l">Темп, с / число</span><span class="v">1.55</span></div>
   <div class="ro" style="--c:var(--green)"><span class="l">Норма ★★★</span><span class="v">≤ 35 с</span></div></div></div>
  <div class="pnl dim" style="height:166px"><span class="tl"></span><span class="br"></span><span class="ttl">Правило</span><div class="in"><p class="rule">Смотри в центр. Находи числа периферийным зрением, щёлкай мышью или вводи с клавиатуры. Ошибка +2 с. Числа после нахождения гаснут (настройка).</p></div></div>
 </div>
</div>
<div style="display:flex;gap:8px;justify-content:center"><span class="btn amber big"><span>⟲ Заново</span><span class="k">R</span></span><span class="btn big"><span>❚❚ Пауза</span><span class="k">Пробел</span></span><span class="btn big red"><span>Выход</span><span class="k">Esc</span></span></div>
</div>
''')

# ---------- 4. overview ----------
ex=[("R-HYP","Гипердрайв","Чтение по слову (RSVP), красная буква","452 сл/мин","★★☆","amber"),
("E-SHL","Таблица Шульте","Числа 1→N, 3×3…7×7","5×5 · 31.8 с","★★★",""),
("E-GRB","Таблица Горбова","Красные ↑ / чёрные ↓ чередуя","5×5 · 58.0 с","★☆☆",""),
("E-PYR","Пирамида","Расширение поля зрения по клину","ширина 34 зн.","★★☆",""),
("E-TAC","Вспышка","Тахистоскоп: слово на 50–300 мс","3 сл · 90 мс","★★☆",""),
("E-FND","Поиск слов","Найди заданные слова в тексте","12 / 12 · 41 с","★★☆",""),
("E-GAP","Пропущенные буквы","Прочти слова с пропусками","94%","★★★",""),
("E-EYE","Глазодвигатель","Точки-мишени, саккады без головы","2:00 · 128","★☆☆",""),
("E-PCR","Указка","Ведущая строка без возвратов","380 сл/мин","—","")]
cards="".join(f'''<div class="pnl {c}" style="height:112px"><span class="tl"></span><span class="br"></span><div class="in" style="padding:10px 12px">
<div style="display:flex;justify-content:space-between"><span class="mono" style="color:var(--cyan);font-weight:700;font-size:9pt">{code}</span><span style="color:var(--amber);font-size:11pt">{st}</span></div>
<div style="font:700 13pt var(--font-hud);margin-top:4px">{n}</div><div class="muted" style="font-size:8.5pt;margin-top:2px">{d}</div>
<div class="ramp" style="margin-top:8px"><span>лучший</span><div class="sp"></div><span class="mono" style="color:var(--green);font-size:9pt">{b}</span></div></div></div>''' for code,n,d,b,st,c in ex)
# speed gauge svg
import math
def arc(cx,cy,r,a0,a1):
    p=lambda a:(cx+r*math.cos(math.radians(a)),cy+r*math.sin(math.radians(a)))
    x0,y0=p(a0);x1,y1=p(a1);large=1 if (a1-a0)%360>180 else 0
    return f"M{x0:.1f},{y0:.1f} A{r},{r} 0 {large} 1 {x1:.1f},{y1:.1f}"
ticks="".join(f'<line x1="{90+70*math.cos(math.radians(a)):.1f}" y1="{90+70*math.sin(math.radians(a)):.1f}" x2="{90+78*math.cos(math.radians(a)):.1f}" y2="{90+78*math.sin(math.radians(a)):.1f}" stroke="#2B4762" stroke-width="2"/>' for a in range(145,396,25))
val=145+250*452/1000
gauge=f'''<svg width="180" height="170"><path d="{arc(90,90,62,145,395)}" stroke="#060C17" stroke-width="12" fill="none"/><path d="{arc(90,90,62,145,val)}" stroke="#00E5FF" stroke-width="12" fill="none"/>{ticks}
<line x1="90" y1="90" x2="{90+52*math.cos(math.radians(val)):.1f}" y2="{90+52*math.sin(math.radians(val)):.1f}" stroke="#FFB000" stroke-width="3"/><circle cx="90" cy="90" r="5" fill="#FFB000"/>
<text x="90" y="128" fill="#00E5FF" font-family="DejaVu Sans Mono" font-weight="700" font-size="22" text-anchor="middle">452</text><text x="90" y="146" fill="#6F90AB" font-family="DejaVu Sans" font-weight="700" font-size="9" text-anchor="middle">СЛОВ / МИН</text></svg>'''
ring=f'''<svg width="150" height="150"><circle cx="75" cy="75" r="56" stroke="#060C17" stroke-width="12" fill="none"/><path d="{arc(75,75,56,-90,-90+360*0.82)}" stroke="#3DFF8A" stroke-width="12" fill="none"/>
<text x="75" y="80" fill="#3DFF8A" font-family="DejaVu Sans Mono" font-weight="700" font-size="24" text-anchor="middle">82%</text><text x="75" y="98" fill="#6F90AB" font-family="DejaVu Sans" font-weight="700" font-size="8.5" text-anchor="middle">ПОНИМАНИЕ</text></svg>'''
hist=[240,260,255,290,310,305,340,360,350,390,410,452]
mx=600;pts=" ".join(f"{10+i*36},{110-h/mx*100:.0f}" for i,h in enumerate(hist))
chart=f'''<svg width="100%" height="120" viewBox="0 0 420 120" preserveAspectRatio="none"><line x1="10" y1="{110-600/mx*100}" x2="410" y2="{110-600/mx*100}" stroke="#7A5300" stroke-dasharray="4 4"/><text x="408" y="{122-600/mx*100}" fill="#FFB000" font-size="8" font-family="DejaVu Sans" text-anchor="end">ЦЕЛЬ 600</text>
<polyline points="{pts}" fill="none" stroke="#00E5FF" stroke-width="2"/>{"".join(f'<circle cx="{10+i*36}" cy="{110-h/mx*100:.0f}" r="3" fill="#00E5FF"/>' for i,h in enumerate(hist))}<line x1="10" y1="110" x2="410" y2="110" stroke="#15314D"/></svg>'''
page("sr-4-overview.html","Скорочтение — обзор","Обзор",'''
.top{display:grid;grid-template-columns:400px minmax(0,1fr) 330px;gap:12px}
.ex{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.wrap{grid-template-columns:minmax(0,1fr)}
.src{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}.src .btn{height:28px;font-size:8.5pt;padding:0 10px}
''',f'''
<div class="wrap">
 <div class="top">
  <div class="pnl amber" style="height:250px"><span class="tl"></span><span class="br"></span><span class="ttl">Гипердрайв · запуск чтения</span><span class="st muted">R-HYP</span><div class="in">
   <div class="lbl">Текст</div><div style="font:700 14pt var(--font-hud);margin-top:3px">Свой текст · «1984» (рус.) <span class="muted" style="font-size:9pt">· 13% · 9 806 слов</span></div>
   <div class="src"><span class="btn act"><span>Продолжить</span></span><span class="btn"><span>Свой текст</span></span><span class="btn"><span>Вставить</span><span class="k">Ctrl+V</span></span><span class="btn"><span>Открыть .txt</span></span><span class="btn"><span>English</span></span></div>
   <div class="ramp" style="margin:6px 0 10px"><span>старт</span><span class="mono" style="color:var(--cyan)">300</span><span>→ цель</span><span class="mono" style="color:var(--amber)">600</span><span>· 1 слово · ORP вкл</span></div>
   <span class="btn amber big act"><span>► Прыжок в гипердрайв</span><span class="k">Enter</span></span></div></div>
  <div class="pnl" style="height:250px"><span class="tl"></span><span class="br"></span><span class="ttl">Скорость чтения · 12 сессий</span><span class="st" style="color:var(--green)">+88% с начала</span><div class="in" style="display:grid;grid-template-columns:180px minmax(0,1fr);align-items:center">{gauge}<div>{chart}</div></div></div>
  <div class="pnl green" style="height:250px"><span class="tl"></span><span class="br"></span><span class="ttl">Телеметрия чтеца</span><div class="in" style="display:grid;grid-template-columns:150px 1fr;gap:6px;align-items:center">{ring}
   <div><div class="ro" style="--c:var(--amber)"><span class="l">Рекорд</span><span class="v" style="font-size:12pt">520</span></div><div class="ro" style="--c:var(--green)"><span class="l">Эфф.</span><span class="v" style="font-size:12pt">371</span></div><div class="ro"><span class="l">Серия</span><span class="v" style="font-size:12pt">6 дн</span></div></div>
   <div class="muted" style="grid-column:1/3;font-size:8pt">Эффективная скорость = скорость × понимание. XP идёт в общее звание Star Typing.</div></div></div>
 </div>
 <div class="lbl" style="margin-top:2px">Тренажёры обзора · поле зрения, внимание, движение глаз</div>
 <div class="ex">{cards}</div>
</div>
''')
