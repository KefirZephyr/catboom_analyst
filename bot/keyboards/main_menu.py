from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📡 Матчи", callback_data="matches")],
            [InlineKeyboardButton(text="📊 Telegram-каналы", callback_data="channels")],
            [InlineKeyboardButton(text="🎯 Сигналы", callback_data="signals")],
            [InlineKeyboardButton(text="📌 Прогнозы на проверку", callback_data="review_predictions")],
            [InlineKeyboardButton(text="💰 Банк", callback_data="bankroll")],
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")],
        ]
    )
