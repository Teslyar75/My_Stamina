CSS_COMMON='''
.logo small{white-space:nowrap}
.av{--a:var(--cyan);position:relative;width:var(--s,84px);height:var(--s,84px);clip-path:polygon(25% 3%,75% 3%,100% 50%,75% 97%,25% 97%,0 50%);background:var(--a);display:grid;place-items:center;flex:none}
.av i{width:calc(100% - 4px);height:calc(100% - 4px);clip-path:inherit;background:radial-gradient(circle at 50% 38%,color-mix(in srgb,var(--a) 30%,var(--panel)) 0,var(--panel) 70%);display:grid;place-items:center;font-style:normal;color:var(--a);font-size:calc(var(--s,84px)*.45);font-family:"DejaVu Sans",sans-serif}
.av.amber{--a:var(--amber)}.av.green{--a:var(--green)}.av.red{--a:var(--red)}.av.purple{--a:var(--purple)}
.lbl{font:700 8pt var(--font-hud);color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
.bar{height:6px;background:var(--bg-2);border:1px solid var(--line)}.bar i{display:block;height:100%;background:var(--amber)}
.kbd{font:700 8pt var(--font-mono);color:var(--muted)}
'''
def page(fn,title,css,body,note):
    open(fn,"w").write(f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>{title}</title><link rel="stylesheet" href="hud.css"><style>{CSS_COMMON}{css}</style></head><body>{body}<div class="note">{note}</div></body></html>''')

TOP='''<div class="hdr"><div class="logo"><div class="hex"><i>★</i></div><div><b>STAR TYPING</b><small>ПУЛЬТ ПИЛОТА · ТРЕНАЖЁР ПЕЧАТИ</small></div></div><div class="sp"></div>{right}<span class="clock">18:42</span></div><div class="hline"></div>'''

# ---- 1. pilot select ----
pilots=[("★","","George Orwell","1984","ЛЕЙТЕНАНТ","916 / 1500",61,"18:12 сегодня",[("ПЕЧАТЬ","231 зн/мин"),("«1984»","19%"),("ENGLISH","412 слов"),("ЧТЕНИЕ","452 сл/мин")],True),
("☄","amber","КОМЕТА","Аня","МИЧМАН","404 / 700",58,"вчера",[("ПЕЧАТЬ","148 зн/мин"),("«1984»","—"),("ENGLISH","96 слов"),("ЧТЕНИЕ","310 сл/мин")],False),
("✈","green","ЯСТРЕБ","Миша","ПИЛОТ-СТАЖЁР","152 / 300",51,"3 дня назад",[("ПЕЧАТЬ","94 зн/мин"),("«1984»","—"),("ENGLISH","31 слово"),("ЧТЕНИЕ","—")],False)]
cards=""
for g,c,cs,nm,rk,xp,pct,last,stats,sel in pilots:
    st="".join(f'<div class="ro" style="margin-bottom:5px;padding:4px 0 4px 8px"><span class="l">{a}</span><span class="v" style="font-size:11pt">{b}</span></div>' for a,b in stats)
    cards+=f'''<div class="pnl {"amber" if sel else "dim"}" style="height:470px"><span class="tl"></span><span class="br"></span><span class="ttl">{"▶ ВЫБРАН" if sel else "ПИЛОТ"}</span><span class="st" style="color:{"var(--amber)" if sel else "var(--muted)"}">{"🔒 КОД · " if sel else ""}✎ ⇪ ✕</span><div class="in" style="display:flex;flex-direction:column;align-items:center;text-align:center;{"background:color-mix(in srgb,var(--amber) 7%,var(--panel))" if sel else ""}">
<div class="av {c}" style="--s:110px;margin-top:8px"><i>{g}</i></div>
<div style="font:700 {"18pt" if len(cs)>10 else "20pt"} var(--font-hud);letter-spacing:.04em;margin-top:12px;line-height:1.1">{cs}</div><div class="muted" style="font-size:{"13pt;font-family:var(--font-mono);color:var(--cyan)" if nm=="1984" else "10pt"}">{nm}</div>
<div style="color:var(--amber);font:700 10pt var(--font-hud);margin-top:10px">★ {rk}</div>
<div style="width:100%;margin-top:6px"><div class="bar"><i style="width:{pct}%"></i></div><div class="kbd" style="text-align:right;margin-top:3px">{xp} XP</div></div>
<div style="width:100%;margin-top:10px;text-align:left">{st}</div>
<div class="lbl" style="margin-top:auto">последний полёт · {last}</div></div></div>'''
cards+='''<div class="pnl dim" style="height:470px"><span class="tl"></span><span class="br"></span><span class="ttl">Новый пилот</span><div class="in" style="display:grid;place-items:center;text-align:center;border:1px dashed var(--line-hi)">
<div><div style="width:110px;height:110px;margin:0 auto;clip-path:polygon(25% 3%,75% 3%,100% 50%,75% 97%,25% 97%,0 50%);background:var(--line-hi);display:grid;place-items:center"><div style="width:106px;height:106px;clip-path:inherit;background:var(--bg-2);display:grid;place-items:center;font:300 48pt var(--font-hud);color:var(--cyan)">+</div></div>
<div style="font:700 14pt var(--font-hud);margin-top:14px;color:var(--cyan)">ЗАЧИСЛИТЬ В ЭКИПАЖ</div><div class="muted" style="font-size:9pt;margin-top:6px">новый пилот начинает<br>со звания «Кадет»</div><span class="btn" style="margin-top:14px"><span>⇩ Импорт пилота</span></span></div></div></div>'''
page("pilot-select.html","Вход в кабину",'''
.strip{display:flex;align-items:center;gap:12px;margin:4px 14px 14px;padding-left:12px;border-left:5px solid var(--amber)}
.strip h1{font:700 16pt var(--font-hud);text-transform:uppercase;letter-spacing:.06em}
.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;padding:0 14px}
.acts{display:flex;gap:10px;align-items:center;padding:14px}
.chk{display:inline-flex;align-items:center;gap:8px;font:700 9pt var(--font-hud);color:var(--muted);text-transform:uppercase}.chk b{width:16px;height:16px;border:1px solid var(--green);background:var(--green-dim);display:grid;place-items:center;color:var(--green);font-size:9pt}
''',TOP.format(right='<span class="lbl" style="margin-right:10px">экипаж: 3 пилота</span>')+f'''
<div class="strip"><div><h1>Вход в кабину</h1><span class="muted" style="font-size:9pt">выбери пилота — у каждого своё звание, статистика, книга, английский и скорочтение · ← → выбор · Enter вход</span></div></div>
<div class="grid">{cards}</div>
<div class="acts"><span class="btn amber big act"><span>► Войти · George Orwell 🔒</span><span class="k">Enter</span></span><span class="btn big"><span>✎ Переименовать</span><span class="k">F2</span></span><span class="btn big"><span>⇪ Экспорт</span></span><span class="btn big red"><span>✕ Удалить</span><span class="k">Del</span></span><div class="sp"></div><span class="chk"><b>✓</b>Спрашивать при запуске</span></div>
''',"Макет · профили пилотов · палитра и шрифты Star Typing")

# ---- 2. create pilot ----
glyphs=[("★",""),("☄","amber"),("✈","green"),("♆","purple"),("⚡","amber"),("◉",""),("▲","red"),("♛","amber"),("⚓",""),("☾","purple"),("✪","green"),("☢","red"),("✦",""),("⬡","green"),("♞","amber"),("⊕","")]
avs="".join(f'<div class="cell{" on" if i==1 else ""}"><div class="av {c}" style="--s:58px"><i>{g}</i></div></div>' for i,(g,c) in enumerate(glyphs))
sw="".join(f'<span class="sw{" on" if n=="amber" else ""}" style="--c:var(--{n})"><b></b>{t}</span>' for n,t in [("cyan","Циан"),("amber","Янтарь"),("green","Зелёный"),("red","Красный"),("purple","Фиолет")])
page("pilot-create.html","Новый пилот",'''
.strip{display:flex;align-items:center;gap:12px;margin:4px 14px 12px;padding-left:12px;border-left:5px solid var(--amber)}
.strip h1{font:700 16pt var(--font-hud);text-transform:uppercase;letter-spacing:.06em}
.grid{display:grid;grid-template-columns:360px minmax(0,1fr) 300px;gap:12px;padding:0 14px}
.field{margin:6px 0 4px;height:40px;display:flex;align-items:center;padding:0 12px;background:var(--bg-2);border:1px solid var(--line-hi);font:700 15pt var(--font-hud)}
.field.on{border-color:var(--amber);box-shadow:inset 3px 0 0 var(--amber)}
.field .cur{display:inline-block;width:2px;height:22px;background:var(--amber);margin-left:2px}
.hint{font-size:8.5pt;color:var(--muted);margin-bottom:12px}
.sws{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}.sw{display:inline-flex;align-items:center;gap:6px;padding:5px 9px;border:1px solid var(--line-hi);font:700 8.5pt var(--font-hud);color:var(--muted);text-transform:uppercase}
.sw b{width:14px;height:14px;background:var(--c)}.sw.on{border-color:var(--c);color:var(--c);background:color-mix(in srgb,var(--c) 12%,var(--bg))}
.avs{display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:6px}
.cell{display:grid;place-items:center;height:74px;background:var(--bg-2);border:1px solid var(--line)}
.cell.on{border:2px solid var(--amber);background:color-mix(in srgb,var(--amber) 10%,var(--bg))}
.up{display:grid;grid-template-columns:150px 1fr;gap:14px;align-items:center;margin-top:14px;padding-top:12px;border-top:1px solid var(--line)}
.crop{position:relative;width:150px;height:150px;background:repeating-linear-gradient(45deg,#0B2A3A 0 10px,#0A2232 10px 20px);border:1px solid var(--line-hi)}
.crop .sq{position:absolute;left:22px;top:12px;width:116px;height:116px;border:2px solid var(--amber);box-shadow:0 0 0 999px rgba(3,6,12,.55)}
.crop .hx{position:absolute;left:24px;top:14px;width:112px;height:112px;clip-path:polygon(25% 3%,75% 3%,100% 50%,75% 97%,25% 97%,0 50%);border:0;background:linear-gradient(160deg,#3a6a8a,#14324a)}
.crop .hx::after{content:"фото";position:absolute;inset:0;display:grid;place-items:center;font:700 10pt var(--font-hud);color:#9fc3d8}
.prev{display:flex;flex-direction:column;align-items:center;text-align:center}
.mini{display:flex;align-items:center;gap:8px;padding:6px 10px;background:var(--bg-2);border:1px solid var(--line);margin-top:8px}
''',TOP.format(right='')+f'''
<div class="strip"><div><h1>Зачисление в экипаж · новый пилот</h1><span class="muted" style="font-size:9pt">← вход в кабину · Tab — следующее поле · Enter — создать · Esc — отмена</span></div></div>
<div class="grid">
 <div class="pnl amber" style="height:540px"><span class="tl"></span><span class="br"></span><span class="ttl">Личное дело</span><div class="in">
  <div class="lbl">Позывной *</div><div class="field on">КОМЕТА<span class="cur"></span></div><div class="hint">2–16 символов, будет в шапке и на карточке · должен быть уникальным</div>
  <div class="lbl">Имя</div><div class="field" style="font-weight:400">Аня</div><div class="hint">необязательно</div>
  <div class="lbl">Акцентный цвет</div><div class="sws">{sw}</div><div class="hint" style="margin-top:6px">рамка аватара и карточки; остальной интерфейс не меняется</div>
  <div class="lbl" style="margin-top:4px">Стартовые настройки</div>
  <div class="ro" style="margin-top:6px"><span class="l">Язык раскладки</span><span class="v" style="font-size:11pt">RU + EN</span></div>
  <div class="ro" style="--c:var(--amber)"><span class="l">Копировать настройки</span><span class="v" style="font-size:11pt">от ТЕСЛЯР ▾</span></div>
 </div></div>
 <div class="pnl" style="height:540px"><span class="tl"></span><span class="br"></span><span class="ttl">Эмблема пилота</span><span class="st muted">16 встроенных</span><div class="in">
  <div class="avs">{avs}</div>
  <div class="up"><div class="crop"><div class="hx"></div><div class="sq"></div></div>
   <div><div style="font:700 12pt var(--font-hud)">СВОЁ ИЗОБРАЖЕНИЕ</div><div class="muted" style="font-size:9pt;margin:6px 0 10px">PNG / GIF (JPG — если есть Pillow). Обрезается по центру в квадрат 256×256 и показывается в шестиугольнике. Рамку кадрирования можно сдвинуть мышью.</div>
   <div style="display:flex;gap:8px"><span class="btn"><span>⇪ Загрузить файл…</span></span><span class="btn"><span>⟲ Сбросить</span></span></div></div></div>
 </div></div>
 <div class="pnl green" style="height:540px"><span class="tl"></span><span class="br"></span><span class="ttl">Предпросмотр</span><div class="in prev">
  <div class="av amber" style="--s:120px;margin-top:16px"><i>☄</i></div>
  <div style="font:700 20pt var(--font-hud);letter-spacing:.06em;margin-top:12px">КОМЕТА</div><div class="muted">Аня</div>
  <div style="color:var(--amber);font:700 10pt var(--font-hud);margin-top:10px">★ КАДЕТ · 0 / 100 XP</div>
  <div class="lbl" style="margin-top:24px">В шапке</div>
  <div class="mini"><div class="av amber" style="--s:30px"><i>☄</i></div><div style="text-align:left"><div style="font:700 9pt var(--font-hud);color:var(--amber)">КОМЕТА ▾</div><div class="kbd">★ КАДЕТ · 0 / 100 XP</div></div></div>
  <div class="muted" style="font-size:8.5pt;margin-top:auto">Свой прогресс: печать и миссии, «1984», английский, скорочтение, достижения, настройки.</div>
 </div></div>
</div>
<div style="display:flex;gap:10px;padding:14px"><span class="btn amber big act"><span>✓ Создать пилота</span><span class="k">Enter</span></span><span class="btn big"><span>Отмена</span><span class="k">Esc</span></span></div>
''',"Макет · профили пилотов · палитра и шрифты Star Typing")

# ---- 3. PIN dialog ----
pins="".join(f'<span class="pc{" f" if i<2 else (" cur" if i==2 else "")}">{"●" if i<2 else ""}</span>' for i in range(4))
keys="".join(f'<span class="btn key"><span>{k}</span></span>' for k in ["1","2","3","4","5","6","7","8","9","⌫","0","✓"])
page("pin-dialog.html","Код доступа",'''
.dim{position:absolute;inset:0;background:rgba(3,6,12,.78);z-index:5}
.bgshot{position:absolute;inset:0;background:url(pilot-select.png) 0 0/1280px 800px no-repeat;filter:blur(1px)}
.dlg{position:absolute;left:390px;top:100px;width:500px;height:615px;z-index:6}
.dlg .in{display:flex;flex-direction:column;align-items:center;text-align:center;padding-top:34px}
.pcs{display:flex;gap:10px;margin:14px 0 6px}
.pc{width:52px;height:60px;display:grid;place-items:center;background:var(--bg-2);border:1px solid var(--line-hi);font:700 20pt var(--font-mono);color:var(--amber)}
.pc.f{border-color:var(--amber)}.pc.cur{border:2px solid var(--amber);box-shadow:inset 0 -4px 0 var(--amber)}
.pad{display:grid;grid-template-columns:repeat(3,72px);gap:8px;margin-top:12px}
.key{height:46px;font:700 15pt var(--font-mono)}
''',f'''<div class="bgshot"></div><div class="dim"></div>
<div class="pnl amber dlg"><span class="tl"></span><span class="br"></span><span class="ttl">🔒 Код доступа</span><span class="st muted">Esc — отмена</span><div class="in">
 <div class="av" style="--s:84px"><i>★</i></div>
 <div style="font:700 18pt var(--font-hud);letter-spacing:.04em;margin-top:10px">George Orwell</div><div class="mono" style="color:var(--cyan);font-size:12pt">1984</div>
 <div class="lbl" style="margin-top:14px">Введите код доступа пилота</div>
 <div class="pcs">{pins}</div>
 <div class="lbl" style="color:var(--red)">✕ Код неверен · осталось попыток: 4</div>
 <div class="pad">{keys}</div>
 <div style="display:flex;gap:10px;margin-top:16px"><span class="btn amber act"><span>✓ Войти</span><span class="k">Enter</span></span><span class="btn"><span>Отмена</span><span class="k">Esc</span></span></div>
 <div style="margin-top:12px;font:700 8.5pt var(--font-hud);color:var(--cyan);text-decoration:underline;letter-spacing:.05em">ЗАБЫЛИ КОД? · СБРОС ЧЕРЕЗ ПОДТВЕРЖДЕНИЕ</div>
</div></div>''',"Макет · код доступа пилота · хранится только солёный хэш")
