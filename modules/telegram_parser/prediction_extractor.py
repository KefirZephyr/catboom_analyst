import re
from dataclasses import dataclass

MIN_CONFIDENCE = 0.6

DOTA_KEYWORDS = {
    "dota",
    "дота",
    "dota2",
    "дота2",
    "bo1",
    "bo2",
    "bo3",
    "bo5",
    "карта",
    "карты",
    "мап",
    "матч",
}

PREDICTION_KEYWORDS = {
    "прогноз",
    "ставка",
    "беру",
    "победа",
    "тотал",
    "тб",
    "тм",
    "winner",
    "win",
    "maps",
    "total",
}

ODDS_PATTERNS = [
    r"(?:кф|коэф|коэффициент)\s*[:\-]?\s*(\d+(?:[.,]\d{1,2})?)",
    r"odds\s*[:\-]?\s*(\d+(?:[.,]\d{1,2})?)",
    r"@(\d+(?:[.,]\d{1,2})?)",
    r"\b(\d+[.,]\d{1,2})\b",
]


@dataclass(frozen=True)
class ExtractedPrediction:
    raw_text: str
    normalized_text: str
    picked_team_name: str | None
    market_type: str
    odds: float | None
    confidence: float
    needs_review: bool


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def extract_decimal_odds(text: str) -> float | None:
    normalized = normalize_text(text)
    for pattern in ODDS_PATTERNS:
        for match in re.findall(pattern, normalized, flags=re.IGNORECASE):
            value = float(match.replace(",", "."))
            if 1.01 <= value <= 20.0:
                return round(value, 2)
    return None


def detect_market_type(normalized_text: str) -> str | None:
    maps_markers = ("тотал карт", "карты", "карт", "maps", "map total", "тб", "тм")
    winner_markers = ("победа", "п1", "п2", "winner", "win", "победит")

    if any(marker in normalized_text for marker in maps_markers):
        return "maps_total"
    if any(marker in normalized_text for marker in winner_markers):
        return "match_winner"
    return None


def extract_team_name(text: str, market_type: str | None) -> str | None:
    if market_type != "match_winner":
        return None

    patterns = [
        r"(?:победа|беру|win|winner)\s+([A-Za-zА-Яа-я0-9_.\- ]{2,40})",
        r"([A-Za-zА-Яа-я0-9_.\- ]{2,40})\s+(?:победит|win)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            team = re.sub(r"[@#:/|]+", " ", match.group(1)).strip(" .,-")
            return team[:80] or None
    return None


def calculate_confidence(normalized_text: str, market_type: str | None, odds: float | None) -> float:
    confidence = 0.0

    if any(keyword in normalized_text for keyword in DOTA_KEYWORDS):
        confidence += 0.25
    if any(keyword in normalized_text for keyword in PREDICTION_KEYWORDS):
        confidence += 0.25
    if market_type:
        confidence += 0.25
    if odds:
        confidence += 0.2
    if len(normalized_text) >= 30:
        confidence += 0.05

    return round(min(confidence, 1.0), 2)


def extract_prediction(text: str) -> ExtractedPrediction | None:
    if not text or len(text.strip()) < 10:
        return None

    normalized = normalize_text(text)
    market_type = detect_market_type(normalized)
    odds = extract_decimal_odds(normalized)
    confidence = calculate_confidence(normalized, market_type, odds)

    if not market_type and confidence < MIN_CONFIDENCE:
        return None

    market_type = market_type or "match_winner"
    return ExtractedPrediction(
        raw_text=text.strip(),
        normalized_text=normalized,
        picked_team_name=extract_team_name(text, market_type),
        market_type=market_type,
        odds=odds,
        confidence=confidence,
        needs_review=confidence < MIN_CONFIDENCE,
    )
