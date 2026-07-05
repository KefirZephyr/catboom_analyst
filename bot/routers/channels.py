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
            [InlineKeyboardButton(text="рџ“‹ РЎРїРёСЃРѕРє РєР°РЅР°Р»РѕРІ", callback_data="channels_list")],
            [InlineKeyboardButton(text="вћ• Р”РѕР±Р°РІРёС‚СЊ РєР°РЅР°Р»", callback_data="channels_add")],
            [InlineKeyboardButton(text="рџ”„ РЎРєР°РЅРёСЂРѕРІР°С‚СЊ РІСЃРµ", callback_data="channels_scan_all")],
            [InlineKeyboardButton(text="🔄 Обновить результаты", callback_data="channels_update_results")],
            [InlineKeyboardButton(text="рџ“Љ Р РµР№С‚РёРЅРі РєР°РЅР°Р»РѕРІ", callback_data="channels_stats")],
            [InlineKeyboardButton(text="в¬…пёЏ РќР°Р·Р°Рґ", callback_data="main_menu")],
        ]
    )


def channel_actions_keyboard(channel_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_text = "вЏё Р’С‹РєР»СЋС‡РёС‚СЊ" if is_active else "в–¶пёЏ Р’РєР»СЋС‡РёС‚СЊ"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data=f"channels_toggle:{channel_id}")],
            [
                InlineKeyboardButton(
                    text="рџ”„ РЎРєР°РЅРёСЂРѕРІР°С‚СЊ РєР°РЅР°Р»",
                    callback_data=f"channels_scan:{channel_id}",
                )
            ],
            [InlineKeyboardButton(text="рџ“Љ Р РµР№С‚РёРЅРі РІСЃРµС… РєР°РЅР°Р»РѕРІ", callback_data="channels_stats")],
            [InlineKeyboardButton(text="в¬…пёЏ РќР°Р·Р°Рґ", callback_data="channels")],
        ]
    )


def format_last_sync(value) -> str:
    return value.strftime("%d.%m.%Y %H:%M") if value else "РµС‰С‘ РЅРµ СЃРєР°РЅРёСЂРѕРІР°Р»СЃСЏ"


def format_percent(value: float) -> str:
    return f"{value:.1f}%"


async def render_channel_card(callback: CallbackQuery, channel_id: int) -> None:
    channels = await list_channels()
    channel = next((item for item in channels if item.id == channel_id), None)

    if not channel:
        await callback.answer("РљР°РЅР°Р» РЅРµ РЅР°Р№РґРµРЅ", show_alert=True)
        return

    stats = await calculate_channel_stats(channel_id)
    status = "РІРєР»СЋС‡С‘РЅ" if channel.is_active else "РІС‹РєР»СЋС‡РµРЅ"
    text = (
        f"рџ“Љ <b>{channel.title or '@' + channel.username}</b>\n\n"
        f"Username: @{channel.username}\n"
        f"РЎС‚Р°С‚СѓСЃ: {status}\n"
        f"РџРѕСЃР»РµРґРЅРµРµ СЃРєР°РЅРёСЂРѕРІР°РЅРёРµ: {format_last_sync(channel.last_sync_at)}\n\n"
    )

    if stats:
        text += format_channel_stats_block(stats)

    if channel.last_error:
        text += f"\n\nРџРѕСЃР»РµРґРЅСЏСЏ РѕС€РёР±РєР°: {channel.last_error[:300]}"

    await callback.message.edit_text(
        text,
        reply_markup=channel_actions_keyboard(channel.id, channel.is_active),
    )


