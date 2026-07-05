from dataclasses import dataclass

from sqlalchemy import select

from db.models import DotaMatch, Team, TelegramPrediction
from db.session import async_session
from modules.telegram_parser.channel_rating import calculate_all_channels_stats


@dataclass(frozen=True)
class MatchProbability:
    model_probability_percent: float
    confidence_percent: float
    reason: str


async def estimate_match_probability(match_id: int, picked_team_id: int | None) -> MatchProbability:
    async with async_session() as session:
        match = await session.get(DotaMatch, match_id)
        if not match or not picked_team_id:
            return MatchProbability(50.0, 20.0, "Недостаточно данных о матче или пике")

        team_a = await session.get(Team, match.team_a_id) if match.team_a_id else None
        team_b = await session.get(Team, match.team_b_id) if match.team_b_id else None
        picked = await session.get(Team, picked_team_id)

        if not picked or not team_a or not team_b:
            return MatchProbability(50.0, 25.0, "Нет данных по одной из команд")

        predictions_result = await session.execute(
            select(TelegramPrediction).where(TelegramPrediction.match_id == match_id)
        )
        match_predictions = list(predictions_result.scalars().all())

    base_probability = probability_from_rating(team_a, team_b, picked_team_id)
    channel_adjustment, channel_confidence = await channel_signal_adjustment(match_predictions)
    model_probability = clamp(base_probability + channel_adjustment, 35.0, 75.0)

    data_points = 0
    if team_a.rating or team_b.rating:
        data_points += 1
    if match_predictions:
        data_points += 1
    if channel_confidence > 0:
        data_points += 1

    confidence = 40 + data_points * 12 + channel_confidence
    confidence = clamp(confidence, 20.0, 85.0)

    reason = (
        f"База по рейтингу команд: {base_probability:.1f}%. "
        f"Корректировка по Telegram-прогнозам: {channel_adjustment:+.1f}%."
    )
    return MatchProbability(round(model_probability, 2), round(confidence, 2), reason)


def probability_from_rating(team_a: Team, team_b: Team, picked_team_id: int) -> float:
    rating_a = team_a.rating or 0
    rating_b = team_b.rating or 0
    if rating_a <= 0 and rating_b <= 0:
        return 50.0

    total = max(rating_a + rating_b, 1)
    team_a_probability = (rating_a / total) * 100
    if picked_team_id == team_a.id:
        return team_a_probability
    return 100 - team_a_probability


async def channel_signal_adjustment(predictions: list[TelegramPrediction]) -> tuple[float, float]:
    if not predictions:
        return 0.0, 0.0

    channel_stats = {stats.channel_id: stats for stats in await calculate_all_channels_stats()}
    adjustments = []
    confidences = []
    for prediction in predictions:
        stats = channel_stats.get(prediction.channel_id)
        if not stats or stats.resolved_predictions < 3:
            continue
        adjustments.append(max(min(stats.roi_flat / 10, 5), -5))
        confidences.append(min(stats.resolved_predictions, 20) / 2)

    if not adjustments:
        return 0.0, 0.0
    return sum(adjustments) / len(adjustments), min(sum(confidences) / len(confidences), 15)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
