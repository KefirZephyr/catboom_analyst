import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import Integer, func, select
from sqlalchemy.exc import IntegrityError

from config.settings import settings
from db.models import TelegramChannel, TelegramPrediction
from db.session import async_session
from modules.telegram_parser.client import TelegramClientManager
from modules.telegram_parser.prediction_extractor import extract_prediction

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChannelStats:
    channel_id: int
    username: str
    title: str | None
    total_predictions: int
    with_odds: int
    needs_review: int
    average_odds: float | None
    last_sync_at: datetime | None


@dataclass(frozen=True)
class ScanResult:
    channel_id: int
    username: str
    scanned_messages: int = 0
    saved_predictions: int = 0
    skipped_duplicates: int = 0
    error: str | None = None


def normalize_channel_username(username: str) -> str:
    return username.strip().lstrip("@")


async def ensure_default_channels() -> list[TelegramChannel]:
    async with async_session() as session:
        for username in settings.default_channels:
            normalized = normalize_channel_username(username)
            result = await session.execute(
                select(TelegramChannel).where(TelegramChannel.username == normalized)
            )
            if not result.scalar_one_or_none():
                session.add(TelegramChannel(username=normalized, title=f"@{normalized}"))

        await session.commit()

        result = await session.execute(select(TelegramChannel).order_by(TelegramChannel.username))
        return list(result.scalars().all())


async def add_channel(username: str) -> TelegramChannel:
    normalized = normalize_channel_username(username)
    if len(normalized) < 3:
        raise ValueError("Некорректный username канала")

    async with async_session() as session:
        result = await session.execute(
            select(TelegramChannel).where(TelegramChannel.username == normalized)
        )
        channel = result.scalar_one_or_none()
        if channel:
            return channel

        channel = TelegramChannel(username=normalized, title=f"@{normalized}", is_active=True)
        session.add(channel)
        await session.commit()
        await session.refresh(channel)
        return channel


async def list_channels() -> list[TelegramChannel]:
    await ensure_default_channels()
    async with async_session() as session:
        result = await session.execute(select(TelegramChannel).order_by(TelegramChannel.username))
        return list(result.scalars().all())


async def toggle_channel(channel_id: int) -> TelegramChannel | None:
    async with async_session() as session:
        channel = await session.get(TelegramChannel, channel_id)
        if not channel:
            return None
        channel.is_active = not channel.is_active
        await session.commit()
        await session.refresh(channel)
        return channel


async def scan_channel(channel_id: int) -> ScanResult:
    if not settings.api_id or not settings.api_hash.get_secret_value():
        return ScanResult(
            channel_id=channel_id,
            username="",
            error="Telegram API credentials не заданы. Проверьте API_ID и API_HASH в .env.",
        )

    async with async_session() as session:
        channel = await session.get(TelegramChannel, channel_id)
        if not channel:
            return ScanResult(channel_id=channel_id, username="", error="Канал не найден")

    async with TelegramClientManager() as client:
        return await scan_channel_with_client(client, channel)


async def scan_all_channels() -> list[ScanResult]:
    if not settings.api_id or not settings.api_hash.get_secret_value():
        return [
            ScanResult(
                channel_id=0,
                username="",
                error="Telegram API credentials не заданы. Проверьте API_ID и API_HASH в .env.",
            )
        ]

    channels = [channel for channel in await list_channels() if channel.is_active]
    results: list[ScanResult] = []

    async with TelegramClientManager() as client:
        for channel in channels:
            results.append(await scan_channel_with_client(client, channel))

    return results


async def scan_channel_with_client(client, channel: TelegramChannel) -> ScanResult:
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=settings.default_history_days)
    scanned_messages = 0
    saved_predictions = 0
    skipped_duplicates = 0

    try:
        entity = await client.get_entity(channel.username)
        title = getattr(entity, "title", None) or channel.title

        async for message in client.iter_messages(
            entity,
            limit=settings.telegram_history_message_limit,
            offset_date=datetime.now(timezone.utc),
        ):
            if not message or not message.message:
                continue

            message_date = message.date
            if message_date and message_date < cutoff_date:
                break

            scanned_messages += 1
            extracted = extract_prediction(message.message)
            if not extracted:
                continue

            was_saved = await save_prediction(channel.id, message.id, message_date, extracted)
            if was_saved:
                saved_predictions += 1
            else:
                skipped_duplicates += 1

        await mark_channel_scanned(channel.id, title=title, error=None)
        return ScanResult(
            channel_id=channel.id,
            username=channel.username,
            scanned_messages=scanned_messages,
            saved_predictions=saved_predictions,
            skipped_duplicates=skipped_duplicates,
        )
    except Exception as exc:
        error = str(exc)
        logger.warning("Channel scan failed for %s: %s", channel.username, error)
        await mark_channel_scanned(channel.id, title=channel.title, error=error)
        return ScanResult(channel_id=channel.id, username=channel.username, error=error)


async def save_prediction(channel_id: int, source_message_id: int, message_date, extracted) -> bool:
    prediction_id: int | None = None
    async with async_session() as session:
        exists = await session.execute(
            select(TelegramPrediction.id).where(
                TelegramPrediction.channel_id == channel_id,
                TelegramPrediction.source_message_id == source_message_id,
            )
        )
        if exists.scalar_one_or_none():
            return False

        prediction = TelegramPrediction(
            channel_id=channel_id,
            source_message_id=source_message_id,
            raw_text=extracted.raw_text,
            normalized_text=extracted.normalized_text,
            picked_team_name=extracted.picked_team_name,
            market_type=extracted.market_type,
            odds_value=extracted.odds,
            confidence=extracted.confidence,
            needs_review=extracted.needs_review,
            message_date=message_date.replace(tzinfo=None) if message_date else None,
        )
        session.add(prediction)

        try:
            await session.flush()
            prediction_id = prediction.id
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return False

    if prediction_id:
        from modules.telegram_parser.result_matcher import auto_match_prediction

        await auto_match_prediction(prediction_id)

        return True


async def mark_channel_scanned(channel_id: int, title: str | None, error: str | None) -> None:
    async with async_session() as session:
        channel = await session.get(TelegramChannel, channel_id)
        if not channel:
            return
        channel.title = title or channel.title
        channel.last_sync_at = datetime.utcnow()
        channel.last_error = error
        await session.commit()


async def get_channel_stats() -> list[ChannelStats]:
    await ensure_default_channels()
    async with async_session() as session:
        channels_result = await session.execute(
            select(TelegramChannel).order_by(TelegramChannel.username)
        )
        channels = channels_result.scalars().all()

        stats: list[ChannelStats] = []
        for channel in channels:
            totals = await session.execute(
                select(
                    func.count(TelegramPrediction.id),
                    func.count(TelegramPrediction.odds_value),
                    func.sum(TelegramPrediction.needs_review.cast(Integer)),
                    func.avg(TelegramPrediction.odds_value),
                ).where(TelegramPrediction.channel_id == channel.id)
            )
            total, with_odds, needs_review, average_odds = totals.one()
            stats.append(
                ChannelStats(
                    channel_id=channel.id,
                    username=channel.username,
                    title=channel.title,
                    total_predictions=total or 0,
                    with_odds=with_odds or 0,
                    needs_review=needs_review or 0,
                    average_odds=round(average_odds, 2) if average_odds else None,
                    last_sync_at=channel.last_sync_at,
                )
            )
        return stats


async def sync_channels() -> list[ScanResult]:
    await ensure_default_channels()
    return await scan_all_channels()
