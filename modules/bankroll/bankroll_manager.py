from datetime import datetime, time

from sqlalchemy import func, select

from config.settings import settings
from db.models import BankrollSettings, BetOrder
from db.session import async_session

ACTIVE_BET_STATUSES = {"accepted_manually", "open", "pending"}


async def get_or_create_bankroll_settings(user_id: int) -> BankrollSettings:
    async with async_session() as session:
        result = await session.execute(
            select(BankrollSettings).where(BankrollSettings.user_id == user_id)
        )
        bankroll = result.scalar_one_or_none()
        if bankroll:
            return bankroll

        bankroll = BankrollSettings(
            user_id=user_id,
            currency=settings.currency,
            bankroll=settings.start_bankroll,
            risk_profile=settings.risk_profile,
            max_bet_percent=settings.max_bet_percent,
            max_daily_loss_percent=settings.max_daily_loss_percent,
            max_open_bets=settings.max_open_bets,
        )
        session.add(bankroll)
        await session.commit()
        await session.refresh(bankroll)
        return bankroll


async def update_bankroll(user_id: int, bankroll_amount: float) -> BankrollSettings:
    bankroll = await get_or_create_bankroll_settings(user_id)
    async with async_session() as session:
        managed = await session.get(BankrollSettings, bankroll.id)
        managed.bankroll = bankroll_amount
        managed.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(managed)
        return managed


async def update_risk_profile(user_id: int, risk_profile: str) -> BankrollSettings:
    if risk_profile not in {"low", "normal", "high"}:
        raise ValueError("Риск-профиль должен быть low, normal или high")

    bankroll = await get_or_create_bankroll_settings(user_id)
    async with async_session() as session:
        managed = await session.get(BankrollSettings, bankroll.id)
        managed.risk_profile = risk_profile
        managed.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(managed)
        return managed


async def check_daily_risk_limit(user_id: int, extra_stake: float = 0) -> tuple[bool, float, float]:
    bankroll = await get_or_create_bankroll_settings(user_id)
    today_start = datetime.combine(datetime.utcnow().date(), time.min)

    async with async_session() as session:
        result = await session.execute(
            select(func.coalesce(func.sum(BetOrder.stake), 0)).where(
                BetOrder.user_id == user_id,
                BetOrder.status.in_(ACTIVE_BET_STATUSES),
                BetOrder.created_at >= today_start,
            )
        )
        used_today = float(result.scalar_one() or 0)

    max_daily = bankroll.bankroll * bankroll.max_daily_loss_percent / 100
    return used_today + extra_stake <= max_daily, used_today, max_daily


async def check_max_open_bets(user_id: int) -> tuple[bool, int, int]:
    bankroll = await get_or_create_bankroll_settings(user_id)
    async with async_session() as session:
        result = await session.execute(
            select(func.count(BetOrder.id)).where(
                BetOrder.user_id == user_id,
                BetOrder.status.in_(ACTIVE_BET_STATUSES),
            )
        )
        open_count = int(result.scalar_one() or 0)

    return open_count < bankroll.max_open_bets, open_count, bankroll.max_open_bets
