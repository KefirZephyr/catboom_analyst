from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from bot.keyboards import main_menu_keyboard
from bot.texts import MAIN_MENU_TEXT

router = Router()


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "<b>Справка CatBoom Dota Analyst v2</b>\n\n"
        "/start - главное меню\n"
        "/help - эта справка\n\n"
        "Разделы:\n"
        "📡 Матчи - синхронизация и просмотр Dota 2 матчей.\n"
        "📊 Telegram-каналы - сканирование прогнозов и рейтинг каналов.\n"
        "💰 Банк - банк, лимиты и risk profile.\n"
        "🎯 Сигналы - аналитические value-рекомендации для ручного решения.\n\n"
        "Бот не делает автоматические ставки.",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())
    await callback.answer()
