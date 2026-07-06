from datetime import datetime

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import exists, select

from bot.routers.matches import format_match_card, hydrate_match
from db.models import DotaMatch, Tournament
from db.session import async_session

router = Router()


def tournaments_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏆 Текущие турниры", callback_data="tournaments_current")],
            [InlineKeyboardButton(text="🔜 Ближайшие турниры", callback_data="tournaments_upcoming")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
        ]
    )


@router.callback_query(F.data == "tournaments")
async def tournaments_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "🏆 <b>Турниры Dota 2</b>\n\n"
        "Смотрите текущие и ближайшие турниры, а также матчи внутри турнира.",
        reply_markup=tournaments_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.in_({"tournaments_current", "tournaments_upcoming"}))
async def tournaments_list(callback: CallbackQuery) -> None:
    kind = callback.data.removeprefix("tournaments_")
    rows, text = await load_tournaments(kind)
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.startswith("tournament_view:"))
async def tournament_view(callback: CallbackQuery) -> None:
    tournament_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        tournament = await session.get(Tournament, tournament_id)
        if not tournament:
            await callback.answer("Турнир не найден", show_alert=True)
            return
        result = await session.execute(
            select(DotaMatch)
            .where(DotaMatch.tournament_id == tournament_id)
            .order_by(DotaMatch.starts_at.is_(None), DotaMatch.starts_at)
            .limit(12)
        )
        matches = [await hydrate_match(session, match) for match in result.scalars().all()]

    lines = [f"🏆 <b>{tournament.name}</b>"]
    details = " / ".join(part for part in [tournament.league_name, tournament.serie_name, tournament.tier] if part)
    if details:
        lines.append(details)
    lines.append("")
    lines.extend(format_match_card(*row) for row in matches)
    if not matches:
        lines.append("Матчи турнира пока не найдены.")

    await callback.message.edit_text("\n\n".join(lines), reply_markup=tournaments_keyboard())
    await callback.answer()


async def load_tournaments(kind: str):
    now = datetime.utcnow()
    if kind == "current":
        match_filter = DotaMatch.status.in_(["live", "scheduled"])
        title = "🏆 <b>Текущие турниры</b>"
    else:
        match_filter = DotaMatch.starts_at >= now
        title = "🔜 <b>Ближайшие турниры</b>"

    async with async_session() as session:
        query = (
            select(Tournament)
            .where(exists().where(DotaMatch.tournament_id == Tournament.id).where(match_filter))
            .order_by(Tournament.updated_at.desc())
            .limit(20)
        )
        result = await session.execute(query)
        tournaments = list(result.scalars().all())

    if not tournaments:
        return [[InlineKeyboardButton(text="⬅️ Назад", callback_data="tournaments")]], (
            f"{title}\n\nПока нет данных. Запустите обновление данных."
        )

    rows = [
        [InlineKeyboardButton(text=tournament.name[:60], callback_data=f"tournament_view:{tournament.id}")]
        for tournament in tournaments
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="tournaments")])
    return rows, title
