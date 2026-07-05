from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.keyboards import main_menu_keyboard

router = Router()


@router.callback_query(F.data == "signals")
async def signals_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "🎯 <b>Сигналы</b>\n\nValue-сигналы будут формироваться только как рекомендации для ручного подтверждения.",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()
