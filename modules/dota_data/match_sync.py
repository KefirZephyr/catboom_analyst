from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from db.models import DotaMatch, Player, Team, TeamAlias, Tournament
from db.session import async_session
from modules.dota_data.providers.pandascore import (
    PandaScoreError,
    PandaScoreProvider,
    PandaScoreTokenMissing,
)


@dataclass(frozen=True)
class MatchSyncResult:
    upcoming: int = 0
    live: int = 0
    past: int = 0
    teams: int = 0
    tournaments: int = 0
    matches: int = 0
    players: int = 0
    error: str | None = None


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def external_id(value: Any) -> str | None:
    return str(value) if value is not None else None


async def sync_matches() -> MatchSyncResult:
    provider = PandaScoreProvider()
    if not provider.is_configured:
        return MatchSyncResult(error="PANDASCORE_TOKEN не задан. Добавьте токен в .env.")

    try:
        upcoming = await provider.get_upcoming_matches()
        live = await provider.get_live_matches()
        past = await provider.get_past_matches()
    except PandaScoreTokenMissing as exc:
        return MatchSyncResult(error=str(exc))
    except PandaScoreError as exc:
        return MatchSyncResult(error=str(exc))

    counters = {"teams": 0, "tournaments": 0, "matches": 0, "players": 0}
    async with async_session() as session:
        for status_group, payload in (
            ("upcoming", upcoming),
            ("live", live),
            ("past", past),
        ):
            for item in payload:
                await upsert_match(session, item, status_group, counters)

        await session.commit()

    return MatchSyncResult(
        upcoming=len(upcoming),
        live=len(live),
        past=len(past),
        teams=counters["teams"],
        tournaments=counters["tournaments"],
        matches=counters["matches"],
        players=counters["players"],
    )


async def upsert_team(session, team_data: dict[str, Any] | None, counters: dict[str, int]) -> Team | None:
    if not team_data:
        return None

    team_external_id = external_id(team_data.get("id"))
    if not team_external_id:
        return None

    result = await session.execute(select(Team).where(Team.external_id == team_external_id))
    team = result.scalar_one_or_none()
    if not team:
        team = Team(external_id=team_external_id, name=team_data.get("name") or "Unknown")
        session.add(team)
        counters["teams"] += 1

    team.name = team_data.get("name") or team.name
    team.slug = team_data.get("slug") or team.slug
    team.acronym = team_data.get("acronym") or team.acronym
    team.image_url = team_data.get("image_url") or team.image_url
    team.updated_at = datetime.utcnow()
    await upsert_team_aliases(session, team, [team.name, team.slug, team.acronym])
    await upsert_team_players(session, team, team_data, counters)
    return team