def format_channel_stats_block(stats: ChannelRatingStats) -> str:
    best_market = stats.best_market or "РЅРµС‚ РґР°РЅРЅС‹С…"
    worst_market = stats.worst_market or "РЅРµС‚ РґР°РЅРЅС‹С…"
    return (
        "<b>РљР°С‡РµСЃС‚РІРѕ РєР°РЅР°Р»Р°</b>\n"
        f"РџСЂРѕРіРЅРѕР·РѕРІ: {stats.total_predictions}\n"
        f"Р Р°СЃСЃС‡РёС‚Р°РЅРѕ: {stats.resolved_predictions}\n"
        f"Winrate: {format_percent(stats.winrate)} ({stats.win_count}W / {stats.loss_count}L)\n"
        f"ROI flat: {format_percent(stats.roi_flat)}\n"
        f"Profit flat: {stats.profit_flat:+.2f} unit\n"
        f"РЎСЂРµРґРЅРёР№ РєСЌС„: {stats.avg_odds:.2f}\n"
        f"Pending: {stats.pending_predictions}\n"
        f"Needs review: {stats.needs_review_predictions}\n"
        f"Р›СѓС‡С€РёР№ СЂС‹РЅРѕРє: {best_market}\n"
        f"РҐСѓРґС€РёР№ СЂС‹РЅРѕРє: {worst_market}\n"
        f"Р РµР№С‚РёРЅРі: {stats.rating_score:.1f} / {stats.rating_grade}\n\n"
        "ROI СЃС‡РёС‚Р°РµС‚СЃСЏ РїРѕ flat stake 1 unit РЅР° РєР°Р¶РґС‹Р№ СЂР°СЃСЃС‡РёС‚Р°РЅРЅС‹Р№ РїСЂРѕРіРЅРѕР·."
    )


@router.callback_query(F.data == "channels")
async def channels_menu(callback: CallbackQuery) -> None:
    await ensure_default_channels()
    await callback.message.edit_text(
        "рџ“Љ <b>Telegram-РєР°РЅР°Р»С‹</b>\n\nРЈРїСЂР°РІР»РµРЅРёРµ РєР°РЅР°Р»Р°РјРё Рё РѕС†РµРЅРєР° РєР°С‡РµСЃС‚РІР° Dota 2 РїСЂРѕРіРЅРѕР·РѕРІ.",
        reply_markup=channels_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "channels_list")
