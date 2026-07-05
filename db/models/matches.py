from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class DotaMatch(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    tournament_id: Mapped[int | None] = mapped_column(ForeignKey("tournaments.id"))
    team_a_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    team_b_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    best_of: Mapped[int | None] = mapped_column(Integer)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(32), default="scheduled")
    winner_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
