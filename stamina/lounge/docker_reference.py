"""Учебник Docker для Док-станции: темы, команды, примеры.

Данные отдельно от интерфейса — их читает панель `docker_ref_panel` и по ним же
строится подсказка автодополнения. Описания по-русски: это учебный текст, а не
подписи интерфейса (подписи берутся из i18n, как везде на борту).

Поле ``sim`` — команда выполняется в учебном симуляторе (`docker_sim`). Для
остальных панель честно пишет: «в тренажёре не выполняется, попробуйте в
настоящем Docker», и даёт пример, чтобы было что повторить руками.
"""

from __future__ import annotations

from stamina.i18n import t as _t

#: Заголовок панели учебника и подписи карточки — одинаковые для всех тренажёров.
PANEL_TITLE = _t("УЧЕБНИК DOCKER · КОМАНДЫ")
SIM_HINT = _t("✓ выполняется в тренажёре")
REAL_HINT = _t("· только в настоящем Docker")

# fmt: off
TOPICS = [
    {
        "id": "basics",
        "title": _t("Основы"),
        "blurb": _t("Образ — это шаблон, контейнер — его запущенный экземпляр. Реестр (Docker Hub) хранит образы, локальный диск — тоже."),
        "commands": [
            {
                "cmd": "docker version",
                "desc": _t("Версии клиента и демона. Если демон не отвечает — Docker не запущен."),
                "example": "docker version",
                "sim": False,
            },
            {
                "cmd": "docker info",
                "desc": _t("Всё о среде: сколько контейнеров и образов, драйвер хранилища, ядер, памяти, корневой каталог."),
                "example": "docker info",
                "sim": False,
            },
            {
                "cmd": "docker --help",
                "desc": _t("Список команд. Справка по конкретной: docker run --help."),
                "example": "docker run --help",
                "sim": False,
            },
            {
                "cmd": "docker search nginx",
                "desc": _t("Поиск образов в Docker Hub без браузера."),
                "example": "docker search nginx",
                "sim": False,
            },
            {
                "cmd": "docker login",
                "desc": _t("Вход в реестр. Нужен, чтобы скачивать приватные образы и публиковать свои."),
                "example": "docker login",
                "sim": False,
            },
            {
                "cmd": "docker logout",
                "desc": _t("Выход из реестра — убрать учётные данные с машины."),
                "example": "docker logout",
                "sim": False,
            },
            {
                "cmd": "docker context ls",
                "desc": _t("Список контекстов: локальный демон, удалённый сервер, Docker Desktop."),
                "example": "docker context ls",
                "sim": False,
            },
        ],
    },
    {
        "id": "containers",
        "title": _t("Контейнеры"),
        "blurb": _t("Жизненный цикл: создать → запустить → посмотреть → остановить → удалить. Имя контейнера задаётся флагом --name, иначе Docker придумает своё."),
        "commands": [
            {
                "cmd": "docker run ship/radio",
                "desc": _t("Создать контейнер из образа и запустить на переднем плане. Вывод идёт в терминал, Ctrl+C его останавливает."),
                "example": "docker run ship/radio",
                "sim": True,
            },
            {
                "cmd": "docker run -d ship/radio",
                "desc": _t("Запуск в фоне (detached). Вернёт ID и отдаст терминал. Так запускают сервисы."),
                "example": "docker run -d ship/radio",
                "sim": True,
            },
            {
                "cmd": "docker run -it ship/base sh",
                "desc": _t("Интерактивно, с терминалом: -i держит ввод, -t даёт псевдотерминал. Так заходят внутрь и смотрят, что там."),
                "example": "docker run -it ship/base sh",
                "sim": False,
            },
            {
                "cmd": "docker run --rm ship/scanner",
                "desc": _t("--rm удаляет контейнер сразу после остановки: одноразовый запуск без мусора."),
                "example": "docker run --rm ship/scanner",
                "sim": False,
            },
            {
                "cmd": "docker run -p 9000:9000 ship/orion",
                "desc": _t("Проброс порта: слева порт хоста, справа порт внутри контейнера. Без -p контейнер снаружи не виден."),
                "example": "docker run -d -p 9000:9000 ship/orion",
                "sim": True,
            },
            {
                "cmd": "docker run --name my_orion ship/orion",
                "desc": _t("Понятное имя вместо случайного. Имя уникально: занятое вызовет ошибку."),
                "example": "docker run -d --name my_orion ship/orion",
                "sim": True,
            },
            {
                "cmd": "docker run -e MODE=test ship/lab",
                "desc": _t("Переменная окружения внутри контейнера. Их можно перечислять: -e A=1 -e B=2."),
                "example": "docker run -e MODE=test ship/lab",
                "sim": False,
            },
            {
                "cmd": "docker ps",
                "desc": _t("Запущенные контейнеры: ID, образ, команда, статус, порты, имя."),
                "example": "docker ps",
                "sim": True,
            },
            {
                "cmd": "docker ps -a",
                "desc": _t("Все контейнеры, включая остановленные. Здесь видно, почему упал."),
                "example": "docker ps -a",
                "sim": True,
            },
            {
                "cmd": "docker start my_orion",
                "desc": _t("Запустить существующий контейнер заново — быстрее, чем создавать новый."),
                "example": "docker start my_orion",
                "sim": False,
            },
            {
                "cmd": "docker stop my_orion",
                "desc": _t("Мягкая остановка: SIGTERM, через 10 секунд SIGKILL. Флаг -t 30 даёт больше времени."),
                "example": "docker stop my_orion",
                "sim": True,
            },
            {
                "cmd": "docker restart my_orion",
                "desc": _t("Остановить и сразу запустить: перечитать конфиг, не теряя контейнер."),
                "example": "docker restart my_orion",
                "sim": False,
            },
            {
                "cmd": "docker kill my_orion",
                "desc": _t("Жёсткое убийство сигналом (по умолчанию SIGKILL), без ожидания."),
                "example": "docker kill my_orion",
                "sim": False,
            },
            {
                "cmd": "docker rm my_orion",
                "desc": _t("Удалить остановленный контейнер. Запущенный не удалится — сначала stop или rm -f."),
                "example": "docker rm my_orion",
                "sim": True,
            },
            {
                "cmd": "docker rm -f my_orion",
                "desc": _t("Остановить и удалить одной командой."),
                "example": "docker rm -f my_orion",
                "sim": True,
            },
            {
                "cmd": "docker logs my_orion",
                "desc": _t("Вывод контейнера (stdout/stderr) по имени или ID."),
                "example": "docker logs my_orion",
                "sim": True,
            },
            {
                "cmd": "docker logs -f --tail 50 my_orion",
                "desc": _t("Следить за логами в реальном времени, начиная с последних 50 строк."),
                "example": "docker logs -f --tail 50 my_orion",
                "sim": False,
            },
            {
                "cmd": "docker exec -it my_orion sh",
                "desc": _t("Зайти в работающий контейнер отдельным процессом. Классика: exec -it <имя> bash."),
                "example": "docker exec -it my_orion sh",
                "sim": False,
            },
            {
                "cmd": "docker inspect my_orion",
                "desc": _t("Полная карточка в JSON: сеть, тома, переменные, точки монтирования."),
                "example": "docker inspect my_orion",
                "sim": False,
            },
            {
                "cmd": "docker inspect -f '{{.State.Status}}' my_orion",
                "desc": _t("Достать одно поле из JSON шаблоном, без чтения простыни."),
                "example": "docker inspect -f '{{.State.Status}}' my_orion",
                "sim": False,
            },
            {
                "cmd": "docker port my_orion",
                "desc": _t("Какие порты контейнера и куда опубликованы на хосте."),
                "example": "docker port my_orion",
                "sim": True,
            },
            {
                "cmd": "docker stats",
                "desc": _t("Живые CPU, память, сеть и диск по контейнерам. --no-stream — один снимок."),
                "example": "docker stats --no-stream",
                "sim": False,
            },
            {
                "cmd": "docker top my_orion",
                "desc": _t("Процессы внутри контейнера — как обычный ps хоста."),
                "example": "docker top my_orion",
                "sim": False,
            },
            {
                "cmd": "docker cp my_orion:/app/log.txt .",
                "desc": _t("Копировать файлы между контейнером и хостом в обе стороны."),
                "example": "docker cp my_orion:/app/log.txt .",
                "sim": False,
            },
            {
                "cmd": "docker rename old_name new_name",
                "desc": _t("Переименовать контейнер, не пересоздавая его."),
                "example": "docker rename my_orion orion_2",
                "sim": False,
            },
            {
                "cmd": "docker diff my_orion",
                "desc": _t("Что изменилось в файловой системе контейнера относительно образа."),
                "example": "docker diff my_orion",
                "sim": False,
            },
        ],
    },
    {
        "id": "images",
        "title": _t("Образы"),
        "blurb": _t("Образ собирается из Dockerfile или скачивается из реестра. Тег — это версия: ship/radio:1.2. Без тега берётся latest."),
        "commands": [
            {
                "cmd": "docker images",
                "desc": _t("Локальные образы: репозиторий, тег, ID, размер, когда создан."),
                "example": "docker images",
                "sim": True,
            },
            {
                "cmd": "docker pull ship/radio",
                "desc": _t("Скачать образ (или обновить) из реестра. Слои кешируются."),
                "example": "docker pull ship/radio:latest",
                "sim": True,
            },
            {
                "cmd": "docker build -t ship/radio:1.0 .",
                "desc": _t("Собрать образ из Dockerfile в текущем каталоге. -t задаёт имя и тег, точка — контекст сборки."),
                "example": "docker build -t ship/radio:1.0 .",
                "sim": True,
            },
            {
                "cmd": "docker build --no-cache -t ship/radio .",
                "desc": _t("Собрать заново, не доверяя кешу слоёв. Медленнее, зато честно."),
                "example": "docker build --no-cache -t ship/radio .",
                "sim": False,
            },
            {
                "cmd": "docker tag ship/radio:1.0 ship/radio:latest",
                "desc": _t("Второе имя для того же образа. Так готовят версию к публикации."),
                "example": "docker tag ship/radio:1.0 ship/radio:latest",
                "sim": False,
            },
            {
                "cmd": "docker push ship/radio:1.0",
                "desc": _t("Отправить образ в реестр. Нужен docker login и права на репозиторий."),
                "example": "docker push ship/radio:1.0",
                "sim": False,
            },
            {
                "cmd": "docker rmi ship/radio",
                "desc": _t("Удалить образ. Занятый контейнером образ не удалится, пока не rm контейнер."),
                "example": "docker rmi ship/radio:1.0",
                "sim": False,
            },
            {
                "cmd": "docker rmi -f ship/radio",
                "desc": _t("Удалить образ вместе с его тегами, даже если он не один."),
                "example": "docker rmi -f ship/radio:1.0",
                "sim": False,
            },
            {
                "cmd": "docker history ship/radio",
                "desc": _t("Слои образа: какая инструкция Dockerfile сколько весит."),
                "example": "docker history ship/radio",
                "sim": False,
            },
            {
                "cmd": "docker inspect ship/radio",
                "desc": _t("Метаданные образа: переменные, порты, команда запуска, слои."),
                "example": "docker inspect ship/radio",
                "sim": False,
            },
            {
                "cmd": "docker commit my_orion ship/radio:snapshot",
                "desc": _t("Зафиксировать изменения контейнера в новый образ. Для опытов годится, для сборки — Dockerfile."),
                "example": "docker commit my_orion ship/radio:snapshot",
                "sim": False,
            },
            {
                "cmd": "docker save -o radio.tar ship/radio",
                "desc": _t("Сохранить образ в файл — перенести на машину без реестра."),
                "example": "docker save -o radio.tar ship/radio",
                "sim": False,
            },
            {
                "cmd": "docker load -i radio.tar",
                "desc": _t("Загрузить образ из файла, созданного docker save."),
                "example": "docker load -i radio.tar",
                "sim": False,
            },
        ],
    },
    {
        "id": "volumes",
        "title": _t("Тома и данные"),
        "blurb": _t("Контейнер эфемерен: удалили — данные внутри пропали. Тома живут отдельно и переживают контейнеры."),
        "commands": [
            {
                "cmd": "docker volume create ship_data",
                "desc": _t("Создать именованный том. Docker сам выберет место на диске."),
                "example": "docker volume create ship_data",
                "sim": True,
            },
            {
                "cmd": "docker volume ls",
                "desc": _t("Список томов: именованные и анонимные (длинные хеши)."),
                "example": "docker volume ls",
                "sim": True,
            },
            {
                "cmd": "docker volume inspect ship_data",
                "desc": _t("Где том лежит на хосте (Mountpoint) и какие у него метки."),
                "example": "docker volume inspect ship_data",
                "sim": False,
            },
            {
                "cmd": "docker volume rm ship_data",
                "desc": _t("Удалить том. Занятый контейнером том не удалится."),
                "example": "docker volume rm ship_data",
                "sim": True,
            },
            {
                "cmd": "docker run -v ship_data:/data ship/lab",
                "desc": _t("Подключить том к каталогу контейнера. Всё, что записано в /data, останется после удаления контейнера."),
                "example": "docker run -d -v ship_data:/data ship/lab",
                "sim": False,
            },
            {
                "cmd": "docker run -v ./config:/app/config:ro ship/lab",
                "desc": _t("Смонтировать каталог хоста. :ro — только чтение, контейнер не испортит файлы."),
                "example": "docker run -v ./config:/app/config:ro ship/lab",
                "sim": False,
            },
            {
                "cmd": "docker run --mount type=volume,src=ship_data,dst=/data ship/lab",
                "desc": _t("Подробная форма монтирования — понятнее и строже, чем короткая -v."),
                "example": "docker run --mount type=volume,src=ship_data,dst=/data ship/lab",
                "sim": False,
            },
            {
                "cmd": "docker volume prune",
                "desc": _t("Удалить неиспользуемые тома. Осторожно: данные исчезнут без вопросов."),
                "example": "docker volume prune",
                "sim": False,
            },
        ],
    },
    {
        "id": "networks",
        "title": _t("Сети"),
        "blurb": _t("В пользовательской сети контейнеры видны друг другу по имени — это и есть сервис-дискавери Docker."),
        "commands": [
            {
                "cmd": "docker network create shipnet",
                "desc": _t("Создать пользовательскую bridge-сеть. В ней работает DNS по именам."),
                "example": "docker network create shipnet",
                "sim": True,
            },
            {
                "cmd": "docker network ls",
                "desc": _t("Сети: bridge, host, none и ваши собственные."),
                "example": "docker network ls",
                "sim": True,
            },
            {
                "cmd": "docker network inspect shipnet",
                "desc": _t("Кто подключён, какая подсеть и шлюз."),
                "example": "docker network inspect shipnet",
                "sim": False,
            },
            {
                "cmd": "docker run --network shipnet ship/lab",
                "desc": _t("Запустить контейнер сразу в нужной сети. По умолчанию — bridge."),
                "example": "docker run -d --network shipnet --name lab ship/lab",
                "sim": False,
            },
            {
                "cmd": "docker network connect shipnet my_orion",
                "desc": _t("Подключить работающий контейнер к ещё одной сети."),
                "example": "docker network connect shipnet my_orion",
                "sim": False,
            },
            {
                "cmd": "docker network disconnect shipnet my_orion",
                "desc": _t("Отключить контейнер от сети, не останавливая его."),
                "example": "docker network disconnect shipnet my_orion",
                "sim": False,
            },
            {
                "cmd": "docker network rm shipnet",
                "desc": _t("Удалить сеть. Сначала отключите от неё контейнеры."),
                "example": "docker network rm shipnet",
                "sim": False,
            },
            {
                "cmd": "docker network prune",
                "desc": _t("Убрать все неиспользуемые сети."),
                "example": "docker network prune",
                "sim": False,
            },
            {
                "cmd": "docker run -p 127.0.0.1:9000:9000 ship/orion",
                "desc": _t("Публиковать порт только на localhost — наружу сервис не откроется."),
                "example": "docker run -d -p 127.0.0.1:9000:9000 ship/orion",
                "sim": False,
            },
        ],
    },
    {
        "id": "compose",
        "title": "Docker Compose",
        "blurb": _t("compose.yml описывает несколько сервисов сразу: один файл — весь корабельный стенд. Запускается одной командой."),
        "commands": [
            {
                "cmd": "docker compose up -d",
                "desc": _t("Поднять все сервисы из compose.yml в фоне. Создаст сети и тома сам."),
                "example": "docker compose up -d",
                "sim": True,
            },
            {
                "cmd": "docker compose up -d orion lab base",
                "desc": _t("Поднять только перечисленные сервисы (и их зависимости)."),
                "example": "docker compose up -d orion lab base",
                "sim": True,
            },
            {
                "cmd": "docker compose ps",
                "desc": _t("Контейнеры этого проекта: статус, порты, здоровье."),
                "example": "docker compose ps",
                "sim": True,
            },
            {
                "cmd": "docker compose logs -f orion",
                "desc": _t("Логи сервиса в реальном времени."),
                "example": "docker compose logs -f orion",
                "sim": False,
            },
            {
                "cmd": "docker compose down",
                "desc": _t("Остановить и удалить контейнеры и сети проекта. Тома остаются без флага -v."),
                "example": "docker compose down",
                "sim": True,
            },
            {
                "cmd": "docker compose down -v",
                "desc": _t("То же плюс удаление томов — чистое состояние, данные пропадут."),
                "example": "docker compose down -v",
                "sim": False,
            },
            {
                "cmd": "docker compose build",
                "desc": _t("Пересобрать образы сервисов, у которых есть build: в compose.yml."),
                "example": "docker compose build",
                "sim": False,
            },
            {
                "cmd": "docker compose pull",
                "desc": _t("Скачать свежие образы сервисов перед обновлением."),
                "example": "docker compose pull",
                "sim": False,
            },
            {
                "cmd": "docker compose restart orion",
                "desc": _t("Перезапустить один сервис, остальные не трогать."),
                "example": "docker compose restart orion",
                "sim": False,
            },
            {
                "cmd": "docker compose exec orion sh",
                "desc": _t("Зайти в работающий сервис из compose-проекта."),
                "example": "docker compose exec orion sh",
                "sim": False,
            },
            {
                "cmd": "docker compose config",
                "desc": _t("Показать итоговый конфиг после подстановки переменных — удобно ловить опечатки."),
                "example": "docker compose config",
                "sim": False,
            },
        ],
    },
    {
        "id": "dockerfile",
        "title": "Dockerfile",
        "blurb": _t("Рецепт образа: каждая инструкция — слой. Меньше слоёв и раньше неизменяемое — быстрее сборка."),
        "commands": [
            {
                "cmd": "FROM python:3.12-slim",
                "desc": _t("Базовый образ, с которого начинается сборка. Первая инструкция файла."),
                "example": "FROM python:3.12-slim",
                "sim": False,
            },
            {
                "cmd": "WORKDIR /app",
                "desc": _t("Рабочий каталог для следующих инструкций и запуска."),
                "example": "WORKDIR /app",
                "sim": False,
            },
            {
                "cmd": "COPY . .",
                "desc": _t("Копировать файлы из контекста сборки в образ. COPY requirements.txt . — сначала зависимости, потом код."),
                "example": "COPY requirements.txt .",
                "sim": False,
            },
            {
                "cmd": "ADD archive.tar.gz /app",
                "desc": _t("Как COPY, но умеет распаковывать архивы и ходить по URL. Без нужды лучше COPY."),
                "example": "ADD archive.tar.gz /app",
                "sim": False,
            },
            {
                "cmd": "RUN pip install -r requirements.txt",
                "desc": _t("Выполнить команду при сборке. Каждый RUN — новый слой."),
                "example": "RUN pip install -r requirements.txt",
                "sim": False,
            },
            {
                "cmd": "CMD [\"python\", \"main.py\"]",
                "desc": _t("Что запускать по умолчанию. Перекрывается аргументами docker run."),
                "example": "CMD [\"python\", \"main.py\"]",
                "sim": False,
            },
            {
                "cmd": "ENTRYPOINT [\"python\"]",
                "desc": _t("Незыблемая точка входа: docker run образ main.py добавит аргумент к ней."),
                "example": "ENTRYPOINT [\"python\"]",
                "sim": False,
            },
            {
                "cmd": "EXPOSE 8080",
                "desc": _t("Документирует порт контейнера. Публикует его всё равно -p при запуске."),
                "example": "EXPOSE 8080",
                "sim": False,
            },
            {
                "cmd": "ENV MODE=production",
                "desc": _t("Переменная окружения внутри образа. Перекрывается флагом -e."),
                "example": "ENV MODE=production",
                "sim": False,
            },
            {
                "cmd": "ARG VERSION=1.0",
                "desc": _t("Переменная только на время сборки: docker build --build-arg VERSION=2.0."),
                "example": "ARG VERSION=1.0",
                "sim": False,
            },
            {
                "cmd": "VOLUME /data",
                "desc": _t("Объявить каталог данных: Docker создаст анонимный том, если не задан свой."),
                "example": "VOLUME /data",
                "sim": False,
            },
            {
                "cmd": "USER app",
                "desc": _t("Дальше процесс работает не от root — базовое требование безопасности."),
                "example": "USER app",
                "sim": False,
            },
            {
                "cmd": "HEALTHCHECK CMD curl -f http://localhost/ || exit 1",
                "desc": _t("Проверка живости: docker ps покажет healthy или unhealthy."),
                "example": "HEALTHCHECK CMD curl -f http://localhost/ || exit 1",
                "sim": False,
            },
            {
                "cmd": "LABEL maintainer=\"orion@ship\"",
                "desc": _t("Метка для людей и инструментов: автор, версия, назначение."),
                "example": "LABEL maintainer=\"orion@ship\"",
                "sim": False,
            },
            {
                "cmd": "docker build -f Dockerfile.prod -t ship/orion:1.0 .",
                "desc": _t("Собрать по файлу с другим именем."),
                "example": "docker build -f Dockerfile.prod -t ship/orion:1.0 .",
                "sim": False,
            },
        ],
    },
    {
        "id": "cleanup",
        "title": _t("Очистка"),
        "blurb": _t("Docker копит остановленные контейнеры, висячие образы и тома. Сначала посмотрите, что занимает место, потом удаляйте."),
        "commands": [
            {
                "cmd": "docker system df",
                "desc": _t("Сколько места занимают образы, контейнеры, тома и кеш сборки."),
                "example": "docker system df -v",
                "sim": False,
            },
            {
                "cmd": "docker system prune",
                "desc": _t("Убрать остановленные контейнеры, неиспользуемые сети и висячие образы."),
                "example": "docker system prune",
                "sim": True,
            },
            {
                "cmd": "docker system prune -a --volumes",
                "desc": _t("Самая сильная уборка: плюс все неиспользуемые образы и тома."),
                "example": "docker system prune -a --volumes",
                "sim": False,
            },
            {
                "cmd": "docker container prune",
                "desc": _t("Удалить только остановленные контейнеры."),
                "example": "docker container prune",
                "sim": False,
            },
            {
                "cmd": "docker image prune -a",
                "desc": _t("Удалить образы, на которые не ссылается ни один контейнер."),
                "example": "docker image prune -a",
                "sim": False,
            },
            {
                "cmd": "docker builder prune",
                "desc": _t("Очистить кеш сборки: иногда это десятки гигабайт."),
                "example": "docker builder prune",
                "sim": False,
            },
        ],
    },
    {
        "id": "useful",
        "title": _t("Полезное"),
        "blurb": _t("Мелочи, которые экономят время каждый день."),
        "commands": [
            {
                "cmd": "docker run --restart unless-stopped -d ship/radio",
                "desc": _t("Политика перезапуска: контейнер поднимется сам после падения или перезагрузки хоста."),
                "example": "docker run --restart unless-stopped -d ship/radio",
                "sim": False,
            },
            {
                "cmd": "docker logs --tail 100 -t my_orion",
                "desc": _t("Последние 100 строк с отметками времени."),
                "example": "docker logs --tail 100 -t my_orion",
                "sim": False,
            },
            {
                "cmd": "docker events",
                "desc": _t("Поток событий демона: кто запустился, умер, подключился к сети."),
                "example": "docker events --filter container=my_orion",
                "sim": False,
            },
            {
                "cmd": "docker exec -u root my_orion whoami",
                "desc": _t("Выполнить команду от конкретного пользователя, не заходя в оболочку."),
                "example": "docker exec -u root my_orion whoami",
                "sim": False,
            },
            {
                "cmd": "docker run --label team=orion ship/lab",
                "desc": _t("Метка на контейнере: по ней потом удобно фильтровать и удалять."),
                "example": "docker run -d --label team=orion ship/lab",
                "sim": False,
            },
            {
                "cmd": "docker ps --filter \"status=exited\"",
                "desc": _t("Фильтры вместо ручного перебора: по статусу, имени, метке, образу."),
                "example": "docker ps -a --filter \"status=exited\"",
                "sim": False,
            },
            {
                "cmd": "docker compose up -d --build",
                "desc": _t("Пересобрать образы и поднять проект — обычный деплой после правок."),
                "example": "docker compose up -d --build",
                "sim": False,
            },
            {
                "cmd": "docker update --memory 512m my_orion",
                "desc": _t("Поменять лимиты работающего контейнера без пересоздания."),
                "example": "docker update --memory 512m my_orion",
                "sim": False,
            },
        ],
    },
]

