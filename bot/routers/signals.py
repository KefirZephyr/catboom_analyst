from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from db.models import BetOrder, DotaMatch, Signal, Team, TelegramChannel, TelegramPrediction
from db.session import async_session
from modules.bankroll.bankroll_manager import check_daily_risk_limit, check_max_open_bets
from modules.recommendations.signal_generator import generate_signals_for_ready_predictions
from modules.telegram_parser.result_matcher import (
    PredictionMatchResult,
    apply_prediction_match,
    find_match_candidates,
)

router = Router()


class SignalStates(StatesGroup):
    waiting_for_stake = State()


def signals_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Список сигналов", callback_data="signals_list")],
            [InlineKeyboardButton(text="🔄 Сгенерировать сигналы", callback_data="signals_generate")],
            [InlineKeyboardButton(text="📌 Прогнозы на проверку", callback_data="review_predictions")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
        ]
    )


@router.callback_query(F.data == "signals")
async def signals_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "🎯 <b>Сигналы</b>\n\n"
        "Сигналы являются аналитическими рекомендациями. Бот не делает автоставки "
        "и не гарантирует прибыль.",
        reply_markup=signals_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "signals_generate")
async def signals_generate(callback: CallbackQuery) -> None:
    await callback.message.edit_text("🔄 Генерирую value-сигналы...", reply_markup=signals_keyboard())
    results = await generate_signals_for_ready_predictions(user_id=callback.from_user.id)
    created = len([item for item in results if item.signal])
    skipped = len(results) - created
    await callback.message.edit_text(
        f"✅ Генерация завершена.\n\nСоздано сигналов: {created}\nПропущено: {skipped}",
        reply_markup=signals_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "signals_list")
async def signals_list(callback: CallbackQuery) -> None:
    async with async_session() as session:
        result = await session.execute(
            select(Signal).where(Signal.status == "new").order_by(Signal.created_at.desc()).limit(10)
        )
        signals = result.scalars().all()

    if not signals:
        await callback.message.edit_text(
            "🎯 <b>Сигналы</b>\n\nАктивных сигналов пока нет.",
            reply_markup=signals_keyboard(),
        )
        await callback.answer()
        return

    rows = []
    for signal in signals:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{signal.selection} · edge {signal.edge_percent:+.1f}%",
                    callback_data=f"signal_view:{signal.id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="signals")])
    await callback.message.edit_text(
        "🎯 <b>Активные сигналы</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("signal_view:"))
async def signal_view(callback: CallbackQuery) -> None:
    signal_id = int(callback.data.split(":", 1)[1])
    text = await format_signal_card(signal_id)
    if not text:
        await callback.answer("Сигнал не найден", show_alert=True)
        return

    await callback.message.edit_text(text, reply_markup=signal_actions_keyboard(signal_id))
    await callback.answer()


@router.callback_query(F.data.startswith("signal_accept:"))
async def signal_accept(callback: CallbackQuery) -> None:
    signal_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        signal = await session.get(Signal, signal_id)
        if not signal:
            await callback.answer("Сигнал не найден", show_alert=True)
            return

        daily_ok, _, _ = await check_daily_risk_limit(callback.from_user.id, signal.recommended_stake)
        open_ok, _, _ = await check_max_open_bets(callback.from_user.id)
        if not daily_ok or not open_ok:
            await callback.answer("Лимиты банка не позволяют принять ставку", show_alert=True)
            return

        order = BetOrder(
            user_id=callback.from_user.id,
            signal_id=signal.id,
            stake=signal.recommended_stake,
            odds_value=signal.odds_value or 0,
            status="accepted_manually",
        )
        signal.status = "accepted_manually"
        session.add(order)
        await session.commit()

    await callback.answer("Ставка отмечена как принятая вручную", show_alert=True)
    await signals_list(callback)


@router.callback_query(F.data.startswith("signal_edit_stake:"))
async def signal_edit_stake(callback: CallbackQuery, state: FSMContext) -> None:
    signal_id = int(callback.data.split(":", 1)[1])
    await state.update_data(signal_id=signal_id)
    await state.set_state(SignalStates.waiting_for_stake)
    await callback.message.edit_text(
        "✏️ Введите новую сумму ставки числом.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data=f"signal_view:{signal_id}")]]
        ),
    )
    await callback.answer()


