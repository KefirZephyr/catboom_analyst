import asyncio
import re
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple
from telethon import TelegramClient
from telethon.errors import ChannelPrivateError, UsernameNotOccupiedError
from sqlalchemy import select, update
from config.settings import (
    API_ID,
    API_HASH,
    PARSING_KEYWORDS,
    MONITORING_INTERVAL,
    MAX_MESSAGES_CHECK,
    RESULT_WIN_KEYWORDS,
    RESULT_LOSS_KEYWORDS,
    RESULTS_UPDATE_INTERVAL,
    RESULTS_SEARCH_HOURS,
    EXPIRED_DAYS,
    MIN_COMMON_WORDS,
    CONFIDENCE_THRESHOLD,
    HISTORY_SCAN_ENABLED,
    DEFAULT_HISTORY_DAYS,
    MAX_HISTORY_DAYS,
    HISTORY_SCAN_DELAY,
    AUTO_SCAN_ON_ADD,
)
from config.texts import NEW_PREDICTION_TEXT, RESULT_UPDATE_TEXT
from database.database import async_session, DatabaseManager
from database.models import Channel, Prediction, User, ResultUpdate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ИСПРАВЛЕНО: Уникальное имя сессии для избежания конфликтов
session_name = f"catboom_session_{uuid.uuid4().hex[:8]}"
client = TelegramClient(session_name, API_ID, API_HASH)

# Глобальная переменная для graceful shutdown
shutdown_event = asyncio.Event()


def get_utc_now():
    """Получение UTC времени с timezone"""
    return datetime.now(timezone.utc)


def get_naive_utc_now():
    """Получение UTC времени без timezone для совместимости с БД"""
    return datetime.utcnow()


def make_timezone_aware(dt):
    """Преобразование naive datetime в timezone-aware"""
    if dt is None:
        return get_utc_now()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def make_timezone_naive(dt):
    """Преобразование timezone-aware datetime в naive"""
    if dt is None:
        return get_naive_utc_now()
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


async def start_channel_monitoring(bot):
    """Запуск мониторинга каналов"""
    logger.info("🚀 Запуск мониторинга каналов...")

    try:
        await client.start()
        logger.info("✅ Telethon клиент запущен")
    except Exception as e:
        logger.error(f"❌ Ошибка запуска Telethon: {e}")
        return

    # Запуск задач с задержкой для избежания конфликтов
    monitoring_task = asyncio.create_task(monitor_channels_loop(bot))
    await asyncio.sleep(60)  # Задержка перед запуском обновления результатов
    results_task = asyncio.create_task(update_results_loop(bot))

    # Ждем завершения задач или сигнала остановки
    try:
        await shutdown_event.wait()
    except asyncio.CancelledError:
        pass
    finally:
        monitoring_task.cancel()
        results_task.cancel()
        await asyncio.gather(monitoring_task, results_task, return_exceptions=True)
        await client.disconnect()


async def monitor_channels_loop(bot):
    """Основной цикл мониторинга каналов"""
    retry_count = 0
    max_retries = 5

    while not shutdown_event.is_set():
        try:
            # ИСПРАВЛЕНО: Безопасное получение каналов с retry-логикой
            async def get_active_channels(session):
                result = await session.execute(
                    select(Channel).where(Channel.is_active == True)
                )
                return result.scalars().all()

            channels = await DatabaseManager.safe_execute(get_active_channels)

            if not channels:
                logger.info("📺 Нет активных каналов для мониторинга")
                await asyncio.sleep(MONITORING_INTERVAL)
                continue

            logger.info(f"📺 Проверяем {len(channels)} каналов")

            for channel in channels:
                if shutdown_event.is_set():
                    break

                try:
                    await monitor_channel_safe(bot, channel)
                    await asyncio.sleep(10)  # Увеличенная пауза между каналами
                except Exception as e:
                    logger.error(
                        f"❌ Ошибка мониторинга канала {channel.username}: {e}"
                    )

            # Обновляем время последней проверки
            async def update_last_checked(session):
                for channel in channels:
                    channel.last_checked = get_naive_utc_now()
                return True

            await DatabaseManager.safe_execute(update_last_checked)

            retry_count = 0  # Сбрасываем счетчик при успешном выполнении
            logger.info(
                f"⏰ Ожидание {MONITORING_INTERVAL} секунд до следующей проверки"
            )
            await asyncio.sleep(MONITORING_INTERVAL)

        except Exception as e:
            retry_count += 1
            logger.error(
                f"❌ Ошибка мониторинга (попытка {retry_count}/{max_retries}): {e}"
            )

            if retry_count >= max_retries:
                logger.error(
                    "❌ Превышено максимальное количество попыток, останавливаем мониторинг"
                )
                break

            # Экспоненциальная задержка при ошибках
            delay = min(300, 30 * (2**retry_count))  # Максимум 5 минут
            await asyncio.sleep(delay)


