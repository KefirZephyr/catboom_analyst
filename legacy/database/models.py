from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Float,
    Boolean,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    url = Column(String(500), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_checked = Column(DateTime)
    predictions_count = Column(Integer, default=0)
    results_updated = Column(DateTime)  # Новое поле


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    odds = Column(Float)
    result = Column(
        String(20), default="pending"
    )  # 'win', 'loss', 'pending', 'expired'
    result_confidence = Column(
        Float, default=0.0
    )  # Новое поле - уверенность в результате
    result_method = Column(String(50))  # Новое поле - способ определения результата
    result_message_id = Column(Integer)  # Новое поле - ID сообщения с результатом
    message_id = Column(Integer)
    telegram_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    result_updated_at = Column(DateTime)  # Новое поле

    __table_args__ = (
        UniqueConstraint("channel_id", "message_id", name="unique_channel_message"),
    )


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    notifications_enabled = Column(Boolean, default=True)
    notifications_count_today = Column(Integer, default=0)
    last_notification_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)


class Statistics(Base):
    __tablename__ = "statistics"

    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, nullable=False)
    date = Column(DateTime, nullable=False)
    predictions_count = Column(Integer, default=0)
    wins_count = Column(Integer, default=0)
    losses_count = Column(Integer, default=0)
    avg_odds = Column(Float, default=0)


class ResultUpdate(Base):
    """Новая таблица для логирования обновлений результатов"""

    __tablename__ = "result_updates"

    id = Column(Integer, primary_key=True)
    prediction_id = Column(Integer, nullable=False)
    old_result = Column(String(20))
    new_result = Column(String(20))
    confidence = Column(Float)
    method = Column(String(50))
    updated_at = Column(DateTime, default=datetime.utcnow)
    message_content = Column(Text)  # Содержимое сообщения с результатом
