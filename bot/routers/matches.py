from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from bot.keyboards import main_menu_keyboard
from config.settings import settings
from db.models import DotaMatch, Team, Tournament
from db.session import async_session
from modules.dota_data.match_sync import sync_matches

router = Router()


def matches_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📡 Live", callback_data="matches_live")],
            [InlineKeyboardButton(text="🗓 Сегодня", callback_data="matches_today")],
            [InlineKeyboardButton(text="🔜 Ближайшие", callback_data="matches_upcoming")],
            [InlineKeyboardButton(text="🏆 Турниры", callback_data="matches_tournaments")],
            [InlineKeyboardButton(text="🔄 Синхронизировать", callback_data="matches_sync")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
        ]
    )


@router.callback_query(F.data == "matches")
async def matches_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "📡 <b>Матчи Dota 2</b>\n\nДанные берутся из PandaScore и сохраняются локально в SQLite.",
        reply_markup=matches_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "matches_sync")
async def matches_sync_callback(callback: CallbackQuery) -> None:
    if settings.admin_ids and callback.from_user.id not in settings.admin_ids:
        await callback.answer("Синхронизация доступна только администратору", show_alert=True)
        return

    await callback.message.edit_text("🔄 Синхронизирую матчи через PandaScore...", reply_markup=matches_keyboard())
    result = await sync_matches()

    if result.error:
        text = f"⚠️ <b>Синхронизация не выполнена</b>\n\n{result.error}"
    else:
        text = (
            "✅ <b>Синхронизация завершена</b>\n\n"
            f"Upcoming: {result.upcoming}\n"
            f"Live: {result.live}\n"
            f"Past: {result.past}\n"
            f"Новых команд: {result.teams}\n"
            f"Новых турниров: {result.tournaments}\n"
            f"Новых матчей: {result.matches}"
        )

    await callback.message.edit_text(text, reply_markup=matches_keyboard())
    await callback.answer()


@router.callback_query(F.data == "matches_live")
async def live_matches(callback: CallbackQuery) -> None:
    matches = await load_matches(kind="live")
    await callback.message.edit_text(
        format_matches("📡 Live-матчи", matches),
        reply_markup=matches_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "matches_today")
async def today_matches(callback: CallbackQuery) -> None:
    matches = await load_matches(kind="today")
    await callback.message.edit_text(
        format_matches("🗓 Матчи сегодня", matches),
        reply_markup=matches_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "matches_upcoming")
async def upcoming_matches(callback: CallbackQuery) -> None:
    matches = await load_matches(kind="upcoming")
    await callback.message.edit_text(
        format_matches("🔜 Ближайшие матчи", matches),
        reply_markup=matches_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "matches_tournaments")
async def tournaments(callback: CallbackQuery) -> None:
    async with async_session() as session:
        result = await session.execute(select(Tournament).order_by(Tournament.name).limit(20))
        items = result.scalars().all()

    if not items:
        text = "🏆 <b>Турниры</b>\n\nПока нет данных. Запустите синхронизацию матчей."
    else:
        lines = ["🏆 <b>Турниры</b>\n"]
        for item in items:
            details = " / ".join(part for part in [item.league_name, item.serie_name] if part)
            lines.append(f"• {item.name}" + (f"\n  {details}" if details else ""))
        text = "\n".join(lines)

    await callback.message.edit_text(text, reply_markup=matches_keyboard())
    await callback.answer()


async def load_matches(kind: str) -> list[tuple[DotaMatch, Team | None, Team | None, Tournament | None]]:
    now = datetime.utcnow()
    query = select(DotaMatch).order_by(DotaMatch.starts_at.is_(None), DotaMatch.starts_at).limit(15)

    if kind == "live":
        query = query.where(DotaMatch.status == "live")
    elif kind == "today":
        moscow = ZoneInfo(settings.app_timezone)
        start_local = datetime.now(moscow).replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local + timedelta(days=1)
        start_utc = start_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        end_utc = end_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        query = query.where(DotaMatch.starts_at >= start_utc, DotaMatch.starts_at < end_utc)
    elif kind == "upcoming":
        query = query.where(DotaMatch.starts_at >= now, DotaMatch.status != "finished")

    async with async_session() as session:
        result = await session.execute(query)
        matches = result.scalars().all()
        rows = []
        for match in matches:
            team_a = await session.get(Team, match.team_a_id) if match.team_a_id else None
            team_b = await session.get(Team, match.team_b_id) if match.team_b_id else None
            tournament = (
                await session.get(Tournament, match.tournament_id)
                if match.tournament_id
                else None
            )
            rows.append((match, team_a, team_b, tournament))
        return rows


def format_matches(
    title: str,
    matches: list[tuple[DotaMatch, Team | None, Team | None, Tournament | None]],
) -> str:
    if not matches:
        return f"{title}\n\nПока нет данных. Запустите синхронизацию матчей."

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
    starts_at = format_moscow_time(match.starts_at)
    score = format_score(match)

    return (
        f"🎮 <b>{team_a_name} vs {team_b_name}</b>\n"
        f"🏆 {tournament_name}\n"
        f"🎯 Формат: {best_of}\n"
        f"🕒 Начало: {starts_at}\n"
        f"📌 Статус: {translate_status(match.status)}\n"
        f"📊 Счёт: {score}"
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


def translate_status(status: str) -> str:
    return {
        "scheduled": "запланирован",
        "live": "live",
        "finished": "завершён",
        "canceled": "отменён",
        "not_played": "не сыгран",
    }.get(status, status)