def extract_player_items(team_data: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not team_data:
        return []

    candidates = []
    for key in ("players", "current_videogame_roster", "current_roster"):
        value = team_data.get(key)
        if isinstance(value, list):
            candidates.extend(item for item in value if isinstance(item, dict))

    roster = team_data.get("roster")
    if isinstance(roster, dict):
        players = roster.get("players")
        if isinstance(players, list):
            candidates.extend(item for item in players if isinstance(item, dict))

    return candidates


async def upsert_team_players(
    session,
    team: Team,
    team_data: dict[str, Any] | None,
    counters: dict[str, int],
) -> None:
    await session.flush()
    for raw_player in extract_player_items(team_data):
        player_data = raw_player.get("player") if isinstance(raw_player.get("player"), dict) else raw_player
        player_external_id = external_id(player_data.get("id"))
        nickname = (
            player_data.get("name")
            or player_data.get("nickname")
            or player_data.get("first_name")
            or "Unknown"
        )
        if not player_external_id and nickname == "Unknown":
            continue

        result = await session.execute(select(Player).where(Player.external_id == player_external_id))
        player = result.scalar_one_or_none() if player_external_id else None
        if not player:
            player = Player(external_id=player_external_id, nickname=nickname)
            session.add(player)
            counters["players"] += 1

        player.team_id = team.id
        player.nickname = nickname
        player.first_name = player_data.get("first_name") or player.first_name
        player.last_name = player_data.get("last_name") or player.last_name
        player.slug = player_data.get("slug") or player.slug
        player.role = raw_player.get("role") or player_data.get("role") or player.role
        player.nationality = player_data.get("nationality") or player.nationality
        player.image_url = player_data.get("image_url") or player.image_url
        player.is_active = True
        player.updated_at = datetime.utcnow()


async def upsert_team_aliases(session, team: Team, aliases: list[str | None]) -> None:
    await session.flush()
    for alias in aliases:
        if not alias:
            continue
        normalized_alias = alias.strip()
        if not normalized_alias:
            continue

        result = await session.execute(
            select(TeamAlias).where(
                TeamAlias.team_id == team.id,
                TeamAlias.alias == normalized_alias,
            )
        )
        if not result.scalar_one_or_none():
            session.add(TeamAlias(team_id=team.id, alias=normalized_alias))


async def upsert_tournament(
    session,
    match_data: dict[str, Any],
    counters: dict[str, int],
) -> Tournament | None:
    tournament_data = match_data.get("tournament") or {}
    serie_data = match_data.get("serie") or {}
    league_data = match_data.get("league") or {}

    tournament_external_id = external_id(tournament_data.get("id") or serie_data.get("id"))
    if not tournament_external_id:
        return None

    result = await session.execute(
        select(Tournament).where(Tournament.external_id == tournament_external_id)
    )
    tournament = result.scalar_one_or_none()
    if not tournament:
        tournament = Tournament(
            external_id=tournament_external_id,
            name=tournament_data.get("name") or serie_data.get("full_name") or "Unknown",
        )
        session.add(tournament)
        counters["tournaments"] += 1

    tournament.name = tournament_data.get("name") or serie_data.get("full_name") or tournament.name
    tournament.league_name = league_data.get("name") or tournament.league_name
    tournament.serie_name = serie_data.get("full_name") or serie_data.get("name") or tournament.serie_name
    tournament.tier = tournament_data.get("tier") or tournament.tier
    tournament.updated_at = datetime.utcnow()
    return tournament


async def upsert_match(
    session,
    match_data: dict[str, Any],
    status_group: str,
    counters: dict[str, int],
) -> DotaMatch | None:
    match_external_id = external_id(match_data.get("id"))
    if not match_external_id:
        return None

    opponents = match_data.get("opponents") or []
    opponent_a = opponents[0] if len(opponents) > 0 else {}
    opponent_b = opponents[1] if len(opponents) > 1 else {}
    team_a_payload = opponent_a.get("opponent") if isinstance(opponent_a, dict) else None
    team_b_payload = opponent_b.get("opponent") if isinstance(opponent_b, dict) else None

    team_a = await upsert_team(
        session,
        team_a_payload,
        counters,
    )
    team_b = await upsert_team(
        session,
        team_b_payload,
        counters,
    )
    tournament = await upsert_tournament(session, match_data, counters)
    await session.flush()

    result = await session.execute(select(DotaMatch).where(DotaMatch.external_id == match_external_id))
    match = result.scalar_one_or_none()
    if not match:
        match = DotaMatch(external_id=match_external_id)
        session.add(match)
        counters["matches"] += 1

    results = match_data.get("results") or []
    scores = {external_id(item.get("team_id")): item.get("score") for item in results}

    match.tournament_id = tournament.id if tournament and tournament.id else match.tournament_id
    match.team_a_id = team_a.id if team_a and team_a.id else match.team_a_id
    match.team_b_id = team_b.id if team_b and team_b.id else match.team_b_id
    match.best_of = match_data.get("number_of_games") or match.best_of
    match.starts_at = parse_datetime(match_data.get("begin_at") or match_data.get("scheduled_at"))
    match.ends_at = parse_datetime(match_data.get("end_at"))
    match.status = normalize_status(match_data.get("status"), status_group)
    match.team_a_score = scores.get(team_a.external_id) if team_a else None
    match.team_b_score = scores.get(team_b.external_id) if team_b else None
    match.raw_name = match_data.get("name") or match.raw_name
    match.winner_team_id = resolve_winner_id(match_data, team_a, team_b)
    match.updated_at = datetime.utcnow()
    return match


def normalize_status(api_status: str | None, status_group: str) -> str:
    if status_group == "live":
        return "live"
    if api_status in {"finished", "canceled", "not_played"}:
        return api_status
    if status_group == "past":
        return "finished"
    return "scheduled"


def resolve_winner_id(match_data: dict[str, Any], team_a: Team | None, team_b: Team | None) -> int | None:
    winner_id = external_id(match_data.get("winner_id"))
    if not winner_id:
        return None
    if team_a and team_a.external_id == winner_id:
        return team_a.id
    if team_b and team_b.external_id == winner_id:
        return team_b.id
    return None
