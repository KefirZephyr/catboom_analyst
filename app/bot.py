from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Dispatcher
from aiogram.types import TelegramObject, User as TelegramUser

from bot.routers import bankroll, channels, matches, menu, settings as settings_router, signals
from config.settings import settings


class WhitelistMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: TelegramUser | None = data.get("event_from_user")
        allowed_ids = settings.allowed_user_ids

        if allowed_ids and user and user.id not in allowed_ids:
            bot = data.get("bot")
            if bot:
                await bot.send_message(
                    user.id,
                    "Доступ запрещён. Ваш Telegram ID не входит в ADMIN_IDS или WHITELIST_USER_IDS.",
                )
            return None

        return await handler(event, data)


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.update.middleware(WhitelistMiddleware())

    dispatcher.include_router(menu.router)
    dispatcher.include_router(matches.router)
    dispatcher.include_router(channels.router)
    dispatcher.include_router(signals.router)
    dispatcher.include_router(bankroll.router)
    dispatcher.include_router(settings_router.router)
    return dispatcher
