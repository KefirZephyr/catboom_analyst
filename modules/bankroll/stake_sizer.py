from dataclasses import dataclass

from config.settings import settings
from db.models import BankrollSettings


@dataclass(frozen=True)
class StakeRecommendation:
    stake_percent: float
    stake_amount: float
    risk_level: str


def classify_risk(edge_percent: float, confidence_percent: float) -> str:
    if edge_percent >= 8 and confidence_percent >= 75:
        return "low"
    if edge_percent >= 5 and confidence_percent >= 65:
        return "medium"
    return "high"


def calculate_recommended_percent(
    edge_percent: float,
    confidence_percent: float,
    risk_profile: str = "normal",
    max_bet_percent: float | None = None,
) -> tuple[float, str]:
    max_percent = settings.max_bet_percent if max_bet_percent is None else max_bet_percent
    risk_level = classify_risk(edge_percent, confidence_percent)

    if risk_profile == "low":
        ranges = {"low": 0.75, "medium": 0.5, "high": 0.25}
    elif risk_profile == "high":
        ranges = {"low": 1.0, "medium": 0.75, "high": 0.5}
    else:
        ranges = {"low": 0.85, "medium": 0.65, "high": 0.35}

    return round(min(ranges[risk_level], max_percent), 2), risk_level


def calculate_recommended_stake(
    bankroll: float | BankrollSettings,
    edge_percent: float = 0,
    confidence_percent: float = 0,
) -> StakeRecommendation | float:
    if isinstance(bankroll, BankrollSettings):
        stake_percent, risk_level = calculate_recommended_percent(
            edge_percent=edge_percent,
            confidence_percent=confidence_percent,
            risk_profile=bankroll.risk_profile,
            max_bet_percent=bankroll.max_bet_percent,
        )
        return StakeRecommendation(
            stake_percent=stake_percent,
            stake_amount=round(bankroll.bankroll * stake_percent / 100, 2),
            risk_level=risk_level,
        )

    stake_percent, _ = calculate_recommended_percent(edge_percent, confidence_percent)
    return round(bankroll * stake_percent / 100, 2)
