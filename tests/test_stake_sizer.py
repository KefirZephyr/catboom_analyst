from modules.bankroll.stake_sizer import calculate_recommended_percent


def test_normal_profile_caps_low_risk_stake():
    percent, risk = calculate_recommended_percent(
        edge_percent=10,
        confidence_percent=80,
        risk_profile="normal",
        max_bet_percent=1,
    )

    assert risk == "low"
    assert 0.75 <= percent <= 1.0


def test_normal_profile_reduces_high_risk_stake():
    percent, risk = calculate_recommended_percent(
        edge_percent=3,
        confidence_percent=60,
        risk_profile="normal",
        max_bet_percent=1,
    )

    assert risk == "high"
    assert 0.25 <= percent <= 0.5