async def monitor_channel_safe(bot, channel):
    """Безопасный мониторинг отдельного канала"""
    try:
        # Получаем сущность канала
        try:
            entity = await client.get_entity(channel.username)
        except (ChannelPrivateError, UsernameNotOccupiedError) as e:
            logger.warning(f"⚠️ Канал {channel.username} недоступен: {e}")
            return
        except Exception as e:
            logger.error(f"❌ Не удалось получить канал {channel.username}: {e}")
            return

        # Получаем сообщения с обработкой ошибок
        try:
            messages = await client.get_messages(entity, limit=MAX_MESSAGES_CHECK)
        except Exception as e:
            logger.error(f"❌ Не удалось получить сообщения из {channel.username}: {e}")
            return

        logger.info(f"📨 Проверяем {len(messages)} сообщений из {channel.username}")

        new_predictions = []

        for message in messages:
            if not message or not message.text:
                continue

            try:
                if await is_prediction(message.text):
                    # Проверяем существование в БД
                    async def check_existing(session):
                        result = await session.execute(
                            select(Prediction).where(
                                Prediction.message_id == message.id,
                                Prediction.channel_id == channel.id,
                            )
                        )
                        return result.scalar_one_or_none()

                    existing = await DatabaseManager.safe_execute(check_existing)

                    if not existing:
                        odds = extract_odds(message.text)
                        telegram_date_naive = make_timezone_naive(message.date)

                        prediction_data = {
                            "channel_id": channel.id,
                            "content": message.text[:2000],  # Ограничиваем длину
                            "odds": odds,
                            "result": "pending",
                            "message_id": message.id,
                            "telegram_date": telegram_date_naive,
                        }

                        new_predictions.append((prediction_data, message))
            except Exception as e:
                logger.error(f"❌ Ошибка обработки сообщения {message.id}: {e}")
                continue

        # Сохраняем новые прогнозы
        if new_predictions:

            async def save_predictions(session):
                saved_count = 0
                for pred_data, message in new_predictions:
                    try:
                        prediction = Prediction(**pred_data)
                        session.add(prediction)
                        saved_count += 1
                    except Exception as e:
                        logger.error(f"❌ Ошибка создания прогноза: {e}")
                        continue

                # Обновляем счетчик канала
                if saved_count > 0:
                    channel.predictions_count += saved_count

                return saved_count

            count = await DatabaseManager.safe_execute(save_predictions)

            # Отправляем уведомления
            if count > 0:
                for pred_data, message in new_predictions[:count]:  # Только сохраненные
                    try:
                        await send_notifications(
                            bot, channel, message.text, pred_data["odds"], message.date
                        )
                        await asyncio.sleep(0.5)  # Пауза между уведомлениями
                    except Exception as e:
                        logger.warning(f"⚠️ Ошибка отправки уведомления: {e}")

                logger.info(f"✅ Добавлено {count} прогнозов от {channel.username}")

    except Exception as e:
        logger.error(
            f"❌ Критическая ошибка мониторинга канала {channel.username}: {e}"
        )


