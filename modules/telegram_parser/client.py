import logging
from types import TracebackType

from telethon import TelegramClient

from config.settings import settings

logger = logging.getLogger(__name__)


def create_telegram_client(session_name: str = "catboom_dota_v2") -> TelegramClient:
    return TelegramClient(
        session_name,
        settings.api_id,
        settings.api_hash.get_secret_value(),
    )


class TelegramClientManager:
    def __init__(self, session_name: str = "catboom_dota_v2") -> None:
        self.client = create_telegram_client(session_name)

    async def start(self) -> TelegramClient:
        if not settings.api_id or not settings.api_hash.get_secret_value():
            raise RuntimeError("API_ID/API_HASH are not configured")
        await self.client.start()
        logger.info("Telethon client started")
        return self.client

    async def stop(self) -> None:
        if self.client.is_connected():
            await self.client.disconnect()
            logger.info("Telethon client stopped")

    async def __aenter__(self) -> TelegramClient:
        return await self.start()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.stop()
