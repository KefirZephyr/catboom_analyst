from datetime import datetime, timedelta
from sqlalchemy import select, func, and_
from database.database import async_session
from database.models import Channel, Prediction


async def calculate_channel_stats(channel_id, days=None):
    """Расчет статистики канала за период"""
    async with async_session() as session:
        # Базовый запрос
        query = select(Prediction).where(Prediction.channel_id == channel_id)

        # Фильтр по периоду
        if days:
            start_date = datetime.utcnow() - timedelta(days=days)
            query = query.where(Prediction.created_at >= start_date)

        result = await session.execute(query)
        predictions = result.scalars().all()

        # Подсчет статистики
        total = len(predictions)
        wins = len([p for p in predictions if p.result == "win"])
        losses = len([p for p in predictions if p.result == "loss"])
        pending = len([p for p in predictions if p.result == "pending"])
        expired = len([p for p in predictions if p.result == "expired"])  # НОВОЕ

        # Статистика по методам определения результатов (НОВОЕ)
        auto_results = len(
            [p for p in predictions if p.result_method and "auto" in p.result_method]
        )
        manual_results = len(
            [p for p in predictions if p.result_method and "manual" in p.result_method]
        )

        # Процентные показатели
        if total == 0:
            return {
                "total": 0,
                "wins": 0,
                "losses": 0,
                "pending": 0,
                "expired": 0,  # НОВОЕ
                "win_rate": 0,
                "loss_rate": 0,
                "avg_odds": 0,
                "best_streak": 0,
                "auto_results_percent": 0,  # НОВОЕ
                "manual_results_percent": 0,  # НОВОЕ
            }

        win_rate = round((wins / total) * 100, 1)
        loss_rate = round((losses / total) * 100, 1)
        auto_results_percent = (
            round((auto_results / total) * 100, 1) if total > 0 else 0
        )
        manual_results_percent = (
            round((manual_results / total) * 100, 1) if total > 0 else 0
        )

        # Средний коэффициент
        odds_list = [p.odds for p in predictions if p.odds]
        avg_odds = round(sum(odds_list) / len(odds_list), 2) if odds_list else 0

        # Лучшая серия побед
        best_streak = calculate_best_winning_streak(predictions)

        return {
            "total": total,
            "wins": wins,
            "losses": losses,
            "pending": pending,
            "expired": expired,  # НОВОЕ
            "win_rate": win_rate,
            "loss_rate": loss_rate,
            "avg_odds": avg_odds,
            "best_streak": best_streak,
            "auto_results_percent": auto_results_percent,  # НОВОЕ
            "manual_results_percent": manual_results_percent,  # НОВОЕ
        }


async def calculate_all_stats(days=None):
    """Расчет общей статистики по всем каналам"""
    async with async_session() as session:
        # Получаем все активные каналы
        channels_result = await session.execute(
            select(Channel).where(Channel.is_active == True)
        )
        channels = channels_result.scalars().all()

        # Базовый запрос для всех прогнозов
        query = select(Prediction)
        if days:
            start_date = datetime.utcnow() - timedelta(days=days)
            query = query.where(Prediction.created_at >= start_date)

        result = await session.execute(query)
        all_predictions = result.scalars().all()

        # Общая статистика
        total_all = len(all_predictions)
        wins_all = len([p for p in all_predictions if p.result == "win"])
        losses_all = len([p for p in all_predictions if p.result == "loss"])
        pending_all = len([p for p in all_predictions if p.result == "pending"])
        expired_all = len(
            [p for p in all_predictions if p.result == "expired"]
        )  # НОВОЕ

        # Статистика автоматического определения (НОВОЕ)
        auto_determined = len(
            [
                p
                for p in all_predictions
                if p.result_method and "keyword" in p.result_method
            ]
        )
        auto_determined_percent = (
            round((auto_determined / total_all) * 100, 1) if total_all > 0 else 0
        )

        win_rate_all = round((wins_all / total_all) * 100, 1) if total_all > 0 else 0
        loss_rate_all = round((losses_all / total_all) * 100, 1) if total_all > 0 else 0

        # Находим лучший канал
        best_channel = "Нет данных"
        best_rate = 0

        # Находим канал с самым высоким процентом автоопределения (НОВОЕ)
        most_accurate_channel = "Нет данных"
        highest_auto_rate = 0

        for channel in channels:
            channel_stats = await calculate_channel_stats(channel.id, days)
            if channel_stats["total"] > 5 and channel_stats["win_rate"] > best_rate:
                best_rate = channel_stats["win_rate"]
                best_channel = f"{channel.name} ({best_rate}%)"

            # НОВОЕ: поиск канала с высоким процентом автоопределения
            if (
                channel_stats["total"] > 5
                and channel_stats["auto_results_percent"] > highest_auto_rate
            ):
                highest_auto_rate = channel_stats["auto_results_percent"]
                most_accurate_channel = f"{channel.name} ({highest_auto_rate}%)"

        return {
            "total_all": total_all,
            "wins_all": wins_all,
            "losses_all": losses_all,
            "pending_all": pending_all,
            "expired_all": expired_all,  # НОВОЕ
            "win_rate_all": win_rate_all,
            "loss_rate_all": loss_rate_all,
            "active_channels": len(channels),
            "best_channel": best_channel,
            "auto_determined": auto_determined_percent,  # НОВОЕ
            "most_accurate": most_accurate_channel,  # НОВОЕ
        }


