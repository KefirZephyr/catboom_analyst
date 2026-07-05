from types import SimpleNamespace

from modules.telegram_parser.result_settlement import (
    is_prediction_eligible,
    settle_prediction_result,
)


def prediction(**kwargs):
    values = {
        "status": "pending",
        "match_id": 10,
        "picked_team_id": 1,
        "market_type": "match_winner",
        "market_side": None,
        "market_line": None,
    }
    values.update(kwargs)
    return SimpleNamespace(**values)


def match(**kwargs):
    values = {
        "status": "finished",
        "winner_team_id": 1,
        "team_a_score": 2,
        "team_b_score": 1,
    }
    values.update(kwargs)
    return SimpleNamespace(**values)


def test_finished_picked_winner_settles_win():
    assert settle_prediction_result(prediction(picked_team_id=1), match(winner_team_id=1)) == "win"


def test_finished_picked_loser_settles_loss():
    assert settle_prediction_result(prediction(picked_team_id=2), match(winner_team_id=1)) == "loss"


def test_canceled_match_settles_void():
    assert settle_prediction_result(prediction(), match(status="canceled", winner_team_id=None)) == "void"


def test_not_played_match_settles_void():
    assert settle_prediction_result(prediction(), match(status="not_played", winner_team_id=None)) == "void"


def test_scheduled_and_live_matches_stay_pending():
    assert settle_prediction_result(prediction(), match(status="scheduled", winner_team_id=None)) is None
    assert settle_prediction_result(prediction(), match(status="live", winner_team_id=None)) is None


def test_prediction_without_match_id_is_not_eligible():
    assert is_prediction_eligible(prediction(match_id=None)) is False


def test_maps_total_over_win_loss_void():
    over = prediction(market_type="maps_total", picked_team_id=None, market_side="over", market_line=2.5)

    assert settle_prediction_result(over, match(team_a_score=2, team_b_score=1)) == "win"
    assert settle_prediction_result(over, match(team_a_score=2, team_b_score=0)) == "loss"


def test_maps_total_under_win_loss_void():
    under = prediction(market_type="maps_total", picked_team_id=None, market_side="under", market_line=2.5)

    assert settle_prediction_result(under, match(team_a_score=2, team_b_score=0)) == "win"
    assert settle_prediction_result(under, match(team_a_score=2, team_b_score=1)) == "loss"


def test_maps_total_integer_line_push_is_void():
    over = prediction(market_type="maps_total", picked_team_id=None, market_side="over", market_line=2.0)
    under = prediction(market_type="maps_total", picked_team_id=None, market_side="under", market_line=2.0)
    two_maps = match(team_a_score=2, team_b_score=0)

    assert settle_prediction_result(over, two_maps) == "void"
    assert settle_prediction_result(under, two_maps) == "void"
