from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from modules.telegram_parser.channel_rating import (
    ChannelRatingStats,
    calculate_all_channels_stats,
    calculate_channel_stats,
)
from modules.telegram_parser.result_settlement import settle_predictions
from modules.telegram_parser.channel_sync import (
    add_channel,
    ensure_default_channels,
    list_channels,
    scan_all_channels,
    scan_channel,
    toggle_channel,
)

router = Router()


class ChannelStates(StatesGroup):
    waiting_for_username = State()


def channels_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Список каналов", callback_data="channels_list")],
            [InlineKeyboardButton(text="➕ Добавить канал", callback_data="channels_add")],
            [InlineKeyboardButton(text="🔄 Сканировать все", callback_data="channels_scan_all")],
            [InlineKeyboardButton(text="🔄 Обновить результаты", callback_data="channels_update_results")],
            [InlineKeyboardButton(text="📊 Рейтинг каналов", callback_data="channels_stats")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
        ]
    )


def channel_actions_keyboard(channel_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_text = "⏸ Выключить" if is_active else "▶️ Включить"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data=f"channels_toggle:{channel_id}")],
            [
                InlineKeyboardButton(
                    text="🔄 Сканировать канал",
                    callback_data=f"channels_scan:{channel_id}",
                )
            ],
            [InlineKeyboardButton(text="📊 Рейтинг всех каналов", callback_data="channels_stats")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="channels")],
        ]
    )


def format_last_sync(value) -> str:
    return value.strftime("%d.%m.%Y %H:%M") if value else "ещё не сканировался"


def format_percent(value: float) -> str:
    return f"{value:.1f}%"


async def render_channel_card(callback: CallbackQuery, channel_id: int) -> None:
    channels = await list_channels()
    channel = next((item for item in channels if item.id == channel_id), None)

    if not channel:
        await callback.answer("Канал не найден", show_alert=True)
        return

    stats = await calculate_channel_stats(channel_id)
    status = "включён" if channel.is_active else "выключен"
    text = (
        f"📊 <b>{channel.title or '@' + channel.username}</b>\n\n"
        f"Username: @{channel.username}\n"
        f"Статус: {status}\n"
        f"Последнее сканирование: {format_last_sync(channel.last_sync_at)}\n\n"
    )

    if stats:
        text += format_channel_stats_block(stats)

    if channel.last_error:
        text += f"\n\nПоследняя ошибка: {channel.last_error[:300]}"

    await callback.message.edit_text(
        text,
        reply_markup=channel_actions_keyboard(channel.id, channel.is_active),
    )


def format_channel_stats_block(stats: ChannelRatingStats) -> str:
    best_market = stats.best_market or "нет данных"
    worst_market = stats.worst_market or "нет данных"
    return (
        "<b>Качество канала</b>\n"
        f"Прогнозов: {stats.total_predictions}\n"
        f"Рассчитано: {stats.resolved_predictions}\n"
        f"Winrate: {format_percent(stats.winrate)} ({stats.win_count}W / {stats.loss_count}L)\n"
        f"ROI flat: {format_percent(stats.roi_flat)}\n"
        f"Profit flat: {stats.profit_flat:+.2f} unit\n"
        f"Средний кэф: {stats.avg_odds:.2f}\n"
        f"Pending: {stats.pending_predictions}\n"
        f"Needs review: {stats.needs_review_predictions}\n"
        f"Лучший рынок: {best_market}\n"
        f"Худший рынок: {worst_market}\n"
        f"Рейтинг: {stats.rating_score:.1f} / {stats.rating_grade}\n\n"
        "ROI считается по flat stake 1 unit на каждый рассчитанный прогноз."
    )


@router.callback_query(F.data == "channels")
async def channels_menu(callback: CallbackQuery) -> None:
    await ensure_default_channels()
    await callback.message.edit_text(
        "📊 <b>Telegram-каналы</b>\n\nУправление каналами и оценка качества Dota 2 прогнозов.",
        reply_markup=channels_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "channels_list")
async def channels_list(callback: CallbackQuery) -> None:
    channels = await list_channels()
    if not channels:
        await callback.message.edit_text("Каналы пока не добавлены.", reply_markup=channels_keyboard())
        await callback.answer()
        return

    rows = []
    for channel in channels:
        status = "🟢" if channel.is_active else "🔴"
        title = channel.title or f"@{channel.username}"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{status} {title}",
                    callback_data=f"channels_view:{channel.id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="channels")])

    await callback.message.edit_text(
        "📋 <b>Список Telegram-каналов</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("channels_view:"))
async def channel_view(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.split(":", 1)[1])
    await render_channel_card(callback, channel_id)
    await callback.answer()


@router.callback_query(F.data == "channels_add")
async def add_channel_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ChannelStates.waiting_for_username)
    await callback.message.edit_text(
        "➕ <b>Добавить Telegram-канал</b>\n\nОтправьте username канала. Можно с символом @.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="channels")]]
        ),
    )
    await callback.answer()