def calculate_best_winning_streak(predictions):
    """Расчет лучшей серии побед"""
    if not predictions:
        return 0

    # Сортируем по дате
    sorted_predictions = sorted(predictions, key=lambda p: p.created_at)

    current_streak = 0
    best_streak = 0

    for prediction in sorted_predictions:
        if prediction.result == "win":
            current_streak += 1
            best_streak = max(best_streak, current_streak)
        elif prediction.result == "loss":  # Только поражения прерывают серию
            current_streak = 0

    return best_streak


async def get_channel_analytics(channel_id, days=None):
    """Получение детальной аналитики канала"""
    async with async_session() as session:
        # Получаем канал
        channel = await session.get(Channel, channel_id)
        if not channel:
            return None

        # Базовая статистика
        stats = await calculate_channel_stats(channel_id, days)

        # Дополнительные метрики
        query = select(Prediction).where(Prediction.channel_id == channel_id)
        if days:
            start_date = datetime.utcnow() - timedelta(days=days)
            query = query.where(Prediction.created_at >= start_date)

        result = await session.execute(query)
        predictions = result.scalars().all()

        # Анализ по коэффициентам
        low_odds = [p for p in predictions if p.odds and p.odds < 2.0]
        high_odds = [p for p in predictions if p.odds and p.odds >= 2.0]

        low_odds_win_rate = 0
        high_odds_win_rate = 0

        if low_odds:
            low_wins = len([p for p in low_odds if p.result == "win"])
            low_odds_win_rate = round((low_wins / len(low_odds)) * 100, 1)

        if high_odds:
            high_wins = len([p for p in high_odds if p.result == "win"])
            high_odds_win_rate = round((high_wins / len(high_odds)) * 100, 1)

        # НОВОЕ: анализ качества автоопределения
        auto_predictions = [
            p for p in predictions if p.result_method and "keyword" in p.result_method
        ]
        avg_confidence = 0
        if auto_predictions:
            confidences = [
                p.result_confidence for p in auto_predictions if p.result_confidence
            ]
            avg_confidence = (
                round(sum(confidences) / len(confidences), 2) if confidences else 0
            )

        return {
            **stats,
            "channel_name": channel.name,
            "low_odds_count": len(low_odds),
            "low_odds_win_rate": low_odds_win_rate,
            "high_odds_count": len(high_odds),
            "high_odds_win_rate": high_odds_win_rate,
            "last_prediction_date": max([p.created_at for p in predictions]).strftime(
                "%d.%m.%Y"
            )
            if predictions
            else None,
            "avg_auto_confidence": avg_confidence,  # НОВОЕ
            "auto_predictions_count": len(auto_predictions),  # НОВОЕ
        }


async def export_channel_data(channel_id, days=None):
    """Экспорт данных канала в CSV формат"""
    async with async_session() as session:
        # Получаем канал
        channel = await session.get(Channel, channel_id)
        if not channel:
            return None

        # Получаем прогнозы
        query = select(Prediction).where(Prediction.channel_id == channel_id)
        if days:
            start_date = datetime.utcnow() - timedelta(days=days)
            query = query.where(Prediction.created_at >= start_date)

        result = await session.execute(query.order_by(Prediction.created_at.desc()))
        predictions = result.scalars().all()

        # Формируем CSV данные с новыми полями
        csv_data = "Дата,Содержание,Коэффициент,Результат,Уверенность,Метод,Обновлено\n"

        for prediction in predictions:
            date_str = prediction.created_at.strftime("%d.%m.%Y %H:%M")
            content = prediction.content.replace("\n", " ").replace(",", ";")[:100]
            odds = prediction.odds or "Не указан"
            result = {
                "win": "Победа",
                "loss": "Поражение",
                "pending": "Ожидание",
                "expired": "Устарело",  # НОВОЕ
            }.get(prediction.result, prediction.result)

            confidence = (
                f"{prediction.result_confidence:.2f}"
                if prediction.result_confidence
                else "Не указана"
            )
            method = prediction.result_method or "Не указан"
            updated = (
                prediction.result_updated_at.strftime("%d.%m.%Y")
                if prediction.result_updated_at
                else "Нет"
            )

            csv_data += f'"{date_str}","{content}","{odds}","{result}","{confidence}","{method}","{updated}"\n'

        return csv_data


# НОВОЕ: функция для анализа эффективности автоопределения
async def get_auto_detection_stats(days=30):
    """Статистика эффективности автоматического определения результатов"""
    async with async_session() as session:
        # Получаем прогнозы за указанный период
        start_date = datetime.utcnow() - timedelta(days=days)

        result = await session.execute(
            select(Prediction).where(Prediction.created_at >= start_date)
        )
        predictions = result.scalars().all()

        total_predictions = len(predictions)
        auto_determined = len(
            [p for p in predictions if p.result_method and "keyword" in p.result_method]
        )
        manual_determined = len(
            [p for p in predictions if p.result_method and "manual" in p.result_method]
        )
        pending = len([p for p in predictions if p.result == "pending"])
        expired = len([p for p in predictions if p.result == "expired"])

        # Средняя уверенность автоопределения
        auto_predictions = [
            p for p in predictions if p.result_confidence and p.result_confidence > 0
        ]
        avg_confidence = 0
        if auto_predictions:
            avg_confidence = round(
                sum(p.result_confidence for p in auto_predictions)
                / len(auto_predictions),
                2,
            )

        return {
            "total_predictions": total_predictions,
            "auto_determined": auto_determined,
            "auto_percentage": round((auto_determined / total_predictions) * 100, 1)
            if total_predictions > 0
            else 0,
            "manual_determined": manual_determined,
            "pending": pending,
            "expired": expired,
            "avg_confidence": avg_confidence,
            "efficiency": round(
                (auto_determined / (auto_determined + manual_determined)) * 100, 1
            )
            if (auto_determined + manual_determined) > 0
            else 0,
        }
