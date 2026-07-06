from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from db.models import Player, Team
from db.session import async_session

router = Router()

PLAYERS_EMPTY_TEXT = (
    "Игроки пока не загружены. Нажмите 🔄 Обновить данные или откройте команду, "
    "чтобы попробовать загрузить состав. Если PandaScore не отдаёт составы по вашему тарифу/API, "
    "бот покажет только команды и матчи."
)


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
            PLAYERS_EMPTY_TEXT,
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

    text = format_player_card(player, team)
    await callback.message.edit_text(text, reply_markup=players_keyboard())
    await callback.answer()


def format_player_card(player: Player, team: Team | None) -> str:
    full_name = " ".join(part for part in [player.first_name, player.last_name] if part) or "нет данных"
    updated_at = player.updated_at.strftime("%d.%m.%Y %H:%M") if player.updated_at else "нет данных"
    status = "активен" if player.is_active else "неактивен"
    return (
        f"🎮 <b>{player.nickname}</b>\n\n"
        f"Имя: {full_name}\n"
        f"Команда: {team.name if team else 'нет данных'}\n"
        f"Роль/позиция: {player.role or 'нет данных'}\n"
        f"Страна: {player.nationality or 'нет данных'}\n"
        f"Статус: {status}\n"
        f"Обновлено: {updated_at}\n\n"
        "Статистика игрока не выдумывается: показываются только поля, доступные из API."
    )
