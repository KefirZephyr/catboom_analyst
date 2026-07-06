from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏆 Турниры", callback_data="tournaments")],
            [InlineKeyboardButton(text="📅 Матчи", callback_data="matches")],
            [InlineKeyboardButton(text="👥 Команды", callback_data="teams")],
            [InlineKeyboardButton(text="🎮 Игроки", callback_data="players")],
            [InlineKeyboardButton(text="🔮 Прогнозы", callback_data="predictions")],
            [InlineKeyboardButton(text="🔄 Обновить данные", callback_data="data_update")],
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")],
        ]
    )
