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
        "🏆 Турниры - текущие и ближайшие турниры, матчи турнира.\n"
        "📅 Матчи - live, сегодня, завтра, предстоящие и завершённые матчи.\n"
        "👥 Команды - карточки команд, последние матчи и форма.\n"
        "🎮 Игроки - список игроков и составы, если данные доступны из API.\n"
        "🔮 Прогнозы - оценка вероятности победителя будущего матча по форме команд.\n"
        "🔄 Обновить данные - синхронизация данных PandaScore.\n\n"
        "Бот показывает аналитическую оценку и не подключается к букмекерским сервисам.",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())
    await callback.answer()