async def update_results_loop(bot):
    """Цикл обновления результатов прогнозов"""
    logger.info("🔄 Запуск цикла обновления результатов")

    while not shutdown_event.is_set():
        try:
            logger.info("🔄 Запуск обновления результатов прогнозов")

            # Только помечаем старые как expired, не ищем результаты для стабильности
            expired_count = await mark_old_predictions_as_expired()

            if expired_count > 0:
                logger.info(f"✅ Помечено как устаревших: {expired_count} прогнозов")

            await asyncio.sleep(RESULTS_UPDATE_INTERVAL)

        except Exception as e:
            logger.error(f"❌ Ошибка обновления результатов: {e}")
            await asyncio.sleep(600)  # 10 минут при ошибке


async def mark_old_predictions_as_expired() -> int:
    """Помечаем старые прогнозы как неактуальные"""
    try:

        async def expire_old_predictions(session):
            cutoff_date = get_naive_utc_now() - timedelta(days=EXPIRED_DAYS)

            result = await session.execute(
                select(Prediction).where(
                    Prediction.result == "pending", Prediction.created_at < cutoff_date
                )
            )

            expired_predictions = result.scalars().all()
            expired_count = len(expired_predictions)

            if expired_count > 0:
                current_time = get_naive_utc_now()

                await session.execute(
                    update(Prediction)
                    .where(
                        Prediction.result == "pending",
                        Prediction.created_at < cutoff_date,
                    )
                    .values(
                        result="expired",
                        result_method="auto_expired",
                        result_updated_at=current_time,
                        updated_at=current_time,
                    )
                )

                logger.info(f"⏰ Помечено как устаревших: {expired_count} прогнозов")

            return expired_count

        return await DatabaseManager.safe_execute(expire_old_predictions)

    except Exception as e:
        logger.error(f"❌ Ошибка пометки старых прогнозов: {e}")
        return 0


