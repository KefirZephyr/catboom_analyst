def estimate_match_probability(team_a_rating: float, team_b_rating: float) -> float:
    total = team_a_rating + team_b_rating
    if total <= 0:
        return 50.0
    return round((team_a_rating / total) * 100, 2)
