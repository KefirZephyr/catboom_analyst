from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.keyboards import main_menu_keyboard
from config.settings import settings

router = Router()


@router.callback_query(F.data == "channels")
async def channels_menu(callback: CallbackQuery) -> None:
    channels = "\n".join(f"@{channel}" for channel in settings.default_channels)
    await callback.message.edit_text(
        f"📊 <b>Telegram-каналы</b>\n\nСтартовый список:\n{channels}",
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()
