from dataclasses import dataclass

from sqlalchemy import select

from db.models import TelegramChannel, TelegramPrediction
from db.session import async_session

RESOLVED_WIN_STATUSES = {"win", "won"}
RESOLVED_LOSS_STATUSES = {"loss", "lost"}
RESOLVED_VOID_STATUSES = {"void", "refund", "push"}
RESOLVED_STATUSES = RESOLVED_WIN_STATUSES | RESOLVED_LOSS_STATUSES | RESOLVED_VOID_STATUSES


@dataclass(frozen=True)
class ChannelRatingStats:
    channel_id: int
    username: str
    title: str | None
    total_predictions: int
    resolved_predictions: int
    pending_predictions: int
    needs_review_predictions: int
    win_count: int
    loss_count: int
    winrate: float
    avg_odds: float
    profit_flat: float
    roi_flat: float
    best_market: str | None
    worst_market: str | None
    rating_score: float
    rating_grade: str
    last_sync_at: object | None


async def calculate_channel_stats(channel_id: int) -> ChannelRatingStats | None:
    async with async_session() as session:
        channel = await session.get(TelegramChannel, channel_id)
        if not channel:
            return None

        result = await session.execute(
            select(TelegramPrediction).where(TelegramPrediction.channel_id == channel_id)
        )
        predictions = list(result.scalars().all())

    return build_channel_stats(channel, predictions)


async def calculate_all_channels_stats() -> list[ChannelRatingStats]:
    async with async_session() as session:
        channels_result = await session.execute(
            select(TelegramChannel).order_by(TelegramChannel.username)
        )
        channels = list(channels_result.scalars().all())

        stats: list[ChannelRatingStats] = []
        for channel in channels:
            predictions_result = await session.execute(
                select(TelegramPrediction).where(TelegramPrediction.channel_id == channel.id)
            )
            stats.append(build_channel_stats(channel, list(predictions_result.scalars().all())))

    return sorted(stats, key=lambda item: item.rating_score, reverse=True)


def build_channel_stats(
    channel: TelegramChannel,
    predictions: list[TelegramPrediction],
) -> ChannelRatingStats:
    total_predictions = len(predictions)
    resolved = [prediction for prediction in predictions if prediction.status in RESOLVED_STATUSES]
    pending_predictions = len(
        [prediction for prediction in predictions if prediction.status not in RESOLVED_STATUSES]
    )
    needs_review_predictions = len([prediction for prediction in predictions if prediction.needs_review])
    win_count = len([prediction for prediction in resolved if prediction.status in RESOLVED_WIN_STATUSES])
    loss_count = len([prediction for prediction in resolved if prediction.status in RESOLVED_LOSS_STATUSES])
    resolved_predictions = len(resolved)

    winrate = round((win_count / resolved_predictions) * 100, 1) if resolved_predictions else 0.0
    odds_values = [prediction.odds_value for prediction in predictions if prediction.odds_value]
    avg_odds = round(sum(odds_values) / len(odds_values), 2) if odds_values else 0.0
    profit_flat = round(sum(flat_profit(prediction) for prediction in resolved), 2)
    roi_flat = round((profit_flat / resolved_predictions) * 100, 1) if resolved_predictions else 0.0
    best_market, worst_market = calculate_market_edges(resolved)
    rating_score = calculate_channel_rating(
        total_predictions=total_predictions,
        resolved_predictions=resolved_predictions,
        winrate=winrate,
        roi_flat=roi_flat,
        needs_review_predictions=needs_review_predictions,
    )

    return ChannelRatingStats(
        channel_id=channel.id,
        username=channel.username,
        title=channel.title,
        total_predictions=total_predictions,
        resolved_predictions=resolved_predictions,
        pending_predictions=pending_predictions,
        needs_review_predictions=needs_review_predictions,
        win_count=win_count,
        loss_count=loss_count,
        winrate=winrate,
        avg_odds=avg_odds,
        profit_flat=profit_flat,
        roi_flat=roi_flat,
        best_market=best_market,
        worst_market=worst_market,
        rating_score=rating_score,
        rating_grade=rating_grade(rating_score),
        last_sync_at=channel.last_sync_at,
    )


def flat_profit(prediction: TelegramPrediction) -> float:
    if prediction.status in RESOLVED_WIN_STATUSES:
        return (prediction.odds_value or 1.0) - 1.0
    if prediction.status in RESOLVED_LOSS_STATUSES:
        return -1.0
    return 0.0


def calculate_market_edges(predictions: list[TelegramPrediction]) -> tuple[str | None, str | None]:
    market_totals: dict[str, list[float]] = {}
    for prediction in predictions:
        market = prediction.market_type or "unknown"
        market_totals.setdefault(market, []).append(flat_profit(prediction))

    if not market_totals:
        return None, None

    market_roi = {
        market: (sum(profits) / len(profits)) * 100 for market, profits in market_totals.items()
    }
    best_market = max(market_roi, key=market_roi.get)
    worst_market = min(market_roi, key=market_roi.get)
    return format_market(best_market, market_roi[best_market]), format_market(
        worst_market, market_roi[worst_market]
    )


def format_market(market: str, roi: float) -> str:
    return f"{market} ({roi:.1f}% ROI)"


def calculate_channel_rating(
    total_predictions: int,
    resolved_predictions: int,
    winrate: float,
    roi_flat: float,
    needs_review_predictions: int,
) -> float:
    if total_predictions <= 0:
        return 0.0

    sample_factor = min(resolved_predictions / 30, 1.0)
    roi_score = max(min((roi_flat + 50) / 100, 1.0), 0.0) * 45
    winrate_score = max(min(winrate / 100, 1.0), 0.0) * 35
    sample_score = sample_factor * 15
    review_penalty = min(needs_review_predictions / total_predictions, 1.0) * 10
    score = roi_score + winrate_score + sample_score - review_penalty
    return round(max(min(score, 100), 0), 1)


def rating_grade(score: float) -> str:
    if score >= 80:
        return "A"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    return "D"
