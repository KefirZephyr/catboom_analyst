from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from datetime import datetime
from sqlalchemy import select, update
from config.texts import MAIN_MENU_TEXT, WELCOME_TEXT, HELP_TEXT
from keyboards.inline_keyboards import main_menu_keyboard, back_to_main_keyboard
from database.database import async_session
from database.models import User

router = Router()


@router.message(CommandStart())
async def start_command(message: Message):
    """Обработка команды /start"""
    await show_main_menu(message)


@router.message(Command("help"))
async def help_command(message: Message):
    """Обработка команды /help"""
    await message.answer(text=HELP_TEXT, reply_markup=main_menu_keyboard())


async def show_main_menu(message: Message):
    """Показ главного меню"""
    # Регистрация/обновление пользователя
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            # Новый пользователь
            user = User(telegram_id=message.from_user.id, notifications_enabled=True)
            session.add(user)
            text = WELCOME_TEXT
        else:
            # Существующий пользователь
            user.last_active = datetime.utcnow()
            text = MAIN_MENU_TEXT

        await session.commit()

    await message.answer(text=text, reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery):
    """Возврат в главное меню"""
    # Обновляем активность пользователя
    async with async_session() as session:
        await session.execute(
            update(User)
            .where(User.telegram_id == callback.from_user.id)
            .values(last_active=datetime.utcnow())
        )
        await session.commit()

    await callback.message.edit_text(
        text=MAIN_MENU_TEXT, reply_markup=main_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "help")
async def help_callback(callback: CallbackQuery):
    """Справка"""
    await callback.message.edit_text(
        text=HELP_TEXT, reply_markup=back_to_main_keyboard()
    )
    await callback.answer()
