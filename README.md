# CatBoom Dota Analyst v2

Локальный Telegram-бот для аналитики Dota 2 матчей и прогнозов. Бот не делает автоматические ставки, не подключается к букмекерскому кабинету и не даёт гарантий прибыли. Он собирает данные, помогает оценивать Telegram-каналы, ищет value-сигналы и рассчитывает размер ставки для ручного решения пользователя.

## Установка

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Настройка `.env`

Создайте `.env` из `.env.example` и заполните значения:

```text
BOT_TOKEN=...
API_ID=...
API_HASH=...
PANDASCORE_TOKEN=...
DATABASE_URL=sqlite+aiosqlite:///./catboom_analyst.db
ADMIN_IDS=123456789
WHITELIST_USER_IDS=123456789
```

Поля, которые нужно заполнить вручную:

- `BOT_TOKEN` - токен Telegram-бота от BotFather.
- `API_ID` и `API_HASH` - Telegram API credentials для Telethon.
- `PANDASCORE_TOKEN` - токен PandaScore API для матчей Dota 2.
- `ADMIN_IDS` и `WHITELIST_USER_IDS` - Telegram ID пользователей, которым разрешён доступ.

`PANDASCORE_TOKEN` нужен для загрузки матчей Dota 2. Если токен не задан, бот запустится, но раздел матчей покажет понятную ошибку при синхронизации.
Если `API_ID` или `API_HASH` не заполнены, бот запустится, но сканирование Telegram-каналов будет недоступно до заполнения этих полей.

## Запуск

```powershell
python -m app.main
```

Альтернативно:

```powershell
python main.py
```

Проверка запуска без подключения к Telegram:

```powershell
$env:CATBOOM_DRY_RUN='1'
python -m app.main
```

## Первое сканирование каналов

1. Запустите бота.
2. Откройте `/start`.
3. Перейдите в `Telegram-каналы`.
4. Нажмите `Сканировать все`.
5. Если Telethon ещё не авторизован, выполните локальную авторизацию Telegram API в консоли.

Session-файлы Telethon не коммитятся: `*.session` и `*.session-journal` находятся в `.gitignore`.

## Разделы

### Матчи

- `Live` - текущие матчи из локальной базы.
- `Сегодня` - матчи на текущий день по `Europe/Moscow`.
- `Ближайшие` - будущие матчи.
- `Турниры` - список турниров.
- `Синхронизировать` - ручная загрузка данных PandaScore.

### Telegram-каналы

- Список каналов.
- Добавление канала.
- Включение/выключение канала.
- Сканирование канала или всех каналов.
- Рейтинг каналов по winrate и ROI.

ROI считается по flat stake 1 unit на каждый рассчитанный прогноз.

### Банк

- Просмотр текущего банка.
- Изменение банка.
- Просмотр дневного лимита риска и открытых ставок.
- Смена risk profile: `low`, `normal`, `high`.

### Сигналы

- Генерация value-сигналов.
- Просмотр карточки сигнала.
- Ручное принятие ставки.
- Изменение рекомендуемой суммы.
- Пропуск сигнала.
- Ручная проверка прогнозов, которые не удалось уверенно привязать к матчу.

## Ручные job-команды

```powershell
python -m jobs.sync_matches
python -m jobs.generate_signals
```

## Проверки

```powershell
python -m compileall .
pytest
```

## Безопасность

- `.env`, базы, session-файлы, логи и виртуальные окружения не должны попадать в git.
- `AUTO_BETTING_ENABLED=false`.
- Автоставки, Selenium/Playwright для букмекера и подключение к букмекерскому кабинету не реализуются.

## Запуск на Windows через ярлык

1. Заполните локальный `.env` по шаблону `.env.example`.
2. Откройте PowerShell из папки проекта обычным пользователем.
3. Выполните:

```powershell
powershell -ExecutionPolicy Bypass -File .\create_desktop_shortcut.ps1
```

4. На рабочем столе появится ярлык `CatBoom Dota Analyst v2`.
5. Запускайте бота двойным кликом по ярлыку.

Ярлык запускает `run_bot.bat`. Скрипт работает из папки проекта, проверяет наличие `.env`, создаёт `.venv`, если его ещё нет, устанавливает зависимости из `requirements.txt` и запускает:

```powershell
python -m app.main
```

В `.env` вручную нужно заполнить секретные и персональные поля: `BOT_TOKEN`, `API_ID`, `API_HASH`, `PANDASCORE_TOKEN`, `ADMIN_IDS`, `WHITELIST_USER_IDS`. Не публикуйте реальные значения этих переменных и не добавляйте `.env` в git.
