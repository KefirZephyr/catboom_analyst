from config.settings import settings


def calculate_recommended_stake(bankroll: float) -> float:
    return round(bankroll * settings.max_bet_percent / 100, 2)
