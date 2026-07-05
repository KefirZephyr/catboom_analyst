import re


def extract_decimal_odds(text: str) -> float | None:
    for match in re.findall(r"\b\d+[.,]\d{1,2}\b", text):
        value = float(match.replace(",", "."))
        if 1.01 <= value <= 20:
            return value
    return None
