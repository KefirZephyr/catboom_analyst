from dataclasses import dataclass

from config.settings import settings


@dataclass(frozen=True)
class ValueResult:
    bookmaker_probability_percent: float
    edge_percent: float
    is_value: bool


def calculate_bookmaker_probability(decimal_odds: float) -> float:
    if decimal_odds <= 1:
        return 100.0
    return round((1 / decimal_odds) * 100, 2)


def calculate_edge_percent(model_probability: float, decimal_odds: float) -> float:
    bookmaker_probability = calculate_bookmaker_probability(decimal_odds)
    return round(model_probability - bookmaker_probability, 2)


def detect_value(model_probability_percent: float, decimal_odds: float) -> ValueResult:
    bookmaker_probability = calculate_bookmaker_probability(decimal_odds)
    edge = round(model_probability_percent - bookmaker_probability, 2)
    return ValueResult(
        bookmaker_probability_percent=bookmaker_probability,
        edge_percent=edge,
        is_value=edge >= settings.min_edge_percent,
    )
