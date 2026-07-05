from dataclasses import dataclass

from sqlalchemy import select

from config.settings import settings
from db.models import Signal, TelegramPrediction
from db.session import async_session
from modules.analytics.match_prediction import estimate_match_probability
from modules.analytics.value_detector import detect_value
from modules.bankroll.bankroll_manager import get_or_create_bankroll_settings
from modules.bankroll.stake_sizer import StakeRecommendation, calculate_recommended_stake
from modules.recommendations.explanation_builder import build_explanation


@dataclass(frozen=True)
class SignalGenerationResult:
    signal: Signal | None
    reason: str


async def generate_signal_for_prediction(
    prediction_id: int,
    user_id: int = 0,
) -> SignalGenerationResult:
    async with async_session() as session:
        prediction = await session.get(TelegramPrediction, prediction_id)
        if not prediction:
            return SignalGenerationResult(None, "Прогноз не найден")
        if not prediction.match_id or not prediction.picked_team_id:
            return SignalGenerationResult(None, "Прогноз не привязан к матчу")
        if prediction.market_type not in {"match_winner", "maps_total"}:
            return SignalGenerationResult(None, "Рынок не поддерживается в MVP")
        if not prediction.odds_value:
            return SignalGenerationResult(None, "Коэффициент не найден")

        existing = await session.execute(
            select(Signal).where(
                Signal.match_id == prediction.match_id,
                Signal.market_type == prediction.market_type,
                Signal.selection == (prediction.picked_team_name or str(prediction.picked_team_id)),
                Signal.status != "skipped",
            )
        )
        if existing.scalar_one_or_none():
            return SignalGenerationResult(None, "Сигнал уже существует")

    probability = await estimate_match_probability(prediction.match_id, prediction.picked_team_id)
    if probability.confidence_percent < settings.min_confidence_percent:
        return SignalGenerationResult(None, "Confidence ниже минимального порога")

    value = detect_value(probability.model_probability_percent, prediction.odds_value)
    if not value.is_value:
        return SignalGenerationResult(None, "Edge ниже минимального порога")

    bankroll = await get_or_create_bankroll_settings(user_id)
    stake = calculate_recommended_stake(
        bankroll,
        edge_percent=value.edge_percent,
        confidence_percent=probability.confidence_percent,
    )
    assert isinstance(stake, StakeRecommendation)

    async with async_session() as session:
        signal = Signal(
            match_id=prediction.match_id,
            prediction_id=prediction.id,
            market_type=prediction.market_type,
            selection=prediction.picked_team_name or str(prediction.picked_team_id),
            picked_team_id=prediction.picked_team_id,
            odds_value=prediction.odds_value,
            model_probability_percent=probability.model_probability_percent,
            bookmaker_probability_percent=value.bookmaker_probability_percent,
            edge_percent=value.edge_percent,
            confidence_percent=probability.confidence_percent,
            stake_percent=stake.stake_percent,
            recommended_stake=stake.stake_amount,
            risk_level=stake.risk_level,
            explanation=build_explanation(value.edge_percent, probability.confidence_percent)
            + "\n"
            + probability.reason,
            status="new",
        )
        session.add(signal)
        await session.commit()
        await session.refresh(signal)
        return SignalGenerationResult(signal, "Сигнал создан")


async def generate_signals_for_ready_predictions(user_id: int = 0) -> list[SignalGenerationResult]:
    async with async_session() as session:
        result = await session.execute(
            select(TelegramPrediction).where(
                TelegramPrediction.match_id.is_not(None),
                TelegramPrediction.picked_team_id.is_not(None),
                TelegramPrediction.needs_review == False,
                TelegramPrediction.odds_value.is_not(None),
            )
        )
        predictions = list(result.scalars().all())

    results = []
    for prediction in predictions:
        results.append(await generate_signal_for_prediction(prediction.id, user_id=user_id))
    return results
