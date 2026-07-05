from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, update, delete
from datetime import datetime
import asyncio
import logging
from config.texts import (
    CHANNELS_MENU_TEXT,
    NO_CHANNELS_TEXT,
    CHANNEL_INFO_TEXT,
    CHANNEL_REMOVED_TEXT,
    ERROR_MESSAGES,
    ADD_CHANNEL_TEXT,
    CHANNEL_ADDED_SUCCESS_TEXT,
    HISTORY_SCAN_TEXT,
    HISTORY_SCANNING_TEXT,
    HISTORY_SCAN_COMPLETE_TEXT,
    HISTORY_SCAN_ERROR_TEXT,
    HISTORY_SCAN_BUTTONS,
)
from keyboards.inline_keyboards import (
    channels_menu_keyboard,
    channel_select_keyboard,
    channel_actions_keyboard,
    stats_period_keyboard,
    confirm_keyboard,
    back_to_main_keyboard,
)
from database.database import async_session
from database.models import Channel, Prediction
from config.settings import HISTORY_SCAN_ENABLED, AUTO_SCAN_ON_ADD

logger = logging.getLogger(__name__)
router = Router()


# Состояния для FSM
class ChannelStates(StatesGroup):
    waiting_for_username = State()


@router.callback_query(F.data == "channels")
async def channels_menu(callback: CallbackQuery):
    """Меню управления каналами"""
    async with async_session() as session:
        result = await session.execute(select(Channel))
        all_channels = result.scalars().all()

        active_result = await session.execute(
            select(Channel).where(Channel.is_active == True)
        )
        active_channels = active_result.scalars().all()

        count = len(all_channels)
        active = len(active_channels)

    text = CHANNELS_MENU_TEXT.format(count=count, active=active)
    await callback.message.edit_text(text=text, reply_markup=channels_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == "channels_list")
async def channels_list(callback: CallbackQuery):
    """Список каналов"""
    async with async_session() as session:
        result = await session.execute(select(Channel))
        channels = result.scalars().all()

    if not channels:
        await callback.message.edit_text(
            text=NO_CHANNELS_TEXT, reply_markup=channels_menu_keyboard()
        )
    else:
        await callback.message.edit_text(
            text="📺 <b>Выберите канал:</b>",
            reply_markup=channel_select_keyboard(channels, "view"),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("channel_view_"))
async def channel_view(callback: CallbackQuery):
    """Просмотр информации о канале"""
    try:
        channel_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("Ошибка в данных", show_alert=True)
        return

    async with async_session() as session:
        channel = await session.get(Channel, channel_id)
        if not channel:
            await callback.answer("Канал не найден", show_alert=True)
            return

        # Подсчитываем количество прогнозов
        predictions_result = await session.execute(
            select(Prediction).where(Prediction.channel_id == channel_id)
        )
        predictions = predictions_result.scalars().all()

        # Последний прогноз
        last_prediction = "Нет данных"
        if predictions:
            latest = max(predictions, key=lambda p: p.created_at)
            last_prediction = latest.created_at.strftime("%d.%m.%Y %H:%M")

        # Время обновления результатов
        results_updated = "Не обновлялись"
        if channel.results_updated:
            results_updated = channel.results_updated.strftime("%d.%m.%Y %H:%M")

    text = CHANNEL_INFO_TEXT.format(
        name=channel.name,
        username=channel.username,
        created_date=channel.created_at.strftime("%d.%m.%Y"),
        predictions_count=len(predictions),
        last_prediction=last_prediction,
        results_updated=results_updated,
    )

    await callback.message.edit_text(
        text=text, reply_markup=channel_actions_keyboard(channel_id)
    )
    await callback.answer()


@router.callback_query(F.data == "channels_add")
async def add_channel_start(callback: CallbackQuery, state: FSMContext):
    """Начало добавления канала"""
    await callback.message.edit_text(
        text=ADD_CHANNEL_TEXT, reply_markup=back_to_main_keyboard()
    )
    await state.set_state(ChannelStates.waiting_for_username)
    await callback.answer()


