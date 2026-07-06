from datetime import UTC, datetime, timedelta

from db.models import DotaMatch
from modules.analytics.match_analytics import (
    ScheduleStrength,
    TeamForm,
    build_match_prediction,
    calculate_form_from_matches,
    calculate_head_to_head_from_matches,
)


def make_match(
    match_id: int,
    team_a_id: int,
    team_b_id: int,
    winner_team_id: int,
    team_a_score: int = 2,
    team_b_score: int = 1,
) -> DotaMatch:
    return DotaMatch(
        id=match_id,
        team_a_id=team_a_id,
        team_b_id=team_b_id,
        winner_team_id=winner_team_id,
        status="finished",
        team_a_score=team_a_score,
        team_b_score=team_b_score,
        starts_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=match_id),
    )


def empty_form(team_id: int) -> TeamForm:
    return TeamForm(team_id=team_id, matches=0, wins=0, losses=0, winrate=0.0)


def test_calculate_winrate_and_average_maps() -> None:
    matches = [
        make_match(1, 1, 2, 1, 2, 0),
        make_match(2, 1, 3, 1, 2, 1),
        make_match(3, 4, 1, 4, 2, 1),
        make_match(4, 1, 5, 1, 2, 0),
    ]

    form = calculate_form_from_matches(1, matches)

    assert form.matches == 4
    assert form.wins == 3
    assert form.losses == 1
    assert form.winrate == 75.0
    assert form.avg_maps_won == 1.75


def test_calculate_streak_from_latest_results() -> None:
    matches = [
        make_match(1, 1, 2, 1),
        make_match(2, 1, 3, 1),
        make_match(3, 1, 4, 4),
        make_match(4, 1, 5, 1),
    ]

    form = calculate_form_from_matches(1, matches)

    assert form.streak_type == "win"
    assert form.streak_count == 2


def test_calculate_head_to_head_summary() -> None:
    matches = [
        make_match(1, 1, 2, 1),
        make_match(2, 2, 1, 2),
        make_match(3, 1, 2, 1),
        make_match(4, 2, 1, 1),
        make_match(5, 1, 2, 2),
    ]

    summary = calculate_head_to_head_from_matches(1, 2, matches)

    assert summary.matches == 5
    assert summary.team_a_wins == 3
    assert summary.team_b_wins == 2
    assert summary.team_a_winrate == 60.0
    assert summary.last_3 == ("A", "B", "A")
    assert summary.last_5 == ("A", "B", "A", "A", "B")


def test_prediction_prefers_team_with_better_form() -> None:
    strong = TeamForm(team_id=1, matches=5, wins=5, losses=0, winrate=100.0, streak_type="win", streak_count=5)
    weak = TeamForm(team_id=2, matches=5, wins=1, losses=4, winrate=20.0, streak_type="loss", streak_count=3)
    h2h = calculate_head_to_head_from_matches(
        1,
        2,
        [
            make_match(1, 1, 2, 1),
            make_match(2, 2, 1, 1),
            make_match(3, 1, 2, 2),
        ],
    )

    prediction = build_match_prediction(
        match_id=100,
        team_a_id=1,
        team_b_id=2,
        team_a_name="Team A",
        team_b_name="Team B",
        form_a_5=strong,
        form_b_5=weak,
        form_a_10=strong,
        form_b_10=weak,
        tournament_a=strong,
        tournament_b=weak,
        head_to_head=h2h,
        schedule_a=ScheduleStrength(team_id=1, opponents_count=3, avg_opponent_winrate=65.0),
        schedule_b=ScheduleStrength(team_id=2, opponents_count=3, avg_opponent_winrate=35.0),
    )

    assert prediction.predicted_team_id == 1
    assert prediction.team_a_probability > prediction.team_b_probability
    assert prediction.confidence_label in {"средняя", "высокая"}


def test_prediction_low_confidence_when_data_is_missing() -> None:
    h2h = calculate_head_to_head_from_matches(1, 2, [])

    prediction = build_match_prediction(
        match_id=100,
        team_a_id=1,
        team_b_id=2,
        team_a_name="Team A",
        team_b_name="Team B",
        form_a_5=empty_form(1),
        form_b_5=empty_form(2),
        form_a_10=empty_form(1),
        form_b_10=empty_form(2),
        tournament_a=empty_form(1),
        tournament_b=empty_form(2),
        head_to_head=h2h,
        schedule_a=ScheduleStrength(team_id=1, opponents_count=0, avg_opponent_winrate=0.0),
        schedule_b=ScheduleStrength(team_id=2, opponents_count=0, avg_opponent_winrate=0.0),
    )

    assert prediction.team_a_probability == 50.0
    assert prediction.team_b_probability == 50.0
    assert prediction.confidence_label == "низкая"
