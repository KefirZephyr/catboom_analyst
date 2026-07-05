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
    "over",
    "under",
    "больше",
    "меньше",
}

EXPLICIT_ODDS_PATTERNS = [
    r"(?:кф|коэф|коэффициент)\s*[:\-]?\s*(\d+(?:[.,]\d{1,2})?)",
    r"odds\s*[:\-]?\s*(\d+(?:[.,]\d{1,2})?)",
    r"@(\d+(?:[.,]\d{1,2})?)",
]

GENERIC_ODDS_PATTERNS = [
    r"\b(\d+[.,]\d{1,2})\b",
]

MAPS_TOTAL_PATTERNS = [
    r"\b(?P<side>over|under)\s*(?P<line>\d+(?:[.,]\d+)?)\s*(?:maps?|карт[а-я]*)?",
    r"\b(?P<side>тб|тм)\s*(?P<line>\d+(?:[.,]\d+)?)\s*(?:карт[а-я]*)?",
    r"\b(?P<side>больше|меньше)\s*(?P<line>\d+(?:[.,]\d+)?)\s*(?:карт[а-я]*)?",
    r"\b(?P<side>tb|tm)\s*(?P<line>\d+(?:[.,]\d+)?)\s*(?:maps?)?",
]


@dataclass(frozen=True)
class ExtractedPrediction:
    raw_text: str
    normalized_text: str
    picked_team_name: str | None
    market_type: str
    market_side: str | None
    market_line: float | None
    odds: float | None
    confidence: float
    needs_review: bool


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower()).replace("ё", "е")


def normalize_market_side(side: str | None) -> str | None:
    if not side:
        return None

    normalized = side.lower()
    if normalized in {"over", "тб", "tb", "больше"}:
        return "over"
    if normalized in {"under", "тм", "tm", "меньше"}:
        return "under"
    return None


def extract_maps_total(text: str) -> tuple[str | None, float | None]:
    normalized = normalize_text(text)
    for pattern in MAPS_TOTAL_PATTERNS:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if not match:
            continue

        side = normalize_market_side(match.group("side"))
        line = float(match.group("line").replace(",", "."))
        if side and 0.5 <= line <= 10:
            return side, line

    return None, None


def extract_decimal_odds(text: str, excluded_values: set[float] | None = None) -> float | None:
    normalized = normalize_text(text)
    excluded_values = excluded_values or set()

    for pattern in EXPLICIT_ODDS_PATTERNS:
        for match in re.findall(pattern, normalized, flags=re.IGNORECASE):
            value = float(match.replace(",", "."))
            if 1.01 <= value <= 20.0:
                return round(value, 2)

    for pattern in GENERIC_ODDS_PATTERNS:
        for match in re.findall(pattern, normalized, flags=re.IGNORECASE):
            value = float(match.replace(",", "."))
            if any(abs(value - excluded) < 0.001 for excluded in excluded_values):
                continue
            if 1.01 <= value <= 20.0:
                return round(value, 2)

    return None


def detect_market_type(normalized_text: str) -> str | None:
    maps_markers = (
        "тотал карт",
        "карты",
        "карт",
        "maps",
        "map total",
        "тб",
        "тм",
        "over",
        "under",
        "больше",
        "меньше",
    )
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
    market_side, market_line = extract_maps_total(normalized)
    market_type = "maps_total" if market_side and market_line is not None else detect_market_type(normalized)

    excluded_odds = {market_line} if market_line is not None else set()
    odds = extract_decimal_odds(normalized, excluded_values=excluded_odds)
    confidence = calculate_confidence(normalized, market_type, odds)

    if not market_type and confidence < MIN_CONFIDENCE:
        return None

    market_type = market_type or "match_winner"
    return ExtractedPrediction(
        raw_text=text.strip(),
        normalized_text=normalized,
        picked_team_name=extract_team_name(text, market_type),
        market_type=market_type,
        market_side=market_side,
        market_line=market_line,
        odds=odds,
        confidence=confidence,
        needs_review=confidence < MIN_CONFIDENCE,
    )
