from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from modules.bankroll.bankroll_manager import (
    check_daily_risk_limit,
    check_max_open_bets,
    get_or_create_bankroll_settings,
    update_bankroll,
    update_risk_profile,
)

router = Router()


class BankrollStates(StatesGroup):
    waiting_for_bankroll = State()


def bankroll_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить банк", callback_data="bankroll_edit")],
            [InlineKeyboardButton(text="📏 Лимиты", callback_data="bankroll_limits")],
            [
                InlineKeyboardButton(text="🟢 low", callback_data="bankroll_risk:low"),
                InlineKeyboardButton(text="🟡 normal", callback_data="bankroll_risk:normal"),
                InlineKeyboardButton(text="🔴 high", callback_data="bankroll_risk:high"),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
        ]
    )


@router.callback_query(F.data == "bankroll")
async def bankroll_menu(callback: CallbackQuery) -> None:
    bankroll = await get_or_create_bankroll_settings(callback.from_user.id)
    await callback.message.edit_text(format_bankroll(bankroll), reply_markup=bankroll_keyboard())
    await callback.answer()


@router.callback_query(F.data == "bankroll_edit")
async def bankroll_edit(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BankrollStates.waiting_for_bankroll)
    await callback.message.edit_text(
        "✏️ <b>Изменить банк</b>\n\nВведите новую сумму банка числом, например: 10000",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="bankroll")]]
        ),
    )
    await callback.answer()


@router.message(BankrollStates.waiting_for_bankroll)
async def bankroll_edit_finish(message: Message, state: FSMContext) -> None:
    try:
        amount = float((message.text or "").replace(",", ".").replace(" ", ""))
    except ValueError:
        await message.answer("Введите сумму числом.")
        return

    if amount <= 0:
        await message.answer("Банк должен быть больше нуля.")
        return

    bankroll = await update_bankroll(message.from_user.id, amount)
    await state.clear()
    await message.answer(format_bankroll(bankroll), reply_markup=bankroll_keyboard())


@router.callback_query(F.data.startswith("bankroll_risk:"))
async def bankroll_risk(callback: CallbackQuery) -> None:
    risk_profile = callback.data.split(":", 1)[1]
    bankroll = await update_risk_profile(callback.from_user.id, risk_profile)
    await callback.message.edit_text(format_bankroll(bankroll), reply_markup=bankroll_keyboard())
    await callback.answer("Риск-профиль обновлён", show_alert=True)


@router.callback_query(F.data == "bankroll_limits")
async def bankroll_limits(callback: CallbackQuery) -> None:
    bankroll = await get_or_create_bankroll_settings(callback.from_user.id)
    daily_ok, used_today, daily_limit = await check_daily_risk_limit(callback.from_user.id)
    open_ok, open_count, open_limit = await check_max_open_bets(callback.from_user.id)
    text = (
        "📏 <b>Лимиты банка</b>\n\n"
        f"Максимум на ставку: {bankroll.max_bet_percent:.2f}%\n"
        f"Дневной лимит риска: {bankroll.max_daily_loss_percent:.2f}% "
        f"= {daily_limit:.2f} {bankroll.currency}\n"
        f"Использовано сегодня: {used_today:.2f} {bankroll.currency}\n"
        f"Открытых ставок: {open_count}/{open_limit}\n\n"
        f"Дневной лимит: {'OK' if daily_ok else 'превышен'}\n"
        f"Лимит открытых ставок: {'OK' if open_ok else 'превышен'}"
    )
    await callback.message.edit_text(text, reply_markup=bankroll_keyboard())
    await callback.answer()


def format_bankroll(bankroll) -> str:
    return (
        "💰 <b>Банк</b>\n\n"
        f"Текущий банк: {bankroll.bankroll:.2f} {bankroll.currency}\n"
        f"Риск-профиль: {bankroll.risk_profile}\n"
        f"Максимум на ставку: {bankroll.max_bet_percent:.2f}%\n"
        f"Дневной стоп: {bankroll.max_daily_loss_percent:.2f}%\n"
        f"Максимум открытых ставок: {bankroll.max_open_bets}\n\n"
        "Бот не делает автоставки. Все действия подтверждаются вручную."
    )
