import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from sqlalchemy import or_, select

from db.models import DotaMatch, Team, TeamAlias, TelegramPrediction
from db.session import async_session

MIN_AUTO_MATCH_CONFIDENCE = 0.6


@dataclass(frozen=True)
class PredictionMatchResult:
    match_id: int | None
    picked_team_id: int | None
    confidence: float
    reason: str


@dataclass(frozen=True)
class MatchCandidate:
    match_id: int
    picked_team_id: int | None
    confidence: float
    reason: str
    title: str


def normalize_match_text(value: str | None) -> str:
    if not value:
        return ""
    value = value.lower().replace("ё", "е")
    value = "".join(
        char for char in value if not unicodedata.category(char).startswith(("S", "P"))
    )
    value = re.sub(r"[^a-zа-я0-9 ]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def fuzzy_ratio(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left in right or right in left:
        return 1.0
    return SequenceMatcher(None, left, right).ratio()


async def match_prediction_to_match(prediction: TelegramPrediction) -> PredictionMatchResult:
    candidates = await find_match_candidates(prediction, limit=1)
    if not candidates:
        return PredictionMatchResult(None, None, 0.0, "Матч-кандидат не найден")

    best = candidates[0]
    return PredictionMatchResult(best.match_id, best.picked_team_id, best.confidence, best.reason)


async def find_match_candidates(
    prediction: TelegramPrediction,
    limit: int = 5,
) -> list[MatchCandidate]:
    prediction_text = normalize_match_text(
        " ".join(
            part
            for part in [
                prediction.raw_text,
                prediction.normalized_text,
                prediction.picked_team_name,
            ]
            if part
        )
    )
    if not prediction_text:
        return []

    now = datetime.utcnow()
    recent_cutoff = now - timedelta(days=3)
    future_cutoff = now + timedelta(days=14)

    async with async_session() as session:
        result = await session.execute(
            select(DotaMatch).where(
                or_(
                    DotaMatch.status.in_(["scheduled", "live"]),
                    DotaMatch.starts_at >= recent_cutoff,
                ),
                or_(DotaMatch.starts_at.is_(None), DotaMatch.starts_at <= future_cutoff),
            )
        )
        matches = result.scalars().all()

        candidates: list[MatchCandidate] = []
        for match in matches:
            team_a = await session.get(Team, match.team_a_id) if match.team_a_id else None
            team_b = await session.get(Team, match.team_b_id) if match.team_b_id else None
            if not team_a and not team_b:
                continue

            team_scores = []
            for team in [team_a, team_b]:
                if not team:
                    continue
                score, alias = await score_team(session, team, prediction_text)
                team_scores.append((score, team, alias))

            if not team_scores:
                continue

            team_scores.sort(key=lambda item: item[0], reverse=True)
            best_score, picked_team, alias = team_scores[0]
            opponent_score = team_scores[1][0] if len(team_scores) > 1 else 0

            confidence = best_score
            if team_a and team_b and opponent_score >= 0.6:
                confidence = min(confidence + 0.1, 1.0)

            if confidence < 0.35:
                continue

            title = format_candidate_title(match, team_a, team_b)
            reason = f"Совпадение команды '{picked_team.name}' по алиасу '{alias}'"
            candidates.append(
                MatchCandidate(
                    match_id=match.id,
                    picked_team_id=picked_team.id,
                    confidence=round(confidence, 2),
                    reason=reason,
                    title=title,
                )
            )

        candidates.sort(key=lambda item: item.confidence, reverse=True)
        return candidates[:limit]


async def score_team(session, team: Team, prediction_text: str) -> tuple[float, str]:
    aliases = {team.name, team.slug, team.acronym}
    result = await session.execute(select(TeamAlias).where(TeamAlias.team_id == team.id))
    aliases.update(alias.alias for alias in result.scalars().all())

    best_score = 0.0
    best_alias = team.name
    for alias in aliases:
        normalized_alias = normalize_match_text(alias)
        score = fuzzy_ratio(normalized_alias, prediction_text)
        if score > best_score:
            best_score = score
            best_alias = alias or team.name
    return best_score, best_alias


def format_candidate_title(match: DotaMatch, team_a: Team | None, team_b: Team | None) -> str:
    team_a_name = team_a.name if team_a else "TBD"
    team_b_name = team_b.name if team_b else "TBD"
    starts_at = match.starts_at.strftime("%d.%m %H:%M") if match.starts_at else "время не указано"
    return f"{team_a_name} vs {team_b_name} · {starts_at}"


async def apply_prediction_match(prediction_id: int, result: PredictionMatchResult) -> bool:
    async with async_session() as session:
        prediction = await session.get(TelegramPrediction, prediction_id)
        if not prediction:
            return False

        prediction.match_id = result.match_id
        prediction.picked_team_id = result.picked_team_id
        prediction.match_confidence = result.confidence
        prediction.match_reason = result.reason
        prediction.needs_review = result.confidence < MIN_AUTO_MATCH_CONFIDENCE
        await session.commit()
        return True


async def auto_match_prediction(prediction_id: int) -> PredictionMatchResult:
    async with async_session() as session:
        prediction = await session.get(TelegramPrediction, prediction_id)
        if not prediction:
            return PredictionMatchResult(None, None, 0.0, "Прогноз не найден")

    result = await match_prediction_to_match(prediction)
    await apply_prediction_match(prediction_id, result)
    return result


async def match_prediction_results() -> None:
    from modules.telegram_parser.result_settlement import settle_predictions

    await settle_predictions()
