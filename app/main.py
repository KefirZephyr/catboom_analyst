import asyncio
import logging
import os

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.bot import create_dispatcher
from config.logging import setup_logging
from config.settings import settings
from db.session import DatabaseUnavailableError, init_db

logger = logging.getLogger(__name__)


async def main() -> None:
    setup_logging()

    token = settings.bot_token.get_secret_value()
    if not token:
        logger.error("BOT_TOKEN is not configured")
        return

    if settings.auto_betting_enabled:
        logger.warning("AUTO_BETTING_ENABLED is ignored in v2 foundation")

    try:
        await init_db()
    except DatabaseUnavailableError as exc:
        logger.error("База данных недоступна: %s", exc)
        return
    except Exception as exc:
        logger.error("Не удалось инициализировать базу данных: %s", exc)
        return

    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = create_dispatcher()

    if os.getenv("CATBOOM_DRY_RUN") == "1":
        logger.info("CatBoom Dota Analyst v2 dry run completed")
        await bot.session.close()
        return

    logger.info("CatBoom Dota Analyst v2 started")
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
