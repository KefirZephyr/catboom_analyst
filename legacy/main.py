import asyncio
import logging
import signal
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault
from config.settings import BOT_TOKEN
from database.database import init_database
from handlers import main_menu, channels, statistics, notifications
from utils.parser import start_channel_monitoring

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def set_bot_commands(bot: Bot):
    """Установка команд бота - только start и help"""
    commands = [
        BotCommand(command="start", description="🏠 Главное меню"),
        BotCommand(command="help", description="❓ Справка по использованию"),
    ]

    await bot.set_my_commands(commands, BotCommandScopeDefault())
    logger.info("✅ Команды бота установлены: /start и /help")


async def main():
    """Главная функция запуска бота"""
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не найден в .env файле!")
        return

    try:
        # Инициализация бота
        bot = Bot(
            token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )

        # Добавляем хранилище для FSM
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)

        # Инициализация базы данных
        logger.info("🔧 Инициализация базы данных...")
        await init_database()

        # Установка команд бота
        await set_bot_commands(bot)

        # Регистрация роутеров
        dp.include_router(main_menu.router)
        dp.include_router(channels.router)
        dp.include_router(statistics.router)
        dp.include_router(notifications.router)

        # Запуск мониторинга каналов в фоне
        logger.info("📡 Запуск мониторинга каналов...")
        monitoring_task = asyncio.create_task(start_channel_monitoring(bot))

        logger.info("🚀 CatBoom Analyst запущен и готов к работе!")

        # Запуск polling
        await dp.start_polling(bot)

    except KeyboardInterrupt:
        logger.info("👋 Получен сигнал остановки")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
    finally:
        try:
            # Остановка мониторинга
            from utils.parser import stop_monitoring

            stop_monitoring()

            # Закрываем сессию бота
            await bot.session.close()
            logger.info("✅ Бот корректно остановлен")
        except Exception as e:
            logger.error(f"❌ Ошибка при остановке: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")
