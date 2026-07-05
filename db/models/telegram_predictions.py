from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class TelegramPrediction(Base):
    __tablename__ = "telegram_predictions"
    __table_args__ = (
        UniqueConstraint("channel_id", "message_id", name="uq_prediction_message"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("telegram_channels.id"))
    message_id: Mapped[int] = mapped_column(Integer)
    raw_text: Mapped[str] = mapped_column(Text)
    market_type: Mapped[str | None] = mapped_column(String(64))
    team_name: Mapped[str | None] = mapped_column(String(255))
    odds_value: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    message_date: Mapped[datetime | None] = mapped_column(DateTime)