# УЛУЧШЕННАЯ функция сканирования истории
async def scan_channel_history(bot, channel, days_back=30, progress_callback=None):
    """Сканирование истории канала с улучшенной обработкой ошибок"""
    logger.info(
        f"🔍 Начинаем сканирование истории канала {channel.username} за {days_back} дней"
    )

    stats = {
        "messages_scanned": 0,
        "predictions_found": 0,
        "auto_results": 0,
        "errors": 0,
        "start_time": get_naive_utc_now(),
    }

    try:
        # Получаем сущность канала
        try:
            entity = await client.get_entity(channel.username)
        except (ChannelPrivateError, UsernameNotOccupiedError) as e:
            logger.error(f"⚠️ Канал {channel.username} недоступен для сканирования: {e}")
            stats["error_message"] = f"Канал недоступен: {str(e)}"
            return stats
        except Exception as e:
            logger.error(f"❌ Ошибка получения канала {channel.username}: {e}")
            stats["error_message"] = f"Ошибка доступа: {str(e)}"
            return stats

        # Определяем дату начала сканирования
        start_date_naive = get_naive_utc_now() - timedelta(days=days_back)
        start_date_aware = make_timezone_aware(start_date_naive)
        current_time_aware = get_utc_now()

        logger.info(
            f"📅 Сканируем сообщения с {start_date_naive.strftime('%d.%m.%Y %H:%M')}"
        )

        # Лимиты для стабильности
        batch_size = 25  # Уменьшенный размер батча
        max_messages = 1000  # Максимум сообщений
        processed_count = 0

        predictions_to_add = []

        try:
            async for message in client.iter_messages(
                entity,
                limit=max_messages,
                offset_date=current_time_aware,
                reverse=False,
            ):
                try:
                    # Проверка даты сообщения
                    message_date = make_timezone_aware(message.date)

                    if message_date < start_date_aware:
                        logger.info(
                            f"📅 Достигли даты {message_date.strftime('%d.%m.%Y')}, останавливаем"
                        )
                        break

                    stats["messages_scanned"] += 1
                    processed_count += 1

                    # Обрабатываем только текстовые сообщения
                    if message.text and len(message.text) > 10:
                        if await is_prediction(message.text):
                            # Проверяем существование
                            async def check_existing_prediction(session):
                                result = await session.execute(
                                    select(Prediction).where(
                                        Prediction.message_id == message.id,
                                        Prediction.channel_id == channel.id,
                                    )
                                )
                                return result.scalar_one_or_none()

                            existing = await DatabaseManager.safe_execute(
                                check_existing_prediction
                            )

                            if not existing:
                                odds = extract_odds(message.text)
                                telegram_date_naive = make_timezone_naive(message.date)

                                # Простое определение результата
                                initial_result = "pending"
                                result_confidence = 0.0
                                result_method = None

                                message_lower = message.text.lower()
                                if any(
                                    keyword in message_lower
                                    for keyword in RESULT_WIN_KEYWORDS
                                ):
                                    initial_result = "win"
                                    result_confidence = 0.7
                                    result_method = "direct_keyword"
                                    stats["auto_results"] += 1
                                elif any(
                                    keyword in message_lower
                                    for keyword in RESULT_LOSS_KEYWORDS
                                ):
                                    initial_result = "loss"
                                    result_confidence = 0.7
                                    result_method = "direct_keyword"
                                    stats["auto_results"] += 1

                                prediction_data = {
                                    "channel_id": channel.id,
                                    "content": message.text[
                                        :2000
                                    ],  # Ограничиваем длину
                                    "odds": odds,
                                    "result": initial_result,
                                    "result_confidence": result_confidence,
                                    "result_method": result_method,
                                    "message_id": message.id,
                                    "telegram_date": telegram_date_naive,
                                    "result_updated_at": get_naive_utc_now()
                                    if initial_result != "pending"
                                    else None,
                                }

                                predictions_to_add.append(prediction_data)
                                stats["predictions_found"] += 1

                    # Обновляем прогресс и сохраняем батчами
                    if processed_count % batch_size == 0:
                        if progress_callback:
                            try:
                                await progress_callback(stats)
                            except Exception:
                                pass

                        # Сохраняем накопленные прогнозы
                        if predictions_to_add:
                            await save_predictions_batch(channel, predictions_to_add)
                            predictions_to_add = []

                        await asyncio.sleep(0.2)  # Пауза для стабильности

                    if processed_count >= max_messages:
                        logger.info(f"⚠️ Достигнут лимит сообщений: {processed_count}")
                        break

                except Exception as e:
                    logger.error(f"❌ Ошибка обработки сообщения: {e}")
                    stats["errors"] += 1
                    continue

        except Exception as e:
            logger.error(f"❌ Ошибка итерации по сообщениям: {e}")
            stats["error_message"] = f"Ошибка чтения: {str(e)}"
            return stats

        # Сохраняем оставшиеся прогнозы
        if predictions_to_add:
            await save_predictions_batch(channel, predictions_to_add)

        # Обновляем статистику канала
        async def update_channel_stats(session):
            channel.predictions_count += stats["predictions_found"]
            channel.results_updated = get_naive_utc_now()
            return True

        await DatabaseManager.safe_execute(update_channel_stats)

        stats["end_time"] = get_naive_utc_now()
        stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()

        logger.info(f"✅ Сканирование канала {channel.username} завершено:")
        logger.info(f"   📨 Проверено сообщений: {stats['messages_scanned']}")
        logger.info(f"   📊 Найдено прогнозов: {stats['predictions_found']}")
        logger.info(f"   🤖 Определено результатов: {stats['auto_results']}")
        logger.info(f"   ⏱ Время выполнения: {stats['duration']:.1f} сек")

        return stats

    except Exception as e:
        logger.error(f"❌ Критическая ошибка сканирования {channel.username}: {e}")
        stats["errors"] += 1
        stats["error_message"] = str(e)
        return stats


async def save_predictions_batch(channel, predictions_data):
    """Сохранение батча прогнозов"""

    async def save_batch(session):
        saved_count = 0
        for pred_data in predictions_data:
            try:
                prediction = Prediction(**pred_data)
                session.add(prediction)
                saved_count += 1
            except Exception as e:
                logger.error(f"❌ Ошибка создания прогноза: {e}")
                continue
        return saved_count

    try:
        saved = await DatabaseManager.safe_execute(save_batch)
        logger.info(f"💾 Сохранено {saved} прогнозов в батче")
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения батча: {e}")


