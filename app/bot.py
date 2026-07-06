from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Dispatcher
from aiogram.types import TelegramObject, User as TelegramUser

from bot.routers import (
    data_update,
    matches,
    menu,
    players,
    predictions,
    settings as settings_router,
    teams,
    tournaments,
)
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
    dispatcher.include_router(tournaments.router)
    dispatcher.include_router(matches.router)
    dispatcher.include_router(teams.router)
    dispatcher.include_router(players.router)
    dispatcher.include_router(predictions.router)
    dispatcher.include_router(data_update.router)
    dispatcher.include_router(settings_router.router)
    return dispatcher
