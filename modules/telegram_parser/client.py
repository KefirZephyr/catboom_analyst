from telethon import TelegramClient

from config.settings import settings


def create_telegram_client(session_name: str = "catboom_dota_v2") -> TelegramClient:
    return TelegramClient(
        session_name,
        settings.api_id,
        settings.api_hash.get_secret_value(),
    )
