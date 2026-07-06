from dataclasses import dataclass

from sqlalchemy import or_, select

from db.models import DotaMatch, Team
from db.session import async_session


@dataclass(frozen=True)
class TeamForm:
    team_id: int
    matches: int
    wins: int
    winrate: float


@dataclass(frozen=True)
class MatchPrediction:
    match_id: int
    team_a_probability: float
    team_b_probability: float
    confidence: float
    predicted_team_id: int | None
    explanation: str


def team_won(match: DotaMatch, team_id: int) -> bool:
    return match.winner_team_id == team_id


async def load_finished_matches_for_team(team_id: int, limit: int = 10) -> list[DotaMatch]:
    async with async_session() as session:
        result = await session.execute(
            select(DotaMatch)
            .where(
                DotaMatch.status == "finished",
                DotaMatch.winner_team_id.is_not(None),
                or_(DotaMatch.team_a_id == team_id, DotaMatch.team_b_id == team_id),
            )
            .order_by(DotaMatch.starts_at.desc().nullslast(), DotaMatch.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


async def calculate_team_form(team_id: int, limit: int = 10) -> TeamForm:
    matches = await load_finished_matches_for_team(team_id, limit=limit)
    wins = sum(1 for match in matches if team_won(match, team_id))
    winrate = round((wins / len(matches)) * 100, 1) if matches else 0.0
    return TeamForm(team_id=team_id, matches=len(matches), wins=wins, winrate=winrate)


async def calculate_tournament_form(team_id: int, tournament_id: int | None) -> TeamForm:
    if tournament_id is None:
        return TeamForm(team_id=team_id, matches=0, wins=0, winrate=0.0)

    async with async_session() as session:
        result = await session.execute(
            select(DotaMatch).where(
                DotaMatch.status == "finished",
                DotaMatch.tournament_id == tournament_id,
                DotaMatch.winner_team_id.is_not(None),
                or_(DotaMatch.team_a_id == team_id, DotaMatch.team_b_id == team_id),
            )
        )
        matches = list(result.scalars().all())

    wins = sum(1 for match in matches if team_won(match, team_id))
    winrate = round((wins / len(matches)) * 100, 1) if matches else 0.0
    return TeamForm(team_id=team_id, matches=len(matches), wins=wins, winrate=winrate)


async def calculate_head_to_head(team_a_id: int, team_b_id: int, limit: int = 10) -> tuple[TeamForm, TeamForm]:
    async with async_session() as session:
        result = await session.execute(
            select(DotaMatch)
            .where(
                DotaMatch.status == "finished",
                DotaMatch.winner_team_id.is_not(None),
                or_(
                    (DotaMatch.team_a_id == team_a_id) & (DotaMatch.team_b_id == team_b_id),
                    (DotaMatch.team_a_id == team_b_id) & (DotaMatch.team_b_id == team_a_id),
                ),
            )
            .order_by(DotaMatch.starts_at.desc().nullslast(), DotaMatch.id.desc())
            .limit(limit)
        )
        matches = list(result.scalars().all())

    a_wins = sum(1 for match in matches if team_won(match, team_a_id))
    b_wins = sum(1 for match in matches if team_won(match, team_b_id))
    total = len(matches)
    return (
        TeamForm(team_a_id, total, a_wins, round((a_wins / total) * 100, 1) if total else 0.0),
        TeamForm(team_b_id, total, b_wins, round((b_wins / total) * 100, 1) if total else 0.0),
    )


async def strength_of_schedule(team_id: int, limit: int = 10) -> float:
    recent = await load_finished_matches_for_team(team_id, limit=limit)
    opponent_rates = []
    for match in recent:
        opponent_id = match.team_b_id if match.team_a_id == team_id else match.team_a_id
        if opponent_id:
            form = await calculate_team_form(opponent_id, limit=10)
            if form.matches:
                opponent_rates.append(form.winrate)
    return round(sum(opponent_rates) / len(opponent_rates), 1) if opponent_rates else 0.0


def probability_from_score(score_a: float, score_b: float) -> tuple[float, float]:
    diff = max(min(score_a - score_b, 35), -35)
    team_a = 50 + diff * 0.75
    team_a = max(15.0, min(85.0, team_a))
    return round(team_a, 1), round(100 - team_a, 1)


async def predict_match_winner(match_id: int) -> MatchPrediction | None:
    async with async_session() as session:
        match = await session.get(DotaMatch, match_id)
        if not match or not match.team_a_id or not match.team_b_id:
            return None
        team_a = await session.get(Team, match.team_a_id)
        team_b = await session.get(Team, match.team_b_id)

    form_a_5 = await calculate_team_form(match.team_a_id, limit=5)
    form_b_5 = await calculate_team_form(match.team_b_id, limit=5)
    form_a_10 = await calculate_team_form(match.team_a_id, limit=10)
    form_b_10 = await calculate_team_form(match.team_b_id, limit=10)
    tournament_a = await calculate_tournament_form(match.team_a_id, match.tournament_id)
    tournament_b = await calculate_tournament_form(match.team_b_id, match.tournament_id)
    h2h_a, h2h_b = await calculate_head_to_head(match.team_a_id, match.team_b_id)
    schedule_a = await strength_of_schedule(match.team_a_id)
    schedule_b = await strength_of_schedule(match.team_b_id)

    score_a = (
        form_a_5.winrate * 0.35
        + form_a_10.winrate * 0.25
        + tournament_a.winrate * 0.2
        + h2h_a.winrate * 0.1
        + schedule_a * 0.1
    )
    score_b = (
        form_b_5.winrate * 0.35
        + form_b_10.winrate * 0.25
        + tournament_b.winrate * 0.2
        + h2h_b.winrate * 0.1
        + schedule_b * 0.1
    )
    probability_a, probability_b = probability_from_score(score_a, score_b)

    samples = (
        form_a_5.matches
        + form_b_5.matches
        + tournament_a.matches
        + tournament_b.matches
        + h2h_a.matches
    )
    confidence = round(min(85.0, 35.0 + samples * 3.0), 1)
    predicted_team_id = match.team_a_id if probability_a >= probability_b else match.team_b_id
    team_a_name = team_a.name if team_a else "Команда A"
    team_b_name = team_b.name if team_b else "Команда B"
    explanation = (
        f"{team_a_name}: форма 5 матчей {form_a_5.winrate:.1f}%, "
        f"10 матчей {form_a_10.winrate:.1f}%, турнир {tournament_a.winrate:.1f}%, "
        f"сила расписания {schedule_a:.1f}%.\n"
        f"{team_b_name}: форма 5 матчей {form_b_5.winrate:.1f}%, "
        f"10 матчей {form_b_10.winrate:.1f}%, турнир {tournament_b.winrate:.1f}%, "
        f"сила расписания {schedule_b:.1f}%.\n"
        f"Очные встречи: {team_a_name} {h2h_a.wins} - {h2h_b.wins} {team_b_name} "
        f"за последние {h2h_a.matches} матчей."
    )
    return MatchPrediction(
        match_id=match_id,
        team_a_probability=probability_a,
        team_b_probability=probability_b,
        confidence=confidence,
        predicted_team_id=predicted_team_id,
        explanation=explanation,
    )