#: Две темы, которых не хватало в первом наборе: диагностика и данные.
EXTRA_TOPICS = [
    {
        "id": "debug",
        "title": "Отладка",
        "blurb": "«Не работает» — это всегда три вопроса: жив ли контейнер, что в логах, кто занял порт.",
        "commands": [
            {
                "cmd": "docker logs --tail 50 my_orion",
                "desc": "Последние 50 строк журнала: там причина падения, а не только приветствие.",
                "example": "docker logs --tail 50 my_orion",
                "sim": True,
            },
            {
                "cmd": "docker port radio_web 8080",
                "desc": "Проверить один порт: какой порт хоста смотрит внутрь контейнера.",
                "example": "docker port radio_web 8080",
                "sim": True,
            },
            {
                "cmd": "docker inspect --format '{{.State.Status}}' my_orion",
                "desc": "Полный JSON контейнера, но здесь — только статус: сеть, тома и лимиты смотрят без --format.",
                "example": "docker inspect --format '{{.State.Status}}' my_orion",
                "sim": False,
            },
            {
                "cmd": "docker stats --no-stream",
                "desc": "Снимок нагрузки: CPU, память, сеть, диск по каждому контейнеру.",
                "example": "docker stats --no-stream",
                "sim": False,
            },
            {
                "cmd": "docker system df -v",
                "desc": "Где кончилось место: подробно по образам, контейнерам и томам.",
                "example": "docker system df -v",
                "sim": False,
            },
        ],
    },
    {
        "id": "data",
        "title": "Данные и переменные",
        "blurb": "Контейнер можно пересоздать — данные должны остаться. Тома и переменные окружения задаются при запуске.",
        "commands": [
            {
                "cmd": "docker run -d -v ship_data:/data --name lab_data ship/lab",
                "desc": "Именованный том внутрь контейнера. Данные переживут docker rm.",
                "example": "docker run -d -v ship_data:/data --name lab_data ship/lab",
                "sim": True,
            },
            {
                "cmd": "docker run -d -v /var/lib/ship:/data --name lab_bind ship/lab",
                "desc": "Привязка к каталогу хоста: правки на хосте сразу видны контейнеру.",
                "example": "docker run -d -v /var/lib/ship:/data --name lab_bind ship/lab",
                "sim": True,
            },
            {
                "cmd": "docker run -d -e LOG_LEVEL=debug --name radio_fm ship/radio",
                "desc": "Переменная окружения контейнера — то, что читает приложение при старте.",
                "example": "docker run -d -e LOG_LEVEL=debug --name radio_fm ship/radio",
                "sim": True,
            },
            {
                "cmd": "docker run --env-file .env -d ship/lab",
                "desc": "Файл с переменными вместо десятка -e: удобно для стендов.",
                "example": "docker run --env-file .env -d ship/lab",
                "sim": False,
            },
        ],
    },
]

