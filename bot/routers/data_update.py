from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from modules.dota_data.match_sync import MatchSyncResult, sync_matches

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
    await callback.answer("Обновляю данные...")
    await callback.message.edit_text("🔄 Обновляю данные PandaScore...", reply_markup=data_update_keyboard())
    result = await sync_matches()
    await callback.message.edit_text(format_data_update_report(result), reply_markup=data_update_keyboard())


def format_data_update_report(result: MatchSyncResult) -> str:
    if result.error:
        return f"⚠️ <b>Обновление не выполнено</b>\n\n{result.error}"

    text = (
        "✅ <b>Данные обновлены</b>\n\n"
        f"Матчи обработано: {result.matches_processed}\n"
        f"Матчи создано: {result.matches_created}\n"
        f"Матчи обновлено: {result.matches_updated}\n"
        f"Команды создано: {result.teams_created}\n"
        f"Команды обновлено: {result.teams_updated}\n"
        f"Турниры создано: {result.tournaments_created}\n"
        f"Турниры обновлено: {result.tournaments_updated}\n"
        f"Игроки создано: {result.players_created}\n"
        f"Игроки обновлено: {result.players_updated}\n"
        f"Player sync skipped: {result.players_skipped}"
    )
    if result.players_reason:
        text += f"\n\nИгроки: {result.players_reason}"
    return text