@router.message(ChannelStates.waiting_for_username)
async def add_channel_process(message: Message, state: FSMContext):
    """Обработка добавления канала"""
    username = message.text.strip().lower()

    # Очистка username
    if username.startswith("@"):
        username = username[1:]

    if not username or len(username) < 3:
        await message.answer(
            "❌ Некорректный username канала. Попробуйте еще раз или используйте команду /menu для отмены."
        )
        return

    async with async_session() as session:
        # Проверяем, не существует ли уже такой канал
        existing = await session.execute(
            select(Channel).where(Channel.username == username)
        )

        if existing.scalar_one_or_none():
            await message.answer(ERROR_MESSAGES["already_exists"])
            await state.clear()
            return

        # Создаем новый канал
        try:
            new_channel = Channel(
                username=username,
                name=f"Канал @{username}",
                url=f"https://t.me/{username}",
                is_active=True,
            )

            session.add(new_channel)
            await session.commit()

            # Получаем ID нового канала
            await session.refresh(new_channel)
            channel_id = new_channel.id

            await state.clear()

            # Отправляем подтверждение добавления
            success_text = CHANNEL_ADDED_SUCCESS_TEXT.format(
                channel_name=new_channel.name,
                username=username,
                date=datetime.now().strftime("%d.%m.%Y %H:%M"),
            )

            # Предлагаем сканирование истории
            if HISTORY_SCAN_ENABLED:
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="🔍 Сканировать историю",
                                callback_data=f"scan_history_{channel_id}",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text="⏭ Пропустить", callback_data="channels"
                            )
                        ],
                    ]
                )

                await message.answer(success_text, reply_markup=keyboard)
            else:
                await message.answer(
                    success_text, reply_markup=channels_menu_keyboard()
                )

            # Автоматическое сканирование если включено
            if AUTO_SCAN_ON_ADD:
                asyncio.create_task(
                    auto_scan_channel_history(
                        message.bot, new_channel, message.from_user.id
                    )
                )

        except Exception as e:
            await message.answer(f"❌ Ошибка добавления канала: {str(e)}")
            await state.clear()


@router.callback_query(F.data.startswith("scan_history_"))
async def scan_history_menu(callback: CallbackQuery):
    """Меню выбора периода сканирования"""
    try:
        channel_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("Ошибка в данных", show_alert=True)
        return

    async with async_session() as session:
        channel = await session.get(Channel, channel_id)
        if not channel:
            await callback.answer("Канал не найден", show_alert=True)
            return

    text = HISTORY_SCAN_TEXT.format(channel_name=channel.name)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=HISTORY_SCAN_BUTTONS["7_days"],
                    callback_data=f"history_{channel_id}_7",
                ),
                InlineKeyboardButton(
                    text=HISTORY_SCAN_BUTTONS["30_days"],
                    callback_data=f"history_{channel_id}_30",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=HISTORY_SCAN_BUTTONS["90_days"],
                    callback_data=f"history_{channel_id}_90",
                )
            ],
            [
                InlineKeyboardButton(
                    text=HISTORY_SCAN_BUTTONS["skip"], callback_data="channels"
                )
            ],
        ]
    )

    await callback.message.edit_text(text=text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("history_"))
async def start_history_scan(callback: CallbackQuery):
    """Запуск сканирования истории"""
    try:
        parts = callback.data.split("_")
        channel_id = int(parts[1])
        days = int(parts[2])
    except (ValueError, IndexError):
        await callback.answer("Ошибка в данных", show_alert=True)
        return

    async with async_session() as session:
        channel = await session.get(Channel, channel_id)
        if not channel:
            await callback.answer("Канал не найден", show_alert=True)
            return

    # Показываем процесс загрузки
    loading_text = HISTORY_SCANNING_TEXT.format(
        channel_name=channel.name, days=days, messages_count=0, predictions_count=0
    )

    await callback.message.edit_text(
        text=loading_text, reply_markup=back_to_main_keyboard()
    )

    # Функция обновления прогресса
    async def update_progress(stats):
        try:
            progress_text = HISTORY_SCANNING_TEXT.format(
                channel_name=channel.name,
                days=days,
                messages_count=stats["messages_scanned"],
                predictions_count=stats["predictions_found"],
            )
            await callback.message.edit_text(
                text=progress_text, reply_markup=back_to_main_keyboard()
            )
        except Exception:
            pass

    try:
        # Запускаем сканирование
        from utils.parser import scan_channel_history

        stats = await scan_channel_history(
            callback.bot, channel, days, progress_callback=update_progress
        )

        # Показываем результат
        if "error_message" in stats:
            error_text = HISTORY_SCAN_ERROR_TEXT.format(
                channel_name=channel.name, error_reason=stats["error_message"]
            )

            await callback.message.edit_text(
                text=error_text, reply_markup=back_to_main_keyboard()
            )
        else:
            success_text = HISTORY_SCAN_COMPLETE_TEXT.format(
                channel_name=channel.name,
                days=days,
                messages_scanned=stats["messages_scanned"],
                predictions_found=stats["predictions_found"],
                auto_results=stats["auto_results"],
            )

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📊 Статистика канала",
                            callback_data=f"channel_stats_{channel_id}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🏠 Главное меню", callback_data="main_menu"
                        )
                    ],
                ]
            )

            await callback.message.edit_text(text=success_text, reply_markup=keyboard)

    except Exception as e:
        error_text = HISTORY_SCAN_ERROR_TEXT.format(
            channel_name=channel.name, error_reason=str(e)
        )

        await callback.message.edit_text(
            text=error_text, reply_markup=back_to_main_keyboard()
        )

    await callback.answer()


