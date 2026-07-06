from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from db.models import Player, Team
from db.session import async_session

router = Router()


def players_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Список игроков", callback_data="players_list")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
        ]
    )


@router.callback_query(F.data == "players")
async def players_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "🎮 <b>Игроки</b>\n\n"
        "Показываются только реальные данные о составах, если они пришли из PandaScore.",
        reply_markup=players_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "players_list")
async def players_list(callback: CallbackQuery) -> None:
    async with async_session() as session:
        result = await session.execute(select(Player).order_by(Player.nickname).limit(40))
        players = list(result.scalars().all())

    if not players:
        await callback.message.edit_text(
            "Игроки пока не загружены. PandaScore не всегда отдаёт составы в ответах матчей.",
            reply_markup=players_keyboard(),
        )
        await callback.answer()
        return

    rows = [
        [InlineKeyboardButton(text=player.nickname[:60], callback_data=f"player_view:{player.id}")]
        for player in players
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="players")])
    await callback.message.edit_text("🎮 <b>Игроки</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.startswith("player_view:"))
async def player_view(callback: CallbackQuery) -> None:
    player_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        player = await session.get(Player, player_id)
        if not player:
            await callback.answer("Игрок не найден", show_alert=True)
            return
        team = await session.get(Team, player.team_id) if player.team_id else None

    text = (
        f"🎮 <b>{player.nickname}</b>\n\n"
        f"Имя: {' '.join(part for part in [player.first_name, player.last_name] if part) or 'нет данных'}\n"
        f"Команда: {team.name if team else 'нет данных'}\n"
        f"Роль: {player.role or 'нет данных'}\n"
        f"Страна: {player.nationality or 'нет данных'}\n\n"
        "Статистика игрока не выдумывается: показываются только поля, доступные из API."
    )
    await callback.message.edit_text(text, reply_markup=players_keyboard())
    await callback.answer()
