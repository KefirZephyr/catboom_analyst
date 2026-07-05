from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class TelegramPrediction(Base):
    __tablename__ = "telegram_predictions"
    __table_args__ = (
        UniqueConstraint("channel_id", "source_message_id", name="uq_prediction_source_message"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("telegram_channels.id"))
    source_message_id: Mapped[int] = mapped_column(Integer)
    raw_text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(Text)
    market_type: Mapped[str | None] = mapped_column(String(64))
    picked_team_name: Mapped[str | None] = mapped_column(String(255))
    odds_value: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"))
    picked_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    match_confidence: Mapped[float] = mapped_column(Float, default=0)
    match_reason: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    message_date: Mapped[datetime | None] = mapped_column(DateTime)
