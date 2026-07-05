from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config.settings import settings
from db.base import Base
from db.models import (
    BankrollSettings,
    BetOrder,
    DotaMatch,
    Odds,
    Signal,
    Team,
    TeamAlias,
    TelegramChannel,
    TelegramPrediction,
    Tournament,
    User,
)

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class DatabaseUnavailableError(RuntimeError):
    pass


async def init_db() -> None:
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            if settings.database_url.startswith("sqlite"):
                await ensure_sqlite_columns(connection)
    except Exception as exc:
        raise DatabaseUnavailableError(str(exc)) from exc


async def ensure_sqlite_columns(connection) -> None:
    table_columns = {
        "telegram_predictions": {
            "source_message_id": "INTEGER",
            "raw_text": "TEXT",
            "normalized_text": "TEXT",
            "market_type": "VARCHAR(64)",
            "picked_team_name": "VARCHAR(255)",
            "odds_value": "FLOAT",
            "confidence": "FLOAT DEFAULT 0",
            "needs_review": "BOOLEAN DEFAULT 0",
            "match_id": "INTEGER",
            "picked_team_id": "INTEGER",
            "match_confidence": "FLOAT DEFAULT 0",
            "match_reason": "VARCHAR(500)",
            "status": "VARCHAR(32) DEFAULT 'pending'",
            "message_date": "DATETIME",
        },
        "telegram_channels": {
            "title": "VARCHAR(255)",
            "rating": "FLOAT DEFAULT 0",
            "last_error": "VARCHAR(500)",
            "created_at": "DATETIME",
            "last_sync_at": "DATETIME",
        },
        "teams": {
            "acronym": "VARCHAR(64)",
            "image_url": "VARCHAR(500)",
            "updated_at": "DATETIME",
        },
        "tournaments": {
            "league_name": "VARCHAR(255)",
            "serie_name": "VARCHAR(255)",
            "updated_at": "DATETIME",
        },
        "matches": {
            "ends_at": "DATETIME",
            "team_a_score": "INTEGER",
            "team_b_score": "INTEGER",
            "raw_name": "VARCHAR(500)",
            "updated_at": "DATETIME",
        },
        "signals": {
            "picked_team_id": "INTEGER",
            "odds_value": "FLOAT",
            "model_probability_percent": "FLOAT DEFAULT 0",
            "bookmaker_probability_percent": "FLOAT DEFAULT 0",
            "stake_percent": "FLOAT DEFAULT 0",
            "risk_level": "VARCHAR(32) DEFAULT 'medium'",
        },
    }

    for table_name, columns in table_columns.items():
        existing = await connection.exec_driver_sql(f"PRAGMA table_info({table_name})")
        existing_names = {row[1] for row in existing.fetchall()}
        for column_name, column_type in columns.items():
            if column_name not in existing_names:
                await connection.exec_driver_sql(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                )
