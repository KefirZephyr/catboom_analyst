import os
from dotenv import load_dotenv
from typing import List

load_dotenv()

# Секретные данные из .env
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///catboom_analyst.db")

# Предустановленные каналы
DEFAULT_CHANNELS = [
    {"username": "travobet", "url": "https://t.me/travobet", "name": "TraVo Bet"}
]

# Настройки парсинга
PARSING_KEYWORDS = [
    "прогноз",
    "ставка",
    "коэф",
    "коэффициент",
    "проход",
    "не прошла",
    "выиграл",
    "проиграл",
    "победа",
    "поражение",
    "✅",
    "❌",
    "🔥",
    "💰",
    "кф",
    "odds",
    "bet",
    "win",
    "loss",
    "зашла",
    "не зашла",
]

# Ключевые слова для результатов
RESULT_WIN_KEYWORDS = [
    "прошла",
    "выиграл",
    "победа",
    "плюс",
    "зашла",
    "прошёл",
    "проходит",
    "✅",
    "🟢",
    "💚",
    "🎉",
    "💰",
    "win",
    "won",
    "+",
    "плюсуем",
    "в плюс",
]

RESULT_LOSS_KEYWORDS = [
    "не прошла",
    "проиграл",
    "поражение",
    "минус",
    "не зашла",
    "не прошёл",
    "❌",
    "🔴",
    "💔",
    "😞",
    "loss",
    "lost",
    "-",
    "минусуем",
    "в минус",
]

# Периоды для быстрого выбора (в днях)
QUICK_PERIODS = [7, 30, 90]

# Настройки мониторинга (консервативные для стабильности)
MONITORING_INTERVAL = 60  # секунд между проверками
MAX_MESSAGES_CHECK = 5  # количество сообщений для проверки
RESULTS_UPDATE_INTERVAL = 3600  # обновление результатов каждый час
RESULTS_SEARCH_HOURS = 72  # поиск результатов в течение 72 часов после прогноза
EXPIRED_DAYS = 7  # прогнозы старше 7 дней помечаются как expired

# Настройки сканирования истории
HISTORY_SCAN_ENABLED = True
DEFAULT_HISTORY_DAYS = 30
MAX_HISTORY_DAYS = 90
HISTORY_SCAN_DELAY = 0.1
AUTO_SCAN_ON_ADD = False

# Настройки поиска результатов
MIN_COMMON_WORDS = 2
CONFIDENCE_THRESHOLD = 0.7
