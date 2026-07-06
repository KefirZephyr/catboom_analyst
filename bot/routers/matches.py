from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from config.settings import settings
from db.models import DotaMatch, Team, Tournament
from db.session import async_session

router = Router()


def matches_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📡 Live", callback_data="matches_live")],
            [InlineKeyboardButton(text="🗓 Сегодня", callback_data="matches_today")],
            [InlineKeyboardButton(text="🌅 Завтра", callback_data="matches_tomorrow")],
            [InlineKeyboardButton(text="🔜 Предстоящие", callback_data="matches_upcoming")],
            [InlineKeyboardButton(text="✅ Завершённые", callback_data="matches_finished")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
        ]
    )


@router.callback_query(F.data == "matches")
async def matches_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "📅 <b>Матчи Dota 2</b>\n\n"
        "Live, ближайшие и завершённые матчи из локальной базы. "
        "Обновить данные можно отдельной кнопкой в главном меню.",
        reply_markup=matches_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.in_({"matches_live", "matches_today", "matches_tomorrow", "matches_upcoming", "matches_finished"}))
async def matches_list(callback: CallbackQuery) -> None:
    kind = callback.data.removeprefix("matches_")
    titles = {
        "live": "📡 Live-матчи",
        "today": "🗓 Матчи сегодня",
        "tomorrow": "🌅 Матчи завтра",
        "upcoming": "🔜 Предстоящие матчи",
        "finished": "✅ Завершённые матчи",
    }
    matches = await load_matches(kind)
    await callback.message.edit_text(format_matches(titles[kind], matches), reply_markup=matches_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("match_view:"))
async def match_view(callback: CallbackQuery) -> None:
    match_id = int(callback.data.split(":", 1)[1])
    row = await load_match_row(match_id)
    if not row:
        await callback.answer("Матч не найден", show_alert=True)
        return
    await callback.message.edit_text(format_match_card(*row), reply_markup=matches_keyboard())
    await callback.answer()


async def load_matches(kind: str, limit: int = 12) -> list[tuple[DotaMatch, Team | None, Team | None, Tournament | None]]:
    now = datetime.utcnow()
    query = select(DotaMatch).order_by(DotaMatch.starts_at.is_(None), DotaMatch.starts_at).limit(limit)

    if kind == "live":
        query = query.where(DotaMatch.status == "live")
    elif kind in {"today", "tomorrow"}:
        moscow = ZoneInfo(settings.app_timezone)
        start_local = datetime.now(moscow).replace(hour=0, minute=0, second=0, microsecond=0)
        if kind == "tomorrow":
            start_local += timedelta(days=1)
        end_local = start_local + timedelta(days=1)
        start_utc = start_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        end_utc = end_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        query = query.where(DotaMatch.starts_at >= start_utc, DotaMatch.starts_at < end_utc)
    elif kind == "upcoming":
        query = query.where(DotaMatch.starts_at >= now, DotaMatch.status != "finished")
    elif kind == "finished":
        query = (
            select(DotaMatch)
            .where(DotaMatch.status == "finished")
            .order_by(DotaMatch.starts_at.desc().nullslast(), DotaMatch.id.desc())
            .limit(limit)
        )

    async with async_session() as session:
        result = await session.execute(query)
        matches = result.scalars().all()
        rows = []
        for match in matches:
            rows.append(await hydrate_match(session, match))
        return rows


async def load_match_row(match_id: int):
    async with async_session() as session:
        match = await session.get(DotaMatch, match_id)
        if not match:
            return None
        return await hydrate_match(session, match)


async def hydrate_match(session, match: DotaMatch):
    team_a = await session.get(Team, match.team_a_id) if match.team_a_id else None
    team_b = await session.get(Team, match.team_b_id) if match.team_b_id else None
    tournament = await session.get(Tournament, match.tournament_id) if match.tournament_id else None
    return match, team_a, team_b, tournament


def format_matches(
    title: str,
    matches: list[tuple[DotaMatch, Team | None, Team | None, Tournament | None]],
) -> str:
    if not matches:
        return f"{title}\n\nПока нет данных. Запустите обновление данных из главного меню."

    lines = [f"<b>{title}</b>\n"]
    for match, team_a, team_b, tournament in matches:
        lines.append(format_match_card(match, team_a, team_b, tournament))
    return "\n\n".join(lines)


def format_match_card(
    match: DotaMatch,
    team_a: Team | None,
    team_b: Team | None,
    tournament: Tournament | None,
) -> str:
    team_a_name = team_a.name if team_a else "TBD"
    team_b_name = team_b.name if team_b else "TBD"
    tournament_name = tournament.name if tournament else "Турнир не указан"
    best_of = f"BO{match.best_of}" if match.best_of else "BO?"
    winner = format_winner(match, team_a, team_b)

    return (
        f"🎮 <b>{team_a_name} vs {team_b_name}</b>\n"
        f"🏆 Турнир: {tournament_name}\n"
        f"🎯 Формат: {best_of}\n"
        f"🕒 Время: {format_moscow_time(match.starts_at)}\n"
        f"📌 Статус: {translate_status(match.status)}\n"
        f"📊 Счёт: {format_score(match)}\n"
        f"👑 Победитель: {winner}"
    )


def format_moscow_time(value: datetime | None) -> str:
    if not value:
        return "не указано"
    utc_value = value.replace(tzinfo=ZoneInfo("UTC"))
    local = utc_value.astimezone(ZoneInfo(settings.app_timezone))
    return local.strftime("%d.%m.%Y %H:%M")


def format_score(match: DotaMatch) -> str:
    if match.team_a_score is None and match.team_b_score is None:
        return "нет данных"
    return f"{match.team_a_score or 0}:{match.team_b_score or 0}"


def format_winner(match: DotaMatch, team_a: Team | None, team_b: Team | None) -> str:
    if not match.winner_team_id:
        return "не определён"
    if team_a and match.winner_team_id == team_a.id:
        return team_a.name
    if team_b and match.winner_team_id == team_b.id:
        return team_b.name
    return "не указан в базе"


def translate_status(status: str) -> str:
    return {
        "scheduled": "запланирован",
        "live": "live",
        "finished": "завершён",
        "canceled": "отменён",
        "not_played": "не сыгран",
    }.get(status, status)
