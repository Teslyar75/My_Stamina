"""Учебник PowerShell для тренажёра: темы, команды, примеры, теория.

Данные отдельно от интерфейса — их читает панель `docker_ref_panel`
(переиспользуется под любой терминальный учебник) и по ним же строится
подсказка автодополнения.

Поле ``sim`` — команда отвечает в учебном симуляторе (`terminal_sim`).
Поле ``theory`` у темы — короткие тезисы, которые панель показывает над
списком команд.
"""

from __future__ import annotations

from stamina.i18n import t as _t

#: Заголовок панели учебника (в интерфейсе — на языке пилота).
PANEL_TITLE = _t("УЧЕБНИК POWERSHELL · КОМАНДЫ")
SIM_HINT = _t("✓ выполняется в тренажёре")
REAL_HINT = _t("· только в настоящем PowerShell")

# fmt: off
TOPICS = [
    {
        "id": "basics",
        "title": "Основы PowerShell",
        "blurb": "Команда = глагол + существительное: Get-Process, Set-Location. Регистр не важен.",
        "commands": [
            {
                "cmd": "Get-Command",
                "desc": "Список команд и их типов: Cmdlet, Function, Alias, Application.",
                "example": "Get-Command Git",
                "sim": True,
            },
            {
                "cmd": "Get-Help Get-Process -Full",
                "desc": "Синтаксис и параметры команды. -Examples — только примеры.",
                "example": "Get-Help Get-Process -Full",
                "sim": True,
            },
            {
                "cmd": "Get-Module -ListAvailable",
                "desc": "Установленные модули. Базовые командлеты встроены.",
                "example": "Get-Module -ListAvailable",
                "sim": True,
            },
            {
                "cmd": "Get-PSVersion",
                "desc": "Версия PowerShell и .NET-рантайма. 7.x — это Core, кроссплатформенный.",
                "example": "Get-PSVersion",
                "sim": True,
            },
            {
                "cmd": "Get-Location",
                "desc": "Текущий путь. То же, что pwd в Linux.",
                "example": "Get-Location",
                "sim": True,
            },
        ],
        "theory": [
            "Имя команды читается как предложение: Get (получить) + Process (процессы).",
            "Параметры начинаются с дефиса: -Name, -Id, -Path; значения можно не заключать в кавычки.",
            "Alias — короткое имя: ls → Get-ChildItem, ps → Get-Process, cd → Set-Location.",
        ],
    },
    {
        "id": "processes",
        "title": "Процессы",
        "blurb": "Get-Process и управление ими: -Name, -Id, Stop-Process, Start-Process.",
        "commands": [
            {
                "cmd": "Get-Process",
                "desc": "Все процессы: Id, ProcessName, CPU. Аналог ps aux.",
                "example": "Get-Process",
                "sim": True,
            },
            {
                "cmd": "Get-Process pwsh",
                "desc": "Процесс по имени. Возвращает объекты, а не текст.",
                "example": "Get-Process pwsh",
                "sim": True,
            },
            {
                "cmd": "Get-Process -Name docker",
                "desc": "Параметр с дефисом: -Name — имя, -Id — идентификатор.",
                "example": "Get-Process -Id 1234",
                "sim": True,
            },
            {
                "cmd": "Stop-Process -Name pwsh",
                "desc": "Остановить процесс по имени (аналог kill).",
                "example": "Stop-Process -Name pwsh",
                "sim": True,
            },
            {
                "cmd": "Start-Process pwsh",
                "desc": "Запустить новый процесс.",
                "example": "Start-Process pwsh",
                "sim": True,
            },
        ],
        "theory": [
            "Get-* возвращает объекты: у них есть свойства (CPU, Id, Name), а не только строки.",
            "Stop-Process без -Force может попросить подтверждение для важных процессов.",
            "Id процесса — то же, что PID в Linux; по нему работает Get-Process -Id.",
        ],
    },
    {
        "id": "services",
        "title": "Службы",
        "blurb": "Службы Windows: Get-Service, Start-Service, Restart-Service, Stop-Service.",
        "commands": [
            {
                "cmd": "Get-Service",
                "desc": "Все службы: Status, Name, DisplayName. Running — работает.",
                "example": "Get-Service",
                "sim": True,
            },
            {
                "cmd": "Get-Service docker",
                "desc": "Одна служба по имени — быстрая проверка «жив ли движок».",
                "example": "Get-Service docker",
                "sim": True,
            },
            {
                "cmd": "Restart-Service docker",
                "desc": "Перезапуск службы. Для docker это перезапуск движка со всеми контейнерами.",
                "example": "Restart-Service docker",
                "sim": True,
            },
            {
                "cmd": "Stop-Service Spooler",
                "desc": "Остановить службу. -Force снимает зависимые службы.",
                "example": "Stop-Service Spooler",
                "sim": True,
            },
            {
                "cmd": "Get-Service | Where-Object Status -eq 'Stopped'",
                "desc": "Только остановленные службы — так ищут проблему после загрузки.",
                "example": "Get-Service | Where-Object Status -eq 'Stopped'",
                "sim": True,
            },
        ],
        "theory": [
            "Status у службы: Running, Stopped, StartPending, StopPending.",
            "Останавливать службы без прав администратора нельзя: нужен запуск от имени администратора.",
            "Get-Service работает и на Linux в PowerShell 7, но список служб будет свой.",
        ],
    },
    {
        "id": "files",
        "title": "Файлы и пути",
        "blurb": "Get-Content, Get-ChildItem, Set-Location, Remove-Item: чтение, список, переход, удаление.",
        "commands": [
            {
                "cmd": "Get-Content -Path C:\\ship\\app.log -Tail 10",
                "desc": "Последние N строк файла. -Raw читает файл целиком одной строкой.",
                "example": "Get-Content -Path C:\\ship\\app.log -Tail 10",
                "sim": True,
            },
            {
                "cmd": "Get-ChildItem C:\\ship -Filter *.log",
                "desc": "Список файлов с фильтром по маске.",
                "example": "Get-ChildItem C:\\ship -Filter *.log",
                "sim": True,
            },
            {
                "cmd": "Get-ChildItem -Recurse -Depth 2",
                "desc": "Рекурсивный обход: -Depth ограничивает вложенность.",
                "example": "Get-ChildItem -Recurse C:\\ship",
                "sim": True,
            },
            {
                "cmd": "Set-Location C:\\ship",
                "desc": "Сменить каталог (cd). Get-Location покажет текущий.",
                "example": "Set-Location C:\\ship",
                "sim": True,
            },
            {
                "cmd": "Remove-Item -Recurse -Force C:\\ship\\tmp",
                "desc": "Удалить каталог с содержимым. -WhatIf покажет, что будет удалено.",
                "example": "Remove-Item -Recurse -Force C:\\ship\\tmp",
                "sim": True,
            },
        ],
        "theory": [
            "Пути Windows: C:\\ship\\app.log; обратный слэш в кавычках не нужно удваивать.",
            "-WhatIf у опасных команд показывает план действий, ничего не делая.",
            "Get-ChildItem -Force показывает скрытые файлы, как ls -a.",
        ],
    },
    {
        "id": "network",
        "title": "Сеть",
        "blurb": "Проверка связи и портов: Test-NetConnection, Get-NetTCPConnection, Resolve-DnsName.",
        "commands": [
            {
                "cmd": "Test-NetConnection -ComputerName localhost -Port 8080",
                "desc": "TCP-пинг: доступен ли порт. TcpTestSucceeded = True — да.",
                "example": "Test-NetConnection -ComputerName localhost -Port 8080",
                "sim": True,
            },
            {
                "cmd": "Get-NetTCPConnection -LocalPort 8080",
                "desc": "Кто слушает порт: адрес, состояние, OwningProcess.",
                "example": "Get-NetTCPConnection -LocalPort 8080",
                "sim": True,
            },
            {
                "cmd": "Resolve-DnsName ship.example.com",
                "desc": "DNS-резолвинг имени в IP.",
                "example": "Resolve-DnsName ship.example.com",
                "sim": True,
            },
            {
                "cmd": "Test-NetConnection -ComputerName 8.8.8.8",
                "desc": "Без -Port проверяет ICMP-пинг, как ping.",
                "example": "Test-NetConnection -ComputerName 8.8.8.8",
                "sim": True,
            },
        ],
        "theory": [
            "TcpTestSucceeded — главный ответ: TCP-порт открыт или нет.",
            "OwningProcess из Get-NetTCPConnection — PID того, кто занял порт.",
            "Test-NetConnection не требует отдельных утилит: он встроен в Windows.",
        ],
    },
    {
        "id": "pipeline",
        "title": "Конвейер и объекты",
        "blurb": "Сердце PowerShell: | передаёт объекты, а не текст. Where — фильтр, Select — выбор, Sort — порядок.",
        "commands": [
            {
                "cmd": "Get-Process | Sort-Object CPU -Descending",
                "desc": "Отсортировать процессы по процессорному времени, сверху самые тяжёлые.",
                "example": "Get-Process | Sort-Object CPU -Descending",
                "sim": True,
            },
            {
                "cmd": "Get-Process | Select-Object Name, CPU",
                "desc": "Оставить только нужные свойства — таблица становится читаемой.",
                "example": "Get-Process | Select-Object Name, CPU",
                "sim": True,
            },
            {
                "cmd": "Get-Process | Select-Object -First 3",
                "desc": "Первые три объекта. -Last, -Skip работают так же.",
                "example": "Get-Process | Select-Object -First 3",
                "sim": True,
            },
            {
                "cmd": "Get-Service | Where-Object Status -eq 'Running'",
                "desc": "Фильтр по свойству: -eq, -ne, -gt, -lt, -like.",
                "example": "Get-Service | Where-Object Status -eq 'Running'",
                "sim": True,
            },
            {
                "cmd": "Get-Process | Measure-Object -Property CPU -Sum",
                "desc": "Посчитать: Count, Sum, Average, Maximum, Minimum.",
                "example": "Get-Process | Measure-Object -Property CPU -Sum",
                "sim": True,
            },
            {
                "cmd": "Get-Process | ForEach-Object { $_.Name }",
                "desc": "Пройти по каждому объекту; $_ — текущий элемент.",
                "example": "Get-Process | ForEach-Object { $_.Name }",
                "sim": True,
            },
        ],
        "theory": [
            "В PowerShell по конвейеру идут объекты: свойство можно взять без разбора текста.",
            "Порядок важен: сначала Get, потом фильтр, потом выбор свойств и сортировка.",
            "Where-Object в скриптовом виде: Where-Object { $_.CPU -gt 0.1 }.",
        ],
    },
    {
        "id": "data",
        "title": "Данные и файлы",
        "blurb": "Записать, скопировать и превратить объекты в JSON/CSV: Set-Content, ConvertTo-Json, Export-Csv.",
        "commands": [
            {
                "cmd": "Get-Service | ConvertTo-Json -Depth 2",
                "desc": "Объекты → JSON. -Depth ограничивает вложенность.",
                "example": "Get-Service | ConvertTo-Json -Depth 2",
                "sim": True,
            },
            {
                "cmd": "Get-Service | Export-Csv C:\\ship\\services.csv -NoTypeInformation",
                "desc": "Объекты → CSV-файл, который откроется в Excel.",
                "example": "Get-Service | Export-Csv C:\\ship\\services.csv -NoTypeInformation",
                "sim": True,
            },
            {
                "cmd": "Set-Content -Path C:\\ship\\note.txt -Value 'patrol'",
                "desc": "Записать строку в файл (перезаписать). Add-Content — дописать.",
                "example": "Set-Content -Path C:\\ship\\note.txt -Value 'patrol'",
                "sim": True,
            },
            {
                "cmd": "Copy-Item C:\\ship\\app.log C:\\ship\\app.log.bak",
                "desc": "Скопировать файл. New-Item создаёт файл или каталог.",
                "example": "Copy-Item C:\\ship\\app.log C:\\ship\\app.log.bak",
                "sim": True,
            },
            {
                "cmd": "Get-Content C:\\ship\\app.log | Select-String ERROR",
                "desc": "Поиск по содержимому, как grep. Возвращает объекты MatchInfo.",
                "example": "Get-Content C:\\ship\\app.log | Select-String ERROR",
                "sim": True,
            },
        ],
        "theory": [
            "ConvertTo-Json и ConvertFrom-Json — мост между объектами и текстом для API.",
            "Export-Csv пишет заголовки из имён свойств; -NoTypeInformation убирает служебную строку.",
            "Set-Content перезаписывает файл целиком, Add-Content дописывает в конец.",
        ],
    },
    {
        "id": "env",
        "title": "Переменные и окружение",
        "blurb": "Свои значения и переменные среды: $env:, Set-Variable, Get-Variable, Get-Date.",
        "commands": [
            {
                "cmd": "$env:SHIP_MODE = 'patrol'",
                "desc": "Переменная среды процесса. Видна дочерним программам.",
                "example": "$env:SHIP_MODE = 'patrol'",
                "sim": True,
            },
            {
                "cmd": "Get-ChildItem Env:",
                "desc": "Список всех переменных среды — как env в Linux.",
                "example": "Get-ChildItem Env:",
                "sim": True,
            },
            {
                "cmd": "Get-Variable Pilot",
                "desc": "Своя переменная сессии: $Pilot = 'orion'.",
                "example": "Get-Variable Pilot",
                "sim": True,
            },
            {
                "cmd": "Set-Variable -Name Mission -Value 'patrol'",
                "desc": "Создать или изменить переменную по имени.",
                "example": "Set-Variable -Name Mission -Value 'patrol'",
                "sim": True,
            },
            {
                "cmd": "Get-Date",
                "desc": "Текущие дата и время как объект: можно вычитать дни и форматировать.",
                "example": "Get-Date -Format 'yyyy-MM-dd'",
                "sim": True,
            },
        ],
        "theory": [
            "Переменные начинаются с $; имя без кавычек: $Pilot, $Mission.",
            "$env:ИМЯ — это переменная среды, она переживёт выход из сессии PowerShell.",
            "Get-Date возвращает объект DateTime, а не строку: с ним работают как с датой.",
        ],
    },
]


def topics() -> list[dict]:
    return TOPICS


def topic(topic_id: str) -> dict | None:
    for t in TOPICS:
        if t["id"] == topic_id:
            return t
    return None


def commands(topic_id: str | None = None) -> list[dict]:
    if topic_id is None:
        return [c for t in TOPICS for c in t["commands"]]
    t = topic(topic_id)
    return list(t["commands"]) if t else []


def total() -> int:
    return sum(len(t["commands"]) for t in TOPICS)


def supported() -> list[dict]:
    return [c for c in commands() if c.get("sim")]


def completions() -> list[str]:
    out: list[str] = []
    for c in commands():
        head = " ".join(c["cmd"].split()[:2])
        if head and not head.startswith("-") and head not in out:
            out.append(head)
    return out


def search(query: str, topic_id: str | None = None) -> list[dict]:
    q = (query or "").strip().lower()
    items = commands(topic_id)
    if not q:
        return items
    words = q.split()
    return [c for c in items if all(w in (c["cmd"] + " " + c["desc"]).lower() for w in words)]
# fmt: on
