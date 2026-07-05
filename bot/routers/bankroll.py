from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.keyboards import main_menu_keyboard
from config.settings import settings

router = Router()


@router.callback_query(F.data == "bankroll")
async def bankroll_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        (
            "💰 <b>Банк</b>\n\n"
            f"Стартовый банк: {settings.start_bankroll:.0f} {settings.currency}\n"
            f"Риск-профиль: {settings.risk_profile}\n"
            f"Максимум на ставку: {settings.max_bet_percent}%\n"
            f"Дневной стоп: {settings.max_daily_loss_percent}%"
        ),
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()
