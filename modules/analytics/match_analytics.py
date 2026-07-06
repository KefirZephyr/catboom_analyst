from dataclasses import dataclass, field

from sqlalchemy import or_, select

from db.models import DotaMatch, Team
from db.session import async_session


@dataclass(frozen=True)
class TeamForm:
    team_id: int
    matches: int
    wins: int
    winrate: float
    losses: int = 0
    streak_type: str | None = None
    streak_count: int = 0
    avg_maps_won: float | None = None
    recent_results: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class HeadToHeadSummary:
    team_a_id: int
    team_b_id: int
    matches: int
    team_a_wins: int
    team_b_wins: int
    team_a_winrate: float
    team_b_winrate: float
    last_3: tuple[str, ...] = field(default_factory=tuple)
    last_5: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ScheduleStrength:
    team_id: int
    opponents_count: int
    avg_opponent_winrate: float


@dataclass(frozen=True)
class MatchPrediction:
    match_id: int
    team_a_probability: float
    team_b_probability: float
    confidence: float
    confidence_label: str
    predicted_team_id: int | None
    factors: tuple[str, ...]
    explanation: str


def team_won(match: DotaMatch, team_id: int) -> bool:
    return match.winner_team_id == team_id


def result_for_team(match: DotaMatch, team_id: int) -> str | None:
    if match.winner_team_id is None:
        return None
    return "win" if team_won(match, team_id) else "loss"


def maps_won_for_team(match: DotaMatch, team_id: int) -> int | None:
    if match.team_a_score is None or match.team_b_score is None:
        return None
    if match.team_a_id == team_id:
        return match.team_a_score
    if match.team_b_id == team_id:
        return match.team_b_score
    return None


def calculate_streak(results: list[str]) -> tuple[str | None, int]:
    if not results:
        return None, 0
    current = results[0]
    count = 0
    for result in results:
        if result != current:
            break
        count += 1
    return current, count


def calculate_form_from_matches(team_id: int, matches: list[DotaMatch]) -> TeamForm:
    results = [result for match in matches if (result := result_for_team(match, team_id))]
    wins = results.count("win")
    losses = results.count("loss")
    winrate = round((wins / len(results)) * 100, 1) if results else 0.0
    streak_type, streak_count = calculate_streak(results)

    maps_values = [
        value
        for match in matches
        if (value := maps_won_for_team(match, team_id)) is not None
    ]
    avg_maps_won = round(sum(maps_values) / len(maps_values), 2) if maps_values else None

    return TeamForm(
        team_id=team_id,
        matches=len(results),
        wins=wins,
        losses=losses,
        winrate=winrate,
        streak_type=streak_type,
        streak_count=streak_count,
        avg_maps_won=avg_maps_won,
        recent_results=tuple(results),
    )


def calculate_head_to_head_from_matches(
    team_a_id: int,
    team_b_id: int,
    matches: list[DotaMatch],
) -> HeadToHeadSummary:
    results = []
    team_a_wins = 0
    team_b_wins = 0

    for match in matches:
        winner = match.winner_team_id
        if winner == team_a_id:
            team_a_wins += 1
            results.append("A")
        elif winner == team_b_id:
            team_b_wins += 1
            results.append("B")

    total = team_a_wins + team_b_wins
    return HeadToHeadSummary(
        team_a_id=team_a_id,
        team_b_id=team_b_id,
        matches=total,
        team_a_wins=team_a_wins,
        team_b_wins=team_b_wins,
        team_a_winrate=round((team_a_wins / total) * 100, 1) if total else 0.0,
        team_b_winrate=round((team_b_wins / total) * 100, 1) if total else 0.0,
        last_3=tuple(results[:3]),
        last_5=tuple(results[:5]),
    )


def calculate_schedule_strength_from_matches(
    team_id: int,
    matches: list[DotaMatch],
    opponent_forms: dict[int, TeamForm],
) -> ScheduleStrength:
    opponent_rates = []
    for match in matches:
        opponent_id = match.team_b_id if match.team_a_id == team_id else match.team_a_id
        if opponent_id is None:
            continue
        opponent_form = opponent_forms.get(opponent_id)
        if opponent_form and opponent_form.matches >= 3:
            opponent_rates.append(opponent_form.winrate)

    return ScheduleStrength(
        team_id=team_id,
        opponents_count=len(opponent_rates),
        avg_opponent_winrate=round(sum(opponent_rates) / len(opponent_rates), 1) if opponent_rates else 0.0,
    )


