import sqlite3
import asyncio
import aiosqlite
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text
from config.settings import DATABASE_URL, DEFAULT_CHANNELS
from database.models import Base, Channel, Prediction, User

logger = logging.getLogger(__name__)

# ИСПРАВЛЕНО: Убраны неподдерживаемые параметры для SQLite
if "sqlite://" in DATABASE_URL:
    db_url = DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://")
else:
    db_url = DATABASE_URL

# Простая конфигурация движка без проблемных параметров
engine = create_async_engine(
    db_url,
    echo=False,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,
    },
)

async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_database():
    """Инициализация базы данных с простой обработкой ошибок"""
    max_retries = 3

    for attempt in range(max_retries):
        try:
            # Создаем таблицы
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            # Добавление предустановленных каналов
            async with async_session() as session:
                for channel_data in DEFAULT_CHANNELS:
                    try:
                        # Проверяем существование канала
                        result = await session.execute(
                            select(Channel).where(
                                Channel.username == channel_data["username"]
                            )
                        )
                        existing = result.scalar_one_or_none()

                        if not existing:
                            channel = Channel(
                                username=channel_data["username"],
                                name=channel_data["name"],
                                url=channel_data["url"],
                            )
                            session.add(channel)
                    except Exception as e:
                        logger.warning(
                            f"⚠️ Ошибка добавления канала {channel_data['username']}: {e}"
                        )
                        continue

                await session.commit()

            logger.info("✅ База данных инициализирована")
            return

        except Exception as e:
            logger.error(
                f"❌ Попытка {attempt + 1}/{max_retries} инициализации БД: {e}"
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(1)
            else:
                logger.error("❌ Не удалось инициализировать базу данных")
                raise


class DatabaseManager:
    """Упрощенный менеджер базы данных"""

    @staticmethod
    async def safe_execute(operation, max_retries=3):
        """Безопасное выполнение операции с БД"""
        last_error = None

        for attempt in range(max_retries):
            try:
                async with async_session() as session:
                    result = await operation(session)
                    await session.commit()
                    return result

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Если база заблокирована, ждем и повторяем
                if "database is locked" in error_str or "locked" in error_str:
                    if attempt < max_retries - 1:
                        wait_time = 0.5 * (attempt + 1)
                        logger.warning(
                            f"⚠️ БД заблокирована, ждем {wait_time}с и повторяем..."
                        )
                        await asyncio.sleep(wait_time)
                        continue

                # Другие ошибки - прерываем
                break

        logger.error(f"❌ Ошибка БД после {max_retries} попыток: {last_error}")
        raise last_error


# Простая функция получения сессии
async def get_session():
    """Получение сессии базы данных"""
    return async_session()
