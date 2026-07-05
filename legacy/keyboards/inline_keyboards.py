from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config.texts import BUTTONS, CHANNEL_BUTTONS, STATS_BUTTONS, NOTIFICATION_BUTTONS


def main_menu_keyboard():
    """Главное меню с иконками в стиле изображения"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📺 Мои каналы", callback_data="channels")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="statistics")],
            [
                InlineKeyboardButton(
                    text="🔔 Уведомления", callback_data="notifications"
                )
            ],
            [InlineKeyboardButton(text="❓ Справка", callback_data="help")],
        ]
    )


def channels_menu_keyboard():
    """Меню управления каналами"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Список каналов", callback_data="channels_list"
                )
            ],
            [
                InlineKeyboardButton(text="➕ Добавить", callback_data="channels_add"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data="channels_remove"),
            ],
            [InlineKeyboardButton(text="🔗 Меню", callback_data="main_menu")],
        ]
    )


def channel_select_keyboard(channels, action="select"):
    """Клавиатура выбора канала"""
    keyboard = []
    for channel in channels:
        status = "🟢" if channel.is_active else "🔴"
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"{status} {channel.name}",
                    callback_data=f"channel_{action}_{channel.id}",
                )
            ]
        )
    keyboard.append([InlineKeyboardButton(text="🔗 Меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def channel_actions_keyboard(channel_id):
    """Действия с каналом"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Статистика", callback_data=f"channel_stats_{channel_id}"
                ),
                InlineKeyboardButton(
                    text="ℹ️ Инфо", callback_data=f"channel_info_{channel_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔍 Сканировать", callback_data=f"scan_history_{channel_id}"
                ),
                InlineKeyboardButton(
                    text="🔄 Вкл/Выкл", callback_data=f"channel_toggle_{channel_id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Удалить", callback_data=f"channel_delete_{channel_id}"
                )
            ],
            [InlineKeyboardButton(text="🔗 Меню", callback_data="main_menu")],
        ]
    )


def stats_menu_keyboard():
    """Меню статистики"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📅 7 дней", callback_data="stats_7"),
                InlineKeyboardButton(text="📅 30 дней", callback_data="stats_30"),
            ],
            [
                InlineKeyboardButton(text="📅 90 дней", callback_data="stats_90"),
                InlineKeyboardButton(text="📅 Все время", callback_data="stats_all"),
            ],
            [
                InlineKeyboardButton(
                    text="📊 Общая статистика", callback_data="stats_summary"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⚖️ Сравнить каналы", callback_data="stats_compare"
                )
            ],
            [InlineKeyboardButton(text="🔗 Меню", callback_data="main_menu")],
        ]
    )


def stats_period_keyboard(channel_id=None):
    """Клавиатура выбора периода для статистики"""
    prefix = f"channel_stats_{channel_id}" if channel_id else "stats"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="7 дней", callback_data=f"{prefix}_7"),
                InlineKeyboardButton(text="30 дней", callback_data=f"{prefix}_30"),
            ],
            [
                InlineKeyboardButton(text="90 дней", callback_data=f"{prefix}_90"),
                InlineKeyboardButton(text="Все время", callback_data=f"{prefix}_all"),
            ],
            [InlineKeyboardButton(text="🔗 Меню", callback_data="main_menu")],
        ]
    )


def notifications_keyboard(enabled=True):
    """Клавиатура уведомлений"""
    button_text = "🔕 Отключить" if enabled else "🔔 Включить"
    callback = "notifications_disable" if enabled else "notifications_enable"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=button_text, callback_data=callback)],
            [
                InlineKeyboardButton(
                    text="📋 Статус", callback_data="notifications_status"
                )
            ],
            [InlineKeyboardButton(text="🔗 Меню", callback_data="main_menu")],
        ]
    )


def back_to_main_keyboard():
    """Кнопка возврата в главное меню в стиле изображения"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Меню", callback_data="main_menu")]
        ]
    )


def confirm_keyboard(action, item_id=None):
    """Клавиатура подтверждения действия"""
    callback_confirm = f"confirm_{action}_{item_id}" if item_id else f"confirm_{action}"
    callback_cancel = f"cancel_{action}_{item_id}" if item_id else f"cancel_{action}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data=callback_confirm),
                InlineKeyboardButton(text="❌ Нет", callback_data=callback_cancel),
            ]
        ]
    )
