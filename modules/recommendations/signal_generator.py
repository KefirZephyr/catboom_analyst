from modules.analytics.risk_engine import is_signal_allowed
from modules.bankroll.stake_sizer import calculate_recommended_stake


def build_signal(edge_percent: float, confidence_percent: float, bankroll: float) -> dict | None:
    if not is_signal_allowed(edge_percent, confidence_percent):
        return None
    return {
        "edge_percent": edge_percent,
        "confidence_percent": confidence_percent,
        "recommended_stake": calculate_recommended_stake(bankroll),
    }
