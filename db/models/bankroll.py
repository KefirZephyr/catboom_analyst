from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class BankrollSettings(Base):
    __tablename__ = "bankroll_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    currency: Mapped[str] = mapped_column(String(8), default="RUB")
    bankroll: Mapped[float] = mapped_column(Float, default=10000)
    risk_profile: Mapped[str] = mapped_column(String(32), default="normal")
    max_bet_percent: Mapped[float] = mapped_column(Float, default=1)
    max_daily_loss_percent: Mapped[float] = mapped_column(Float, default=3)
    max_open_bets: Mapped[int] = mapped_column(Integer, default=6)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
