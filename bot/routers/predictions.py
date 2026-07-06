from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from bot.routers.matches import hydrate_match
from db.models import DotaMatch, Team
from db.session import async_session
from modules.analytics.match_analytics import predict_match_winner

router = Router()


def predictions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔮 Выбрать будущий матч", callback_data="predictions_matches")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
        ]
    )


@router.callback_query(F.data == "predictions")
async def predictions_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "🔮 <b>Прогноз победителя</b>\n\n"
        "Оценка строится по форме команд, результатам в турнире, очным встречам и силе расписания. "
        "Это аналитическая модель MVP, а не гарантия результата.",
        reply_markup=predictions_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "predictions_matches")
async def prediction_matches(callback: CallbackQuery) -> None:
    async with async_session() as session:
        result = await session.execute(
            select(DotaMatch)
            .where(DotaMatch.status == "scheduled", DotaMatch.team_a_id.is_not(None), DotaMatch.team_b_id.is_not(None))
            .order_by(DotaMatch.starts_at.is_(None), DotaMatch.starts_at)
            .limit(20)
        )
        matches = list(result.scalars().all())
        rows = []
        for match in matches:
            row = await hydrate_match(session, match)
            team_a = row[1].name if row[1] else "TBD"
            team_b = row[2].name if row[2] else "TBD"
            rows.append([InlineKeyboardButton(text=f"{team_a} vs {team_b}"[:60], callback_data=f"prediction_view:{match.id}")])

    if not rows:
        await callback.message.edit_text("Будущие матчи с двумя командами пока не найдены.", reply_markup=predictions_keyboard())
        await callback.answer()
        return

    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="predictions")])
    await callback.message.edit_text("🔮 <b>Выберите матч</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.startswith("prediction_view:"))
async def prediction_view(callback: CallbackQuery) -> None:
    match_id = int(callback.data.split(":", 1)[1])
    prediction = await predict_match_winner(match_id)
    if not prediction:
        await callback.answer("Недостаточно данных для прогноза", show_alert=True)
        return

    async with async_session() as session:
        match = await session.get(DotaMatch, match_id)
        team_a = await session.get(Team, match.team_a_id) if match and match.team_a_id else None
        team_b = await session.get(Team, match.team_b_id) if match and match.team_b_id else None
        predicted = await session.get(Team, prediction.predicted_team_id) if prediction.predicted_team_id else None

    text = (
        f"🔮 <b>{team_a.name if team_a else 'TBD'} vs {team_b.name if team_b else 'TBD'}</b>\n\n"
        f"Вероятность {team_a.name if team_a else 'Команда A'}: {prediction.team_a_probability:.1f}%\n"
        f"Вероятность {team_b.name if team_b else 'Команда B'}: {prediction.team_b_probability:.1f}%\n"
        f"Предполагаемый победитель: {predicted.name if predicted else 'нет данных'}\n"
        f"Уверенность модели: {prediction.confidence:.1f}%\n\n"
        f"<b>Факторы</b>\n{prediction.explanation}"
    )
    await callback.message.edit_text(text, reply_markup=predictions_keyboard())
    await callback.answer()
