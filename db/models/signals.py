from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"))
    prediction_id: Mapped[int | None] = mapped_column(ForeignKey("telegram_predictions.id"))
    market_type: Mapped[str] = mapped_column(String(64))
    selection: Mapped[str] = mapped_column(String(255))
    picked_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    odds_value: Mapped[float | None] = mapped_column(Float)
    model_probability_percent: Mapped[float] = mapped_column(Float, default=0)
    bookmaker_probability_percent: Mapped[float] = mapped_column(Float, default=0)
    edge_percent: Mapped[float] = mapped_column(Float)
    confidence_percent: Mapped[float] = mapped_column(Float)
    stake_percent: Mapped[float] = mapped_column(Float, default=0)
    recommended_stake: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(32), default="medium")
    explanation: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
