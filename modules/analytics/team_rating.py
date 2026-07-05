def calculate_team_rating(base_rating: float, recent_form: float) -> float:
    return round((base_rating * 0.7) + (recent_form * 0.3), 2)