#: Теория по темам: короткие тезисы, которые панель показывает над командами.
THEORY = {
    "basics": [
        "Образ — шаблон, контейнер — его запущенный экземпляр; удалили контейнер — образ остался.",
        "Имя образа: репозиторий/имя:тег. Без тега подставляется latest.",
        "docker --help — список команд, docker run --help — флаги конкретной.",
    ],
    "containers": [
        "Жизненный цикл: create → start → running → stop → exited → rm.",
        "-d отпускает терминал: контейнер живёт в фоне, -it даёт оболочку.",
        "--name задаёт имя, иначе Docker выдаёт случайное вида ship_1a2b3c4d.",
    ],
    "images": [
        "Образ собирается слоями из Dockerfile; каждый слой кешируется.",
        "Правка раннего слоя сбрасывает кеш всех последующих — слои идут по порядку.",
        "Тег latest — не «самый свежий», а просто имя по умолчанию: лучше ставить версию.",
    ],
    "volumes": [
        "Том живёт на хосте и переживает контейнер; данные внутри слоя — нет.",
        "-v имя:/путь — именованный том, -v /хост:/путь — привязка к каталогу хоста.",
        "Тома нельзя удалить, пока их держит хотя бы один контейнер.",
    ],
    "networks": [
        "Своя сеть даёт DNS по имени контейнера: base доступен как base, а не по IP.",
        "Сеть по умолчанию bridge — без такого DNS: только IP, и тот меняется.",
        "Порт нужен снаружи только для входа с хоста; внутри сети хватает имени и порта.",
    ],
    "compose": [
        "compose.yml — описание сервисов, сетей и томов одного проекта.",
        "up -d поднимает всё, down останавливает и убирает; ps показывает состояние.",
        "Один файл — один проект: имя проекта задаёт префикс имён контейнеров.",
    ],
    "dockerfile": [
        "Dockerfile читается сверху вниз; каждая инструкция — новый слой.",
        "FROM — база, COPY — файлы, RUN — сборка, CMD — что запускать.",
        "Меньше слоёв и меньше лишнего в COPY — быстрее сборка и меньше образ.",
    ],
    "cleanup": [
        "prune удаляет неиспользуемое; без флагов — только остановленные контейнеры и висячие образы.",
        "-a расширяет уборку на все образы без контейнеров, --volumes — на тома.",
        "Перед уборкой полезно посмотреть docker system df: что именно занимает место.",
    ],
    "useful": [
        "--restart unless-stopped поднимает контейнер после падения и перезагрузки.",
        "--filter в ps заменяет ручной перебор: по статусу, имени, метке.",
        "--label помечает контейнер: потом их удаляют пачкой по метке.",
    ],
    "debug": [
        "Exited (0) — сам завершился; Exited (137) — убит, часто из-за памяти.",
        "Порт уже занят — ищите владельца: docker ps и ss -tulpn на хосте.",
        "Логи без --tail могут быть огромными: сначала хвост, потом всё остальное.",
    ],
    "data": [
        "Данные внутри контейнера живут до docker rm — это ловушка новичка.",
        "Именованный том удобнее привязки к каталогу: путь не зависит от машины.",
        "Секреты не кладут в -e на виду: для стенда сойдёт, для боя нужен secret.",
    ],
}
# fmt: on