def probability_from_score(score_a: float, score_b: float) -> tuple[float, float]:
    diff = max(min(score_a - score_b, 40), -40)
    team_a = 50 + diff * 0.7
    team_a = max(12.0, min(88.0, team_a))
    return round(team_a, 1), round(100 - team_a, 1)


def confidence_label(confidence: float) -> str:
    if confidence >= 70:
        return "высокая"
    if confidence >= 45:
        return "средняя"
    return "низкая"


def _weighted_score(
    form5: TeamForm,
    form10: TeamForm,
    tournament: TeamForm,
    h2h_winrate: float,
    h2h_matches: int,
    schedule: ScheduleStrength,
) -> tuple[float, list[str]]:
    weighted_sum = 0.0
    weight_sum = 0.0
    factors = []

    if form5.matches:
        weighted_sum += form5.winrate * 0.35
        weight_sum += 0.35
        factors.append(f"форма 5 матчей {form5.winrate:.1f}%")
    if form10.matches:
        weighted_sum += form10.winrate * 0.25
        weight_sum += 0.25
        factors.append(f"форма 10 матчей {form10.winrate:.1f}%")
    if tournament.matches:
        weighted_sum += tournament.winrate * 0.2
        weight_sum += 0.2
        factors.append(f"текущий турнир {tournament.winrate:.1f}%")
    if h2h_matches:
        weighted_sum += h2h_winrate * 0.1
        weight_sum += 0.1
        factors.append(f"очные встречи {h2h_winrate:.1f}%")
    if schedule.opponents_count >= 3:
        weighted_sum += schedule.avg_opponent_winrate * 0.1
        weight_sum += 0.1
        factors.append(f"сила последних соперников {schedule.avg_opponent_winrate:.1f}%")

    if weight_sum == 0:
        return 50.0, factors
    return round(weighted_sum / weight_sum, 1), factors


def build_match_prediction(
    match_id: int,
    team_a_id: int,
    team_b_id: int,
    team_a_name: str,
    team_b_name: str,
    form_a_5: TeamForm,
    form_b_5: TeamForm,
    form_a_10: TeamForm,
    form_b_10: TeamForm,
    tournament_a: TeamForm,
    tournament_b: TeamForm,
    head_to_head: HeadToHeadSummary,
    schedule_a: ScheduleStrength,
    schedule_b: ScheduleStrength,
) -> MatchPrediction:
    score_a, factors_a = _weighted_score(
        form_a_5,
        form_a_10,
        tournament_a,
        head_to_head.team_a_winrate,
        head_to_head.matches,
        schedule_a,
    )
    score_b, factors_b = _weighted_score(
        form_b_5,
        form_b_10,
        tournament_b,
        head_to_head.team_b_winrate,
        head_to_head.matches,
        schedule_b,
    )
    probability_a, probability_b = probability_from_score(score_a, score_b)

    data_points = (
        form_a_5.matches
        + form_b_5.matches
        + min(form_a_10.matches + form_b_10.matches, 20)
        + tournament_a.matches
        + tournament_b.matches
        + head_to_head.matches
        + schedule_a.opponents_count
        + schedule_b.opponents_count
    )
    confidence = round(min(85.0, 20.0 + data_points * 2.5), 1)
    predicted_team_id = team_a_id if probability_a >= probability_b else team_b_id
    predicted_name = team_a_name if predicted_team_id == team_a_id else team_b_name

    factors = [
        f"{team_a_name}: {', '.join(factors_a) if factors_a else 'мало данных'}",
        f"{team_b_name}: {', '.join(factors_b) if factors_b else 'мало данных'}",
    ]
    if form_a_5.streak_type:
        factors.append(f"{team_a_name}: серия {format_streak(form_a_5)}")
    if form_b_5.streak_type:
        factors.append(f"{team_b_name}: серия {format_streak(form_b_5)}")
    if head_to_head.matches:
        factors.append(
            f"очные встречи: {team_a_name} {head_to_head.team_a_wins} - "
            f"{head_to_head.team_b_wins} {team_b_name}"
        )
    if schedule_a.opponents_count < 3 or schedule_b.opponents_count < 3:
        factors.append("сила расписания учитывается только при достаточной истории соперников")

    explanation = (
        f"Выбран прогноз: {predicted_name}.\n"
        f"Вероятности: {team_a_name} {probability_a:.1f}%, {team_b_name} {probability_b:.1f}%.\n"
        f"Уверенность: {confidence_label(confidence)} ({confidence:.1f}%).\n"
        + "\n".join(f"• {factor}" for factor in factors)
    )

    return MatchPrediction(
        match_id=match_id,
        team_a_probability=probability_a,
        team_b_probability=probability_b,
        confidence=confidence,
        confidence_label=confidence_label(confidence),
        predicted_team_id=predicted_team_id,
        factors=tuple(factors),
        explanation=explanation,
    )