@router.message(SignalStates.waiting_for_stake)
async def signal_edit_stake_finish(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    signal_id = int(data["signal_id"])
    try:
        stake = float((message.text or "").replace(",", ".").replace(" ", ""))
    except ValueError:
        await message.answer("Введите сумму числом.")
        return

    if stake <= 0:
        await message.answer("Сумма должна быть больше нуля.")
        return

    async with async_session() as session:
        signal = await session.get(Signal, signal_id)
        if signal:
            signal.recommended_stake = stake
            await session.commit()

    await state.clear()
    text = await format_signal_card(signal_id)
    await message.answer(text or "Сигнал обновлён.", reply_markup=signal_actions_keyboard(signal_id))


@router.callback_query(F.data.startswith("signal_skip:"))
async def signal_skip(callback: CallbackQuery) -> None:
    signal_id = int(callback.data.split(":", 1)[1])
    async with async_session() as session:
        signal = await session.get(Signal, signal_id)
        if signal:
            signal.status = "skipped"
            await session.commit()
    await callback.answer("Сигнал пропущен", show_alert=True)
    await signals_list(callback)


def signal_actions_keyboard(signal_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Принял ставку вручную",
                    callback_data=f"signal_accept:{signal_id}",
                )
            ],
            [InlineKeyboardButton(text="✏️ Изменить сумму", callback_data=f"signal_edit_stake:{signal_id}")],
            [InlineKeyboardButton(text="❌ Пропустить", callback_data=f"signal_skip:{signal_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="signals_list")],
        ]
    )


async def format_signal_card(signal_id: int) -> str | None:
    async with async_session() as session:
        signal = await session.get(Signal, signal_id)
        if not signal:
            return None
        match = await session.get(DotaMatch, signal.match_id) if signal.match_id else None
        picked_team = await session.get(Team, signal.picked_team_id) if signal.picked_team_id else None
        team_a = await session.get(Team, match.team_a_id) if match and match.team_a_id else None
        team_b = await session.get(Team, match.team_b_id) if match and match.team_b_id else None

    match_title = (
        f"{team_a.name if team_a else 'TBD'} vs {team_b.name if team_b else 'TBD'}"
        if match
        else "Матч не указан"
    )
    pick = picked_team.name if picked_team else signal.selection
    market = "победа команды" if signal.market_type == "match_winner" else "тотал карт"
    risk = {"low": "низкий", "medium": "средний", "high": "высокий"}.get(
        signal.risk_level,
        signal.risk_level,
    )

    return (
        "🎯 <b>Сигнал найден</b>\n\n"
        f"Матч: {match_title}\n"
        f"Рынок: {market}\n"
        f"Пик: {pick}\n"
        f"Коэф: {signal.odds_value or 0:.2f}\n\n"
        f"Вероятность модели: {signal.model_probability_percent:.1f}%\n"
        f"Вероятность букмекера: {signal.bookmaker_probability_percent:.1f}%\n"
        f"Edge: {signal.edge_percent:+.1f}%\n"
        f"Confidence: {signal.confidence_percent:.1f}%\n"
        f"Риск: {risk}\n\n"
        f"Рекомендовано: {signal.stake_percent:.2f}% = {signal.recommended_stake:.2f} RUB\n\n"
        "Это аналитическая рекомендация, не гарантия прибыли."
    )


# --- Manual prediction review ---


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
    text += "\n".join(
        f"• {candidate.title} ({candidate.confidence:.2f})" for candidate in candidates
    ) if candidates else "Кандидаты не найдены."

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
