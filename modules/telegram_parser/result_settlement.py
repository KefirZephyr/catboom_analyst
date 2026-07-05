from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from db.models import DotaMatch, TelegramPrediction
from db.session import async_session

SETTLED_STATUSES = {"win", "loss", "void"}
VOID_MATCH_STATUSES = {"canceled", "not_played"}
SUPPORTED_MARKETS = {"match_winner", "maps_total"}


@dataclass(slots=True)
class SettlementSummary:
    checked: int = 0
    wins: int = 0
    losses: int = 0
    voids: int = 0
    skipped: int = 0
    errors: int = 0


def is_prediction_eligible(prediction: TelegramPrediction) -> bool:
    if prediction.status != "pending" or prediction.match_id is None:
        return False
    if prediction.market_type == "match_winner":
        return prediction.picked_team_id is not None
    if prediction.market_type == "maps_total":
        return prediction.market_side in {"over", "under"} and prediction.market_line is not None
    return False


def settle_prediction_result(prediction: TelegramPrediction, match: DotaMatch | None) -> str | None:
    if match is None:
        return None

    if match.status in VOID_MATCH_STATUSES:
        return "void"

    if match.status != "finished":
        return None

    if prediction.market_type == "match_winner" and match.winner_team_id:
        return "win" if prediction.picked_team_id == match.winner_team_id else "loss"

    if prediction.market_type == "maps_total":
        if (
            prediction.market_side not in {"over", "under"}
            or prediction.market_line is None
            or match.team_a_score is None
            or match.team_b_score is None
        ):
            return None

        total_maps = match.team_a_score + match.team_b_score
        if total_maps == prediction.market_line:
            return "void"
        if prediction.market_side == "over":
            return "win" if total_maps > prediction.market_line else "loss"
        return "win" if total_maps < prediction.market_line else "loss"

    return None


def apply_settlement(prediction: TelegramPrediction, result_status: str, resolved_at: datetime) -> None:
    prediction.status = result_status
    prediction.updated_at = resolved_at
    if result_status in SETTLED_STATUSES:
        prediction.resolved_at = resolved_at


async def settle_predictions() -> SettlementSummary:
    summary = SettlementSummary()
    now = datetime.utcnow()

    async with async_session() as session:
        result = await session.execute(
            select(TelegramPrediction).where(
                TelegramPrediction.status == "pending",
                TelegramPrediction.match_id.is_not(None),
                TelegramPrediction.market_type.in_(SUPPORTED_MARKETS),
            )
        )
        predictions = result.scalars().all()

        for prediction in predictions:
            summary.checked += 1
            try:
                match = await session.get(DotaMatch, prediction.match_id)
                result_status = settle_prediction_result(prediction, match)

                if result_status is None:
                    summary.skipped += 1
                    continue

                apply_settlement(prediction, result_status, now)
                if result_status == "win":
                    summary.wins += 1
                elif result_status == "loss":
                    summary.losses += 1
                elif result_status == "void":
                    summary.voids += 1
            except Exception:
                summary.errors += 1

        await session.commit()

    return summary
