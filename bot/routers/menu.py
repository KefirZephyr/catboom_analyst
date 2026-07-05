from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from bot.keyboards import main_menu_keyboard
from bot.texts import MAIN_MENU_TEXT

router = Router()


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(MAIN_MENU_TEXT, reply_markup=main_menu_keyboard())
    await callback.answer()
