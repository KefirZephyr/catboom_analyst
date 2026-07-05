from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select, func
from datetime import datetime, timedelta
from config.texts import (
    STATS_MENU_TEXT,
    CHANNEL_STATS_TEXT,
    ALL_STATS_TEXT,
    COMPARE_CHANNELS_TEXT,
    ERROR_MESSAGES,
)
from keyboards.inline_keyboards import (
    stats_menu_keyboard,
    back_to_main_keyboard,
    channel_select_keyboard,
)
from database.database import async_session
from database.models import Channel, Prediction
from utils.analytics import calculate_channel_stats, calculate_all_stats

router = Router()


@router.callback_query(F.data == "statistics")
async def statistics_menu(callback: CallbackQuery):
    """Меню статистики"""
    await callback.message.edit_text(
        text=STATS_MENU_TEXT, reply_markup=stats_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("stats_"))
async def show_statistics(callback: CallbackQuery):
    """Показ общей статистики"""
    period_map = {
        "stats_7": 7,
        "stats_30": 30,
        "stats_90": 90,
        "stats_all": None,
        "stats_summary": None,
    }

    action = callback.data
    if action == "stats_compare":
        await show_channels_comparison(callback)
        return

    days = period_map.get(action)

    if action == "stats_summary":
        # Общая статистика по всем каналам
        stats = await calculate_all_stats(days)
        period_text = f"{days} дней" if days else "все время"

        text = ALL_STATS_TEXT.format(
            period=period_text,
            total_all=stats["total_all"],
            wins_all=stats["wins_all"],
            win_rate_all=stats["win_rate_all"],
            losses_all=stats["losses_all"],
            loss_rate_all=stats["loss_rate_all"],
            pending_all=stats.get("pending_all", 0),
            expired_all=stats.get("expired_all", 0),
            active_channels=stats["active_channels"],
            best_channel=stats["best_channel"],
            auto_determined=stats.get("auto_determined", 0),
        )
    else:
        # Статистика по каждому каналу
        period_text = f"{days} дней" if days else "все время"

        async with async_session() as session:
            result = await session.execute(
                select(Channel).where(Channel.is_active == True)
            )
            channels = result.scalars().all()

            if not channels:
                text = ERROR_MESSAGES["no_data"]
            else:
                text = f"📊 <b>Статистика за {period_text}</b>\n\n"

                for channel in channels:
                    stats = await calculate_channel_stats(channel.id, days)

                    if stats["total"] > 0:
                        text += f"📺 <b>{channel.name}</b>\n"
                        text += f"  • Прогнозов: {stats['total']}\n"
                        text += f"  • Побед: {stats['wins']} ({stats['win_rate']}%)\n"
                        text += f"  • Поражений: {stats['losses']} ({stats['loss_rate']}%)\n"
                        text += f"  • Ср. коэф: {stats['avg_odds']}\n\n"

    await callback.message.edit_text(text=text, reply_markup=back_to_main_keyboard())
    await callback.answer()


async def show_channels_comparison(callback: CallbackQuery):
    """Сравнение каналов"""
    async with async_session() as session:
        result = await session.execute(select(Channel).where(Channel.is_active == True))
        channels = result.scalars().all()

        if len(channels) < 2:
            await callback.message.edit_text(
                text="❌ Для сравнения нужно минимум 2 активных канала",
                reply_markup=back_to_main_keyboard(),
            )
            await callback.answer()
            return

        comparison_data = []
        best_channel = ""
        best_rate = 0
        most_accurate = ""
        highest_auto_rate = 0

        for channel in channels:
            stats = await calculate_channel_stats(channel.id, 30)  # За 30 дней
            if stats["total"] > 0:
                comparison_data.append(
                    {
                        "name": channel.name,
                        "win_rate": stats["win_rate"],
                        "total": stats["total"],
                        "avg_odds": stats["avg_odds"],
                        "auto_rate": stats.get("auto_results_percent", 0),
                    }
                )

                if stats["win_rate"] > best_rate:
                    best_rate = stats["win_rate"]
                    best_channel = channel.name

                if stats.get("auto_results_percent", 0) > highest_auto_rate:
                    highest_auto_rate = stats.get("auto_results_percent", 0)
                    most_accurate = channel.name

        # Сортируем по проценту побед
        comparison_data.sort(key=lambda x: x["win_rate"], reverse=True)

        channels_comparison = ""
        for i, data in enumerate(comparison_data, 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            channels_comparison += f"{emoji} <b>{data['name']}</b>\n"
            channels_comparison += (
                f"   📊 {data['win_rate']}% побед ({data['total']} прогнозов)\n"
            )
            channels_comparison += f"   💰 Ср. коэф: {data['avg_odds']}\n"
            channels_comparison += f"   🤖 Авто: {data['auto_rate']}%\n\n"

        text = COMPARE_CHANNELS_TEXT.format(
            period="30 дней",
            channels_comparison=channels_comparison,
            best_channel=best_channel,
            best_rate=best_rate,
            most_accurate=most_accurate,
            auto_rate=highest_auto_rate,
        )

        await callback.message.edit_text(
            text=text, reply_markup=back_to_main_keyboard()
        )
        await callback.answer()


@router.callback_query(F.data.regexp(r"^channel_stats_\d+_\w+$"))
async def show_channel_statistics(callback: CallbackQuery):
    """Статистика конкретного канала"""
    # Парсим channel_stats_ID_PERIOD
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer("Ошибка в данных", show_alert=True)
        return

    try:
        channel_id = int(parts[2])
        period = parts[3]
    except (ValueError, IndexError):
        await callback.answer("Ошибка в данных", show_alert=True)
        return

    period_map = {"7": 7, "30": 30, "90": 90, "all": None}

    days = period_map.get(period)
    period_text = f"{days} дней" if days else "все время"

    async with async_session() as session:
        channel = await session.get(Channel, channel_id)
        if not channel:
            await callback.answer("Канал не найден", show_alert=True)
            return

    stats = await calculate_channel_stats(channel_id, days)

    text = CHANNEL_STATS_TEXT.format(
        name=channel.name,
        period=period_text,
        total_predictions=stats["total"],
        wins=stats["wins"],
        win_rate=stats["win_rate"],
        losses=stats["losses"],
        loss_rate=stats["loss_rate"],
        pending=stats.get("pending", 0),
        expired=stats.get("expired", 0),
        avg_odds=stats["avg_odds"],
        best_streak=stats.get("best_streak", 0),
        auto_results=stats.get("auto_results_percent", 0),
        manual_results=stats.get("manual_results_percent", 0),
    )

    await callback.message.edit_text(text=text, reply_markup=back_to_main_keyboard())
    await callback.answer()