def _all_topics() -> list[dict]:
    """Темы основного набора плюс добавленные, с подмешанной теорией."""
    out: list[dict] = []
    for topic_item in TOPICS + EXTRA_TOPICS:
        merged = dict(topic_item)
        merged["theory"] = list(THEORY.get(topic_item["id"], []))
        out.append(merged)
    return out


def topics() -> list[dict]:
    """Все темы учебника (для панели и тестов)."""
    return _all_topics()


def topic(topic_id: str) -> dict | None:
    for t in topics():
        if t["id"] == topic_id:
            return t
    return None


def commands(topic_id: str | None = None) -> list[dict]:
    """Команды одной темы или все подряд."""
    if topic_id is None:
        return [c for t in topics() for c in t["commands"]]
    t = topic(topic_id)
    return list(t["commands"]) if t else []


def total() -> int:
    return sum(len(t["commands"]) for t in topics())


def supported() -> list[dict]:
    """Команды, которые понимает учебный симулятор."""
    return [c for c in commands() if c.get("sim")]


def completions() -> list[str]:
    """Строки для автодополнения по Tab: начала команд учебника, без дублей."""
    out: list[str] = []
    for c in commands():
        head = " ".join(c["cmd"].split()[:2])
        if head.startswith("docker") and head not in out:
            out.append(head)
    return out


def search(query: str, topic_id: str | None = None) -> list[dict]:
    """Поиск по учебнику: все слова запроса должны найтись в команде или описании.

    Пустой запрос — просто команды выбранной темы (или все).
    """
    q = (query or "").strip().lower()
    items = commands(topic_id)
    if not q:
        return items
    words = q.split()
    return [c for c in items if all(w in (c["cmd"] + " " + c["desc"]).lower() for w in words)]
