from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.keyboards import main_menu_keyboard
from config.settings import settings

router = Router()


@router.callback_query(F.data == "settings")
async def settings_menu(callback: CallbackQuery) -> None:
    auto_betting = "выключены" if not settings.auto_betting_enabled else "игнорируются"
    await callback.message.edit_text(
        (
            "⚙️ <b>Настройки</b>\n\n"
            f"Часовой пояс: {settings.app_timezone}\n"
            f"Валюта: {settings.currency}\n"
            f"Автоставки: {auto_betting}\n"
            f"Минимальный edge: {settings.min_edge_percent}%\n"
            f"Минимальная confidence: {settings.min_confidence_percent}%"
        ),
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()