async def channels_list(callback: CallbackQuery) -> None:
    channels = await list_channels()
    if not channels:
        await callback.message.edit_text("РљР°РЅР°Р»С‹ РїРѕРєР° РЅРµ РґРѕР±Р°РІР»РµРЅС‹.", reply_markup=channels_keyboard())
        await callback.answer()
        return

    rows = []
    for channel in channels:
        status = "рџџў" if channel.is_active else "рџ”ґ"
        title = channel.title or f"@{channel.username}"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{status} {title}",
                    callback_data=f"channels_view:{channel.id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="в¬…пёЏ РќР°Р·Р°Рґ", callback_data="channels")])

    await callback.message.edit_text(
        "рџ“‹ <b>РЎРїРёСЃРѕРє Telegram-РєР°РЅР°Р»РѕРІ</b>",
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
        "вћ• <b>Р”РѕР±Р°РІРёС‚СЊ Telegram-РєР°РЅР°Р»</b>\n\nРћС‚РїСЂР°РІСЊС‚Рµ username РєР°РЅР°Р»Р°. РњРѕР¶РЅРѕ СЃ СЃРёРјРІРѕР»РѕРј @.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="в¬…пёЏ РќР°Р·Р°Рґ", callback_data="channels")]]
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
    await message.answer(f"вњ… РљР°РЅР°Р» @{channel.username} РґРѕР±Р°РІР»РµРЅ.", reply_markup=channels_keyboard())


@router.callback_query(F.data.startswith("channels_toggle:"))
async def toggle_channel_callback(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.split(":", 1)[1])
    channel = await toggle_channel(channel_id)
    if not channel:
        await callback.answer("РљР°РЅР°Р» РЅРµ РЅР°Р№РґРµРЅ", show_alert=True)
        return

    status = "РІРєР»СЋС‡С‘РЅ" if channel.is_active else "РІС‹РєР»СЋС‡РµРЅ"
    await callback.answer(f"РљР°РЅР°Р» {status}", show_alert=True)
    await render_channel_card(callback, channel_id)


@router.callback_query(F.data.startswith("channels_scan:"))
async def scan_channel_callback(callback: CallbackQuery) -> None:
    channel_id = int(callback.data.split(":", 1)[1])
    await callback.message.edit_text(
        "рџ”„ РЎРєР°РЅРёСЂСѓСЋ РєР°РЅР°Р» С‡РµСЂРµР· Telethon...",
        reply_markup=channels_keyboard(),
    )
    result = await scan_channel(channel_id)

    if result.error:
        text = f"вљ пёЏ <b>РЎРєР°РЅРёСЂРѕРІР°РЅРёРµ РЅРµ РІС‹РїРѕР»РЅРµРЅРѕ</b>\n\n@{result.username}\nРћС€РёР±РєР°: {result.error}"
    else:
        text = (
            f"вњ… <b>РЎРєР°РЅРёСЂРѕРІР°РЅРёРµ Р·Р°РІРµСЂС€РµРЅРѕ</b>\n\n"
            f"РљР°РЅР°Р»: @{result.username}\n"
            f"РџСЂРѕРІРµСЂРµРЅРѕ СЃРѕРѕР±С‰РµРЅРёР№: {result.scanned_messages}\n"
            f"РЎРѕС…СЂР°РЅРµРЅРѕ РїСЂРѕРіРЅРѕР·РѕРІ: {result.saved_predictions}\n"
            f"Р”СѓР±Р»РёРєР°С‚РѕРІ РїСЂРѕРїСѓС‰РµРЅРѕ: {result.skipped_duplicates}"
        )

    await callback.message.edit_text(text, reply_markup=channels_keyboard())
    await callback.answer()


@router.callback_query(F.data == "channels_scan_all")
async def scan_all_channels_callback(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "рџ”„ РЎРєР°РЅРёСЂСѓСЋ Р°РєС‚РёРІРЅС‹Рµ РєР°РЅР°Р»С‹ С‡РµСЂРµР· Telethon...",
        reply_markup=channels_keyboard(),
    )
    results = await scan_all_channels()

    if not results:
        text = "РќРµС‚ Р°РєС‚РёРІРЅС‹С… РєР°РЅР°Р»РѕРІ РґР»СЏ СЃРєР°РЅРёСЂРѕРІР°РЅРёСЏ."
    else:
        lines = ["вњ… <b>РЎРєР°РЅРёСЂРѕРІР°РЅРёРµ Р·Р°РІРµСЂС€РµРЅРѕ</b>\n"]
        for result in results:
            if result.error:
                lines.append(f"@{result.username}: РѕС€РёР±РєР° - {result.error}")
            else:
                lines.append(
                    f"@{result.username}: {result.saved_predictions} РЅРѕРІС‹С…, "
                    f"{result.skipped_duplicates} РґСѓР±Р»РµР№, {result.scanned_messages} СЃРѕРѕР±С‰РµРЅРёР№"
                )
        text = "\n".join(lines)

    await callback.message.edit_text(text, reply_markup=channels_keyboard())
    await callback.answer()


@router.callback_query(F.data == "channels_stats")
async def channels_stats(callback: CallbackQuery) -> None:
    stats = await calculate_all_channels_stats()
    if not stats:
        await callback.message.edit_text("РЎС‚Р°С‚РёСЃС‚РёРєР° РїРѕРєР° РїСѓСЃС‚Р°СЏ.", reply_markup=channels_keyboard())
        await callback.answer()
        return

    lines = [
        "рџ“Љ <b>Р РµР№С‚РёРЅРі Telegram-РєР°РЅР°Р»РѕРІ</b>\n",
        "ROI СЃС‡РёС‚Р°РµС‚СЃСЏ РїРѕ flat stake 1 unit РЅР° РєР°Р¶РґС‹Р№ СЂР°СЃСЃС‡РёС‚Р°РЅРЅС‹Р№ РїСЂРѕРіРЅРѕР·.\n",
    ]
    for index, item in enumerate(stats, 1):
        lines.append(
            f"{index}. <b>@{item.username}</b> вЂ” {item.rating_grade} ({item.rating_score:.1f})\n"
            f"РџСЂРѕРіРЅРѕР·РѕРІ: {item.total_predictions}, СЂР°СЃСЃС‡РёС‚Р°РЅРѕ: {item.resolved_predictions}\n"
            f"Winrate: {format_percent(item.winrate)}, ROI: {format_percent(item.roi_flat)}\n"
            f"Avg РєСЌС„: {item.avg_odds:.2f}, pending: {item.pending_predictions}, "
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
