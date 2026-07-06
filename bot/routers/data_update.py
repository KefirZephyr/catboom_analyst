from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from modules.dota_data.match_sync import sync_matches

router = Router()


def data_update_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Синхронизировать PandaScore", callback_data="data_update_run")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
        ]
    )


@router.callback_query(F.data == "data_update")
async def data_update_menu(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "🔄 <b>Обновить данные</b>\n\n"
        "Синхронизация загружает турниры, матчи, команды и игроков, если составы доступны в данных PandaScore.",
        reply_markup=data_update_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "data_update_run")
async def data_update_run(callback: CallbackQuery) -> None:
    await callback.message.edit_text("🔄 Обновляю данные PandaScore...", reply_markup=data_update_keyboard())
    result = await sync_matches()

    if result.error:
        text = f"⚠️ <b>Обновление не выполнено</b>\n\n{result.error}"
    else:
        text = (
            "✅ <b>Данные обновлены</b>\n\n"
            f"Будущие матчи: {result.upcoming}\n"
            f"Live: {result.live}\n"
            f"Завершённые: {result.past}\n"
            f"Новые команды: {result.teams}\n"
            f"Новые турниры: {result.tournaments}\n"
            f"Новые матчи: {result.matches}\n"
            f"Новые игроки: {result.players}"
        )

    await callback.message.edit_text(text, reply_markup=data_update_keyboard())
    await callback.answer()