@router.message(ChannelStates.waiting_for_username)
async def add_channel_finish(message: Message, state: FSMContext) -> None:
    try:
        channel = await add_channel(message.text or "")
    except ValueError as exc:
        await message.answer(str(exc))
        return

    await state.clear()
    await message.answer(f"✅ Канал @{channel.username} добавлен.", reply_markup=channels_keyboard())


@router.callback_query(F.data.startswith("channels_toggle:"))
async def toggle_channel_callback(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.split(":", 1)[1])
    channel = await toggle_channel(channel_id)
    if not channel:
        await callback.answer("Канал не найден", show_alert=True)
        return

    status = "включён" if channel.is_active else "выключен"
    await callback.answer(f"Канал {status}", show_alert=True)
    await render_channel_card(callback, channel_id)


@router.callback_query(F.data.startswith("channels_scan:"))
async def scan_channel_callback(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.split(":", 1)[1])
    await callback.message.edit_text(
        "🔄 Сканирую канал через Telethon...",
        reply_markup=channels_keyboard(),
    )
    result = await scan_channel(channel_id)

    if result.error:
        text = f"⚠️ <b>Сканирование не выполнено</b>\n\n@{result.username}\nОшибка: {result.error}"
    else:
        text = (
            f"✅ <b>Сканирование завершено</b>\n\n"
            f"Канал: @{result.username}\n"
            f"Проверено сообщений: {result.scanned_messages}\n"
            f"Сохранено прогнозов: {result.saved_predictions}\n"
            f"Дубликатов пропущено: {result.skipped_duplicates}"
        )

    await callback.message.edit_text(text, reply_markup=channels_keyboard())
    await callback.answer()


@router.callback_query(F.data == "channels_scan_all")
async def scan_all_channels_callback(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "🔄 Сканирую активные каналы через Telethon...",
        reply_markup=channels_keyboard(),
    )
    results = await scan_all_channels()

    if not results:
        text = "Нет активных каналов для сканирования."
    else:
        lines = ["✅ <b>Сканирование завершено</b>\n"]
        for result in results:
            if result.error:
                lines.append(f"@{result.username}: ошибка - {result.error}")
            else:
                lines.append(
                    f"@{result.username}: {result.saved_predictions} новых, "
                    f"{result.skipped_duplicates} дублей, {result.scanned_messages} сообщений"
                )
        text = "\n".join(lines)

    await callback.message.edit_text(text, reply_markup=channels_keyboard())
    await callback.answer()


@router.callback_query(F.data == "channels_stats")
async def channels_stats(callback: CallbackQuery) -> None:
    stats = await calculate_all_channels_stats()
    if not stats:
        await callback.message.edit_text("Статистика пока пустая.", reply_markup=channels_keyboard())
        await callback.answer()
        return

    lines = [
        "📊 <b>Рейтинг Telegram-каналов</b>\n",
        "ROI считается по flat stake 1 unit на каждый рассчитанный прогноз.\n",
    ]
    for index, item in enumerate(stats, 1):
        lines.append(
            f"{index}. <b>@{item.username}</b> — {item.rating_grade} ({item.rating_score:.1f})\n"
            f"Прогнозов: {item.total_predictions}, рассчитано: {item.resolved_predictions}\n"
            f"Winrate: {format_percent(item.winrate)}, ROI: {format_percent(item.roi_flat)}\n"
            f"Avg кэф: {item.avg_odds:.2f}, pending: {item.pending_predictions}, "
            f"review: {item.needs_review_predictions}"
        )

    await callback.message.edit_text("\n\n".join(lines), reply_markup=channels_keyboard())
    await callback.answer()


@router.callback_query(F.data == "channels_update_results")
async def channels_update_results(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "🔄 <b>Обновляю результаты прогнозов...</b>",
        reply_markup=channels_keyboard(),
    )
    summary = await settle_predictions()
    text = (
        "✅ <b>Результаты обновлены</b>\n\n"
        f"Проверено: {summary.checked}\n"
        f"Побед: {summary.wins}\n"
        f"Поражений: {summary.losses}\n"
        f"Возвратов: {summary.voids}\n"
        f"Пропущено: {summary.skipped}\n"
        f"Ошибок: {summary.errors}\n\n"
        "ROI каналов пересчитывается по рассчитанным прогнозам."
    )
    await callback.message.edit_text(text, reply_markup=channels_keyboard())
    await callback.answer()
