from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.keyboards import main_menu_keyboard

router = Router()


@router.callback_query(F.data == "matches")
async def matches_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "📡 <b>Матчи</b>\n\nСинхронизация матчей Dota 2 через PandaScore будет добавлена следующим этапом.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()