def format_streak(form: TeamForm) -> str:
    if not form.streak_type or form.streak_count == 0:
        return "нет данных"
    label = "побед" if form.streak_type == "win" else "поражений"
    return f"{form.streak_count} {label}"


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
    return calculate_form_from_matches(team_id, matches)


async def calculate_tournament_form(team_id: int, tournament_id: int | None) -> TeamForm:
    if tournament_id is None:
        return TeamForm(team_id=team_id, matches=0, wins=0, losses=0, winrate=0.0)

    async with async_session() as session:
        result = await session.execute(
            select(DotaMatch)
            .where(
                DotaMatch.status == "finished",
                DotaMatch.tournament_id == tournament_id,
                DotaMatch.winner_team_id.is_not(None),
                or_(DotaMatch.team_a_id == team_id, DotaMatch.team_b_id == team_id),
            )
            .order_by(DotaMatch.starts_at.desc().nullslast(), DotaMatch.id.desc())
        )
        matches = list(result.scalars().all())

    return calculate_form_from_matches(team_id, matches)


async def calculate_head_to_head(team_a_id: int, team_b_id: int, limit: int = 10) -> HeadToHeadSummary:
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

    return calculate_head_to_head_from_matches(team_a_id, team_b_id, matches)


async def strength_of_schedule(team_id: int, limit: int = 10) -> ScheduleStrength:
    recent = await load_finished_matches_for_team(team_id, limit=limit)
    opponent_forms = {}
    for match in recent:
        opponent_id = match.team_b_id if match.team_a_id == team_id else match.team_a_id
        if opponent_id:
            opponent_forms[opponent_id] = await calculate_team_form(opponent_id, limit=10)
    return calculate_schedule_strength_from_matches(team_id, recent, opponent_forms)


async def predict_match_winner(match_id: int) -> MatchPrediction | None:
    async with async_session() as session:
        match = await session.get(DotaMatch, match_id)
        if not match or not match.team_a_id or not match.team_b_id:
            return None
        team_a = await session.get(Team, match.team_a_id)
        team_b = await session.get(Team, match.team_b_id)

    team_a_name = team_a.name if team_a else "Команда A"
    team_b_name = team_b.name if team_b else "Команда B"
    form_a_5 = await calculate_team_form(match.team_a_id, limit=5)
    form_b_5 = await calculate_team_form(match.team_b_id, limit=5)
    form_a_10 = await calculate_team_form(match.team_a_id, limit=10)
    form_b_10 = await calculate_team_form(match.team_b_id, limit=10)
    tournament_a = await calculate_tournament_form(match.team_a_id, match.tournament_id)
    tournament_b = await calculate_tournament_form(match.team_b_id, match.tournament_id)
    h2h = await calculate_head_to_head(match.team_a_id, match.team_b_id)
    schedule_a = await strength_of_schedule(match.team_a_id)
    schedule_b = await strength_of_schedule(match.team_b_id)

    return build_match_prediction(
        match_id=match_id,
        team_a_id=match.team_a_id,
        team_b_id=match.team_b_id,
        team_a_name=team_a_name,
        team_b_name=team_b_name,
        form_a_5=form_a_5,
        form_b_5=form_b_5,
        form_a_10=form_a_10,
        form_b_10=form_b_10,
        tournament_a=tournament_a,
        tournament_b=tournament_b,
        head_to_head=h2h,
        schedule_a=schedule_a,
        schedule_b=schedule_b,
    )
