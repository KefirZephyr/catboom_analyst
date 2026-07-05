from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class BetOrder(Base):
    __tablename__ = "bet_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    signal_id: Mapped[int] = mapped_column(ForeignKey("signals.id"))
    stake: Mapped[float] = mapped_column(Float)
    odds_value: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    user_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
