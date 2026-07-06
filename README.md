# CatBoom Dota Analyst v2

Локальный Telegram-бот для аналитики Dota 2 матчей. Бот помогает смотреть турниры, будущие и завершённые матчи, форму команд, доступные данные по игрокам и аналитический прогноз победителя матча.

Проект не подключается к букмекерским сервисам, не выполняет автоматические действия с внешними аккаунтами и не даёт гарантий результата. Все выводы являются аналитической оценкой на основе доступных данных.

## Возможности MVP

- 🏆 Турниры: текущие и ближайшие турниры, матчи выбранного турнира.
- 📅 Матчи: live, сегодня, завтра, предстоящие и завершённые матчи.
- 👥 Команды: карточка команды, последние матчи, форма за 5 и 10 матчей, результаты в текущем турнире.
- 🎮 Игроки: реальные данные о составе, если они доступны в ответах PandaScore.
- 🔮 Прогнозы: оценка вероятности победителя будущего матча по форме команд, турниру, очным встречам и силе расписания.
- 🔄 Обновить данные: синхронизация матчей, турниров, команд и доступных составов через PandaScore.

## Установка

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Настройка `.env`

Создайте `.env` из `.env.example` и заполните:

```text
BOT_TOKEN=...
PANDASCORE_TOKEN=...
DATABASE_URL=sqlite+aiosqlite:///./catboom_analyst.db
ADMIN_IDS=123456789
WHITELIST_USER_IDS=123456789
```

Обязательные поля:

- `BOT_TOKEN` - токен Telegram-бота от BotFather.
- `PANDASCORE_TOKEN` - токен PandaScore API для загрузки Dota 2 данных.

Опциональные поля:

- `ADMIN_IDS` и `WHITELIST_USER_IDS` - Telegram ID пользователей, которым разрешён доступ. Если списки пустые, локальный доступ не ограничивается.
- `APP_TIMEZONE` - часовой пояс для отображения времени матчей, по умолчанию `Europe/Moscow`.

`API_ID` и `API_HASH` могут оставаться пустыми: основной сценарий бота больше не требует Telethon phone login.

## Запуск

```powershell
python -m app.main
```

Альтернативно:

```powershell
python main.py
```

Проверка запуска без подключения к Telegram polling:

```powershell
$env:CATBOOM_DRY_RUN='1'
python -m app.main
Remove-Item Env:CATBOOM_DRY_RUN
```

## Первый сценарий использования

1. Запустите бота.
2. Откройте `/start`.
3. Нажмите `🔄 Обновить данные`.
4. Запустите синхронизацию PandaScore.
5. Откройте разделы `🏆 Турниры`, `📅 Матчи`, `👥 Команды` или `🔮 Прогнозы`.

## Главное меню

- `🏆 Турниры`
- `📅 Матчи`
- `👥 Команды`
- `🎮 Игроки`
- `🔮 Прогнозы`
- `🔄 Обновить данные`
- `⚙️ Настройки`

## Аналитический прогноз

Для будущего матча бот рассчитывает вероятность победителя по нескольким факторам:

- `winrate_last_5`
- `winrate_last_10`
- `tournament_winrate`
- `head_to_head`
- `strength_of_schedule`, если по соперникам есть история матчей

Если данных мало, уверенность прогноза будет ниже. Игроки и составы показываются только при наличии реальных данных из API.

## Ручные job-команды

```powershell
python -m jobs.sync_matches
```

## Windows-запуск через ярлык

Создать ярлык на рабочем столе:

```powershell
powershell -ExecutionPolicy Bypass -File .\create_desktop_shortcut.ps1
```

Ярлык запускает `run_bot.bat`, создаёт `.venv`, устанавливает зависимости и стартует:

```powershell
python -m app.main
```

## Создание Pull Request одной командой

Нужен GitHub CLI `gh` с авторизацией:

```powershell
powershell -ExecutionPolicy Bypass -File .\create_pr.ps1
```

С параметрами:

```powershell
powershell -ExecutionPolicy Bypass -File .\create_pr.ps1 -Branch chore/my-branch -Title "My PR title" -CommitMessage "My commit message" -BaseBranch main
```

Скрипт запускает проверки, делает commit, push и создаёт Pull Request. Merge и force push скрипт не выполняет.

## Проверки

```powershell
python -m compileall .
python -c "from config.settings import settings; print('settings ok')"
pytest
```

## Безопасность

- `.env`, локальная база, session-файлы, виртуальное окружение, кеши и логи не должны попадать в git.
- Реальные токены нельзя публиковать в README, логах или отчётах.
- Интеграции с букмекерскими сервисами и автоматические действия не реализуются.
