from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from bot.routers.matches import format_moscow_time, hydrate_match
from db.models import DotaMatch, Team
from db.session import async_session
from modules.analytics.match_analytics import MatchPrediction, predict_match_winner

router = Router()


def predictions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔮 Ближайшие матчи с прогнозом", callback_data="predictions_matches")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
        ]
    )


@router.callback_query(F.data == "predictions")
async def predictions_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "🔮 <b>Прогноз победителя</b>\n\n"
        "Модель оценивает ближайшие матчи по форме команд, результатам в турнире, очным встречам "
        "и силе последних соперников. Если данных мало, уверенность будет низкой.",
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
            .limit(8)
        )
        matches = list(result.scalars().all())
        rows = []
        lines = ["🔮 <b>Ближайшие матчи</b>"]

        for match in matches:
            hydrated = await hydrate_match(session, match)
            team_a = hydrated[1].name if hydrated[1] else "TBD"
            team_b = hydrated[2].name if hydrated[2] else "TBD"
            prediction = await predict_match_winner(match.id)
            lines.append(format_prediction_preview(match, team_a, team_b, prediction))
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"Подробнее: {team_a} vs {team_b}"[:60],
                        callback_data=f"prediction_view:{match.id}",
                    )
                ]
            )

    if not rows:
        await callback.message.edit_text(
            "Будущие матчи с двумя командами пока не найдены.",
            reply_markup=predictions_keyboard(),
        )
        await callback.answer()
        return

    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="predictions")])
    await callback.message.edit_text("\n\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
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

    team_a_name = team_a.name if team_a else "Команда A"
    team_b_name = team_b.name if team_b else "Команда B"
    text = (
        f"🔮 <b>{team_a_name} vs {team_b_name}</b>\n\n"
        f"Время: {format_moscow_time(match.starts_at if match else None)}\n"
        f"Вероятность {team_a_name}: {prediction.team_a_probability:.1f}%\n"
        f"Вероятность {team_b_name}: {prediction.team_b_probability:.1f}%\n"
        f"Прогноз: {predicted.name if predicted else 'нет данных'}\n"
        f"Уверенность: {prediction.confidence_label} ({prediction.confidence:.1f}%)\n\n"
        f"<b>Факторы</b>\n{format_factors(prediction)}"
    )
    await callback.message.edit_text(text, reply_markup=predictions_keyboard())
    await callback.answer()


def format_prediction_preview(
    match: DotaMatch,
    team_a_name: str,
    team_b_name: str,
    prediction: MatchPrediction | None,
) -> str:
    if not prediction:
        return (
            f"🎮 <b>{team_a_name} vs {team_b_name}</b>\n"
            f"Время: {format_moscow_time(match.starts_at)}\n"
            "Прогноз: недостаточно данных"
        )

    picked = team_a_name if prediction.predicted_team_id == match.team_a_id else team_b_name
    return (
        f"🎮 <b>{team_a_name} vs {team_b_name}</b>\n"
        f"Время: {format_moscow_time(match.starts_at)}\n"
        f"Прогноз: {picked}\n"
        f"Вероятности: {prediction.team_a_probability:.1f}% / {prediction.team_b_probability:.1f}%\n"
        f"Уверенность: {prediction.confidence_label}"
    )


def format_factors(prediction: MatchPrediction) -> str:
    if not prediction.factors:
        return "Недостаточно истории матчей для подробного объяснения."
    return "\n".join(f"• {factor}" for factor in prediction.factors)