async def is_prediction(text):
    """Проверка, является ли сообщение прогнозом"""
    if not text or len(text) < 10:
        return False

    text_lower = text.lower()

    # Проверяем наличие ключевых слов
    keyword_found = any(keyword.lower() in text_lower for keyword in PARSING_KEYWORDS)

    # Проверяем наличие коэффициентов
    odds_found = extract_odds(text) is not None

    # Минимальная длина
    min_length = len(text) > 20

    return keyword_found and (odds_found or min_length)


def extract_odds(text):
    """Извлечение коэффициента из текста"""
    if not text:
        return None

    patterns = [
        r"коэф[^\d]*(\d+\.?\d*)",  # коэф 1.5
        r"кф[^\d]*(\d+\.?\d*)",  # кф 1.5
        r"odds[^\d]*(\d+\.?\d*)",  # odds 1.5
        r"@(\d+\.?\d*)",  # @1.5
        r"(\d+\.\d{1,2})",  # просто число с точкой
    ]

    for pattern in patterns:
        try:
            matches = re.findall(pattern, text.lower())
            if matches:
                odds = float(matches[0])
                # Проверяем разумность коэффициента
                if 1.01 <= odds <= 20.0:  # Уменьшил максимум
                    return round(odds, 2)
        except (ValueError, IndexError):
            continue

    return None


async def send_notifications(bot, channel, content, odds, message_date):
    """Отправка уведомлений пользователям"""
    try:

        async def get_users_and_send(session):
            result = await session.execute(
                select(User).where(User.notifications_enabled == True)
            )
            users = result.scalars().all()

            if not users:
                return 0

            odds_text = f"{odds}" if odds else "не указан"
            content_preview = content[:300] + "..." if len(content) > 300 else content

            time_str = (
                message_date.strftime("%H:%M")
                if message_date
                else get_naive_utc_now().strftime("%H:%M")
            )

            try:
                notification_text = NEW_PREDICTION_TEXT.format(
                    channel=channel.name,
                    content=content_preview,
                    odds=odds_text,
                    time=time_str,
                    username=channel.username,
                )
            except Exception as e:
                logger.error(f"❌ Ошибка форматирования уведомления: {e}")
                return 0

            sent_count = 0
            current_time = get_naive_utc_now()

            # Ограничиваем количество уведомлений
            for user in users[:10]:  # Максимум 10 пользователей
                try:
                    await bot.send_message(user.telegram_id, notification_text)

                    today = current_time.date()
                    if (
                        not user.last_notification_date
                        or user.last_notification_date.date() != today
                    ):
                        user.notifications_count_today = 1
                    else:
                        user.notifications_count_today += 1

                    user.last_notification_date = current_time
                    sent_count += 1

                    await asyncio.sleep(0.2)  # Пауза между отправками

                except Exception as e:
                    logger.error(
                        f"❌ Не удалось отправить уведомление пользователю {user.telegram_id}: {e}"
                    )
                    continue

            return sent_count

        sent_count = await DatabaseManager.safe_execute(get_users_and_send)
        if sent_count > 0:
            logger.info(
                f"📤 Отправлено {sent_count} уведомлений о прогнозе от {channel.username}"
            )

    except Exception as e:
        logger.error(f"❌ Критическая ошибка отправки уведомлений: {e}")


def stop_monitoring():
    """Остановка мониторинга"""
    logger.info("🛑 Получен сигнал остановки мониторинга")
    shutdown_event.set()


# Функция для graceful shutdown
async def cleanup():
    """Очистка ресурсов"""
    logger.info("🧹 Очистка ресурсов...")
    try:
        if client.is_connected():
            await client.disconnect()
        logger.info("✅ Telethon отключен")
    except Exception as e:
        logger.error(f"❌ Ошибка отключения Telethon: {e}")