async def auto_scan_channel_history(bot, channel, user_id):
    """Автоматическое сканирование истории канала в фоне"""
    try:
        from config.settings import DEFAULT_HISTORY_DAYS
        from utils.parser import scan_channel_history

        stats = await scan_channel_history(bot, channel, DEFAULT_HISTORY_DAYS)

        # Отправляем результат пользователю
        if stats["predictions_found"] > 0:
            text = f"✅ <b>Автосканирование завершено</b>\n\n📺 Канал: {channel.name}\n📊 Найдено прогнозов: {stats['predictions_found']}"
            await bot.send_message(user_id, text)

    except Exception as e:
        logger.error(f"❌ Ошибка автосканирования: {e}")


@router.callback_query(F.data.startswith("channel_stats_"))
async def channel_stats_period(callback: CallbackQuery):
    """Выбор периода для статистики канала"""
    try:
        channel_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("Ошибка в данных", show_alert=True)
        return

    await callback.message.edit_text(
        text="📊 <b>Выберите период для анализа:</b>",
        reply_markup=stats_period_keyboard(channel_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("channel_toggle_"))
async def channel_toggle(callback: CallbackQuery):
    """Переключение активности канала"""
    try:
        channel_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("Ошибка в данных", show_alert=True)
        return

    async with async_session() as session:
        channel = await session.get(Channel, channel_id)
        if channel:
            channel.is_active = not channel.is_active
            status = "включен" if channel.is_active else "отключен"
            await session.commit()

            await callback.answer(f"Мониторинг канала {status}", show_alert=True)
            await channel_view(callback)
        else:
            await callback.answer("Канал не найден", show_alert=True)


@router.callback_query(F.data.startswith("channel_delete_"))
async def channel_delete_confirm(callback: CallbackQuery):
    """Подтверждение удаления канала"""
    try:
        channel_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("Ошибка в данных", show_alert=True)
        return

    async with async_session() as session:
        channel = await session.get(Channel, channel_id)
        if not channel:
            await callback.answer("Канал не найден", show_alert=True)
            return

    text = f"❓ <b>Удалить канал {channel.name}?</b>\n\n⚠️ Все данные и статистика будут удалены безвозвратно!"

    await callback.message.edit_text(
        text=text, reply_markup=confirm_keyboard("delete_channel", channel_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_delete_channel_"))
async def channel_delete_confirmed(callback: CallbackQuery):
    """Подтвержденное удаление канала"""
    try:
        channel_id = int(callback.data.split("_")[3])
    except (ValueError, IndexError):
        await callback.answer("Ошибка в данных", show_alert=True)
        return

    async with async_session() as session:
        channel = await session.get(Channel, channel_id)
        channel_name = channel.name if channel else "Неизвестный канал"

        await session.execute(
            delete(Prediction).where(Prediction.channel_id == channel_id)
        )
        await session.execute(delete(Channel).where(Channel.id == channel_id))
        await session.commit()

    text = CHANNEL_REMOVED_TEXT.format(name=channel_name)
    await callback.message.edit_text(text=text, reply_markup=channels_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("cancel_delete_channel_"))
async def channel_delete_cancelled(callback: CallbackQuery):
    """Отмена удаления канала"""
    await callback.answer("Удаление отменено")
    await channels_list(callback)


@router.callback_query(F.data == "channels_remove")
async def channels_remove_select(callback: CallbackQuery):
    """Выбор канала для удаления"""
    async with async_session() as session:
        result = await session.execute(select(Channel))
        channels = result.scalars().all()

    if not channels:
        await callback.message.edit_text(
            text=NO_CHANNELS_TEXT, reply_markup=channels_menu_keyboard()
        )
    else:
        await callback.message.edit_text(
            text="🗑 <b>Выберите канал для удаления:</b>",
            reply_markup=channel_select_keyboard(channels, "delete_select"),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("channel_delete_select_"))
async def channel_delete_select(callback: CallbackQuery):
    """Подтверждение удаления выбранного канала"""
    try:
        channel_id = int(callback.data.split("_")[3])
    except (ValueError, IndexError):
        await callback.answer("Ошибка в данных", show_alert=True)
        return

    await channel_delete_confirm(
        type(
            "MockCallback",
            (),
            {
                "data": f"channel_delete_{channel_id}",
                "message": callback.message,
                "answer": callback.answer,
            },
        )()
    )
