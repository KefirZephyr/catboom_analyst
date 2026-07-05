from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Odds(Base):
    __tablename__ = "odds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    market_type: Mapped[str] = mapped_column(String(64))
    selection: Mapped[str] = mapped_column(String(255))
    value: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(128), default="telegram")
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
