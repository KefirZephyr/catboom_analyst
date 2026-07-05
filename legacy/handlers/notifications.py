from aiogram import Router, F
from aiogram.types import CallbackQuery
from datetime import datetime
from sqlalchemy import select, update
from config.texts import (
    NOTIFICATIONS_MENU_TEXT,
    NOTIFICATIONS_ENABLED_TEXT,
    NOTIFICATIONS_DISABLED_TEXT,
)
from keyboards.inline_keyboards import notifications_keyboard, back_to_main_keyboard
from database.database import async_session
from database.models import User, Channel

router = Router()


@router.callback_query(F.data == "notifications")
async def notifications_menu(callback: CallbackQuery):
    """Меню управления уведомлениями"""
    async with async_session() as session:
        # Получаем пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            # Создаем пользователя если не существует
            user = User(telegram_id=callback.from_user.id, notifications_enabled=True)
            session.add(user)
            await session.commit()

        # Получаем количество активных каналов
        channels_result = await session.execute(
            select(Channel).where(Channel.is_active == True)
        )
        channels_count = len(channels_result.scalars().all())

        # Считаем обновления результатов за сегодня (заглушка)
        results_updated = 0

        status = "Включены" if user.notifications_enabled else "Отключены"
        today_count = user.notifications_count_today or 0

    text = NOTIFICATIONS_MENU_TEXT.format(
        status=status,
        today_count=today_count,
        channels_count=channels_count,
        results_updated=results_updated,
    )

    await callback.message.edit_text(
        text=text, reply_markup=notifications_keyboard(user.notifications_enabled)
    )
    await callback.answer()


@router.callback_query(F.data == "notifications_enable")
async def enable_notifications(callback: CallbackQuery):
    """Включение уведомлений"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            user = User(telegram_id=callback.from_user.id, notifications_enabled=True)
            session.add(user)
        else:
            user.notifications_enabled = True
            user.last_active = datetime.utcnow()

        await session.commit()

    await callback.message.edit_text(
        text=NOTIFICATIONS_ENABLED_TEXT, reply_markup=back_to_main_keyboard()
    )
    await callback.answer("✅ Уведомления включены")


@router.callback_query(F.data == "notifications_disable")
async def disable_notifications(callback: CallbackQuery):
    """Отключение уведомлений"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            user = User(telegram_id=callback.from_user.id, notifications_enabled=False)
            session.add(user)
        else:
            user.notifications_enabled = False
            user.last_active = datetime.utcnow()

        await session.commit()

    await callback.message.edit_text(
        text=NOTIFICATIONS_DISABLED_TEXT, reply_markup=back_to_main_keyboard()
    )
    await callback.answer("🔕 Уведомления отключены")


@router.callback_query(F.data == "notifications_status")
async def notifications_status(callback: CallbackQuery):
    """Статус уведомлений"""
    await notifications_menu(callback)
