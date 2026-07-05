import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None

if load_dotenv and os.getenv("CATBOOM_SKIP_DOTENV") != "1":
    load_dotenv()


class SecretValue:
    def __init__(self, value: str = "") -> None:
        self._value = value

    def get_secret_value(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "SecretValue('**********')" if self._value else "SecretValue('')"


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _env_int(name: str, default: int = 0) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    value = _env(name, str(default)).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _env_int_list(name: str) -> list[int]:
    values = []
    for item in _env(name).split(","):
        item = item.strip()
        if item.isdigit():
            values.append(int(item))
    return values


def _env_str_list(name: str, default: str = "") -> list[str]:
    return [item.strip().lstrip("@") for item in _env(name, default).split(",") if item.strip()]


def _database_url() -> str:
    value = _env("DATABASE_URL", "sqlite+aiosqlite:///./catboom_analyst.db")
    if value.startswith("sqlite:///"):
        return value.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return value


@dataclass(frozen=True)
class Settings:
    bot_token: SecretValue = field(default_factory=lambda: SecretValue(_env("BOT_TOKEN")))
    api_id: int = field(default_factory=lambda: _env_int("API_ID"))
    api_hash: SecretValue = field(default_factory=lambda: SecretValue(_env("API_HASH")))
    pandascore_token: SecretValue = field(
        default_factory=lambda: SecretValue(_env("PANDASCORE_TOKEN"))
    )
    pandascore_base_url: str = field(
        default_factory=lambda: _env("PANDASCORE_BASE_URL", "https://api.pandascore.co")
    )

    database_url: str = field(default_factory=_database_url)

    admin_ids: list[int] = field(default_factory=lambda: _env_int_list("ADMIN_IDS"))
    whitelist_user_ids: list[int] = field(
        default_factory=lambda: _env_int_list("WHITELIST_USER_IDS")
    )

    app_timezone: str = field(default_factory=lambda: _env("APP_TIMEZONE", "Europe/Moscow"))
    currency: str = field(default_factory=lambda: _env("CURRENCY", "RUB"))
    start_bankroll: float = field(default_factory=lambda: _env_float("START_BANKROLL", 10000))
    risk_profile: str = field(default_factory=lambda: _env("RISK_PROFILE", "normal"))
    max_bet_percent: float = field(default_factory=lambda: _env_float("MAX_BET_PERCENT", 1))
    max_daily_loss_percent: float = field(
        default_factory=lambda: _env_float("MAX_DAILY_LOSS_PERCENT", 3)
    )
    max_open_bets: int = field(default_factory=lambda: _env_int("MAX_OPEN_BETS", 6))
    min_edge_percent: float = field(default_factory=lambda: _env_float("MIN_EDGE_PERCENT", 3))
    min_confidence_percent: float = field(
        default_factory=lambda: _env_float("MIN_CONFIDENCE_PERCENT", 60)
    )
    auto_betting_enabled: bool = field(
        default_factory=lambda: _env_bool("AUTO_BETTING_ENABLED", False)
    )

    default_channels: list[str] = field(
        default_factory=lambda: _env_str_list(
            "DEFAULT_CHANNELS",
            "travobet,StrayDungeon228,GoDota2Bets,doto2_bets,godlike_tips",
        )
    )
    default_history_days: int = field(default_factory=lambda: _env_int("DEFAULT_HISTORY_DAYS", 30))
    telegram_history_message_limit: int = field(
        default_factory=lambda: _env_int("TELEGRAM_HISTORY_MESSAGE_LIMIT", 500)
    )
    match_sync_interval_minutes: int = field(
        default_factory=lambda: _env_int("MATCH_SYNC_INTERVAL_MINUTES", 15)
    )

    @property
    def allowed_user_ids(self) -> set[int]:
        return set(self.admin_ids) | set(self.whitelist_user_ids)


settings = Settings()
