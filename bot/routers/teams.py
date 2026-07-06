from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import or_, select

from bot.routers.matches import format_match_card, hydrate_match
from db.models import DotaMatch, Player, Team
from db.session import async_session
from modules.analytics.match_analytics import calculate_team_form, calculate_tournament_form

router = Router()


def teams_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 Список команд", callback_data="teams_list")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
        ]
    )


@router.callback_query(F.data == "teams")
async def teams_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "👥 <b>Команды</b>\n\n"
        "Карточки команд, последние матчи, форма и результаты в текущем турнире.",
        reply_markup=teams_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "teams_list")
async def teams_list(callback: CallbackQuery) -> None:
    async with async_session() as session:
        result = await session.execute(select(Team).order_by(Team.name).limit(30))
        teams = list(result.scalars().all())

    if not teams:
        await callback.message.edit_text("Команды пока не загружены. Запустите обновление данных.", reply_markup=teams_keyboard())
        await callback.answer()
        return

    rows = [
        [InlineKeyboardButton(text=team.name[:60], callback_data=f"team_view:{team.id}")]
        for team in teams
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="teams")])
    await callback.message.edit_text("👥 <b>Команды</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.startswith("team_view:"))
async def team_view(callback: CallbackQuery) -> None:
    team_id = int(callback.data.split(":", 1)[1])
    text = await format_team_card(team_id)
    if not text:
        await callback.answer("Команда не найдена", show_alert=True)
        return
    await callback.message.edit_text(text, reply_markup=teams_keyboard())
    await callback.answer()


async def format_team_card(team_id: int) -> str | None:
    async with async_session() as session:
        team = await session.get(Team, team_id)
        if not team:
            return None

        match_result = await session.execute(
            select(DotaMatch)
            .where(or_(DotaMatch.team_a_id == team_id, DotaMatch.team_b_id == team_id))
            .order_by(DotaMatch.starts_at.desc().nullslast(), DotaMatch.id.desc())
            .limit(10)
        )
        matches = [await hydrate_match(session, match) for match in match_result.scalars().all()]

        players_result = await session.execute(
            select(Player).where(Player.team_id == team_id, Player.is_active == True).order_by(Player.nickname).limit(10)
        )
        players = list(players_result.scalars().all())

    form5 = await calculate_team_form(team_id, limit=5)
    form10 = await calculate_team_form(team_id, limit=10)
    current_tournament_id = matches[0][0].tournament_id if matches else None
    tournament_form = await calculate_tournament_form(team_id, current_tournament_id)

    lines = [
        f"👥 <b>{team.name}</b>",
        f"Тег: {team.acronym or 'не указан'}",
        f"Форма 5 матчей: {form5.wins}/{form5.matches} ({form5.winrate:.1f}%)",
        f"Форма 10 матчей: {form10.wins}/{form10.matches} ({form10.winrate:.1f}%)",
        f"Текущий турнир: {tournament_form.wins}/{tournament_form.matches} ({tournament_form.winrate:.1f}%)",
        "",
        "<b>Игроки</b>",
    ]
    lines.extend(f"• {player.nickname}" for player in players) if players else lines.append("Нет данных о составе.")
    lines.append("")
    lines.append("<b>Последние матчи</b>")
    lines.extend(format_match_card(*row) for row in matches[:5]) if matches else lines.append("Матчи не найдены.")
    return "\n\n".join(lines)
