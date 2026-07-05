# CatBoom Dota Analyst v2

Локальный Telegram-бот для аналитики Dota 2 ставок. Бот не делает автоматические ставки и не подключается к букмекерскому кабинету: он собирает данные, ищет value-сигналы, рассчитывает рекомендуемый размер ставки от банка и показывает пользователю рекомендации для ручного решения.

## Локальный запуск

1. Создайте виртуальное окружение:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Установите зависимости:

```powershell
pip install -r requirements.txt
```

3. Создайте `.env` по примеру `.env.example` и заполните значения.

4. Запустите бота:

```powershell
python -m app.main
```

Также можно использовать:

```powershell
python main.py
```

## Обязательные переменные окружения

- `BOT_TOKEN`
- `API_ID`
- `API_HASH`
- `PANDASCORE_TOKEN`
- `DATABASE_URL`
- `ADMIN_IDS`
- `WHITELIST_USER_IDS`

Секреты должны храниться только в локальном `.env`. Файл `.env` не должен попадать в git.

## Структура v2

- `app/` - точка входа, создание бота и будущий scheduler.
- `config/` - настройки и логирование.
- `db/` - async SQLAlchemy, SQLite-сессия и модели.
- `modules/telegram_parser/` - синхронизация Telegram-каналов и извлечение прогнозов.
- `modules/dota_data/` - провайдеры Dota 2 данных, включая PandaScore.
- `modules/analytics/` - рейтинги, прогнозы матчей, value и risk engine.
- `modules/bankroll/` - банк и размер ставки.
- `modules/recommendations/` - генерация сигналов и объяснений.
- `modules/bookmaker/` - только ручные/odds-only провайдеры без автоставок.
- `bot/routers/` - Telegram-интерфейс v2.
- `jobs/` - фоновые задачи синхронизации.
- `legacy/` - сохранённая первая версия проекта.

## Принцип безопасности

`AUTO_BETTING_ENABLED` должен оставаться `false`. Автоматические ставки, Selenium/Playwright для букмекера и подключение к букмекерскому кабинету в v2 не реализуются.
