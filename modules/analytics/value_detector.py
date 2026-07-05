def calculate_edge_percent(model_probability: float, decimal_odds: float) -> float:
    implied_probability = 100 / decimal_odds
    return round(model_probability - implied_probability, 2)
