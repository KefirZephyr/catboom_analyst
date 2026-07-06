from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.keyboards import main_menu_keyboard
from config.settings import settings

router = Router()


@router.callback_query(F.data == "settings")
async def settings_menu(callback: CallbackQuery) -> None:
    pandascore_status = "задан" if settings.pandascore_token.get_secret_value() else "не задан"
    access_mode = (
        "ограничен списком пользователей"
        if settings.allowed_user_ids
        else "открыт для локального использования"
    )
    await callback.message.edit_text(
        (
            "⚙️ <b>Настройки</b>\n\n"
            f"Часовой пояс: {settings.app_timezone}\n"
            f"База данных: {settings.database_url}\n"
            f"PandaScore token: {pandascore_status}\n"
            f"Доступ: {access_mode}\n\n"
            "Данные обновляются вручную из раздела «Обновить данные»."
        ),
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()
