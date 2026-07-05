from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from db.models import TelegramChannel, TelegramPrediction
from db.session import async_session
from modules.telegram_parser.result_matcher import (
    PredictionMatchResult,
    apply_prediction_match,
    find_match_candidates,
)

router = Router()


def signals_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📌 Прогнозы на проверку", callback_data="review_predictions")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
        ]
    )


@router.callback_query(F.data == "signals")
async def signals_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "🎯 <b>Сигналы</b>\n\n"
        "Value-сигналы будут формироваться только как рекомендации. "
        "Автоставки не реализуются.",
        reply_markup=signals_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "review_predictions")
async def review_predictions(callback: CallbackQuery) -> None:
    prediction = await load_next_review_prediction()
    if not prediction:
        await callback.message.edit_text(
            "📌 <b>Прогнозы на проверку</b>\n\nНет прогнозов, ожидающих ручной проверки.",
            reply_markup=signals_keyboard(),
        )
        await callback.answer()
        return

    await render_prediction_review(callback, prediction)
    await callback.answer()


@router.callback_query(F.data.startswith("review_open:"))
async def review_open(callback: CallbackQuery) -> None:
    prediction_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        prediction = await session.get(TelegramPrediction, prediction_id)

    if not prediction:
        await callback.answer("Прогноз не найден", show_alert=True)
        return

    await render_prediction_review(callback, prediction)
    await callback.answer()


@router.callback_query(F.data.startswith("review_bind:"))
async def review_bind(callback: CallbackQuery) -> None:
    _, prediction_id_raw, match_id_raw, picked_team_id_raw, confidence_raw = callback.data.split(":")
    prediction_id = int(prediction_id_raw)
    match_id = int(match_id_raw)
    picked_team_id = int(picked_team_id_raw) if picked_team_id_raw != "0" else None
    confidence = float(confidence_raw)

    result = PredictionMatchResult(
        match_id=match_id,
        picked_team_id=picked_team_id,
        confidence=confidence,
        reason="Ручная привязка через Telegram-интерфейс",
    )
    await apply_prediction_match(prediction_id, result)
    await callback.answer("Прогноз привязан к матчу", show_alert=True)
    await review_predictions(callback)


@router.callback_query(F.data.startswith("review_skip:"))
async def review_skip(callback: CallbackQuery) -> None:
    prediction_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        prediction = await session.get(TelegramPrediction, prediction_id)
        if prediction:
            prediction.needs_review = False
            prediction.status = "review_skipped"
            prediction.match_reason = "Ручная проверка пропущена"
            await session.commit()

    await callback.answer("Прогноз пропущен", show_alert=True)
    await review_predictions(callback)


async def load_next_review_prediction() -> TelegramPrediction | None:
    async with async_session() as session:
        result = await session.execute(
            select(TelegramPrediction)
            .where(TelegramPrediction.needs_review == True)
            .order_by(TelegramPrediction.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def render_prediction_review(callback: CallbackQuery, prediction: TelegramPrediction) -> None:
    async with async_session() as session:
        channel = await session.get(TelegramChannel, prediction.channel_id)

    candidates = await find_match_candidates(prediction, limit=4)
    channel_name = f"@{channel.username}" if channel else "канал неизвестен"
    odds = prediction.odds_value if prediction.odds_value is not None else "не найден"
    market = prediction.market_type or "не определён"

    text = (
        "📌 <b>Прогноз на проверку</b>\n\n"
        f"Канал: {channel_name}\n"
        f"Коэффициент: {odds}\n"
        f"Рынок: {market}\n"
        f"Match confidence: {prediction.match_confidence:.2f}\n\n"
        f"<b>Текст прогноза:</b>\n{prediction.raw_text[:900]}\n\n"
        "<b>Кандидаты:</b>\n"
    )
    if candidates:
        text += "\n".join(
            f"• {candidate.title} ({candidate.confidence:.2f})" for candidate in candidates
        )
    else:
        text += "Кандидаты не найдены."

    rows = []
    for candidate in candidates:
        picked_team_id = candidate.picked_team_id or 0
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"✅ Привязать: {candidate.title[:40]}",
                    callback_data=(
                        f"review_bind:{prediction.id}:{candidate.match_id}:"
                        f"{picked_team_id}:{candidate.confidence}"
                    ),
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="❌ Пропустить", callback_data=f"review_skip:{prediction.id}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="signals")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
