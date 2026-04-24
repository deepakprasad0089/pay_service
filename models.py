from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, UniqueConstraint, Index
import uuid
from datetime import datetime, timezone

Base = declarative_base()


class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String(50), primary_key=True)
    merchant_id = Column(String(50), ForeignKey("merchants.id"), index=True)

    amount = Column(Float, nullable=False)
    currency = Column(String(10), nullable=False)
    status = Column(String(50), nullable=False)

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    # Composite index for cursor pagination
    __table_args__ = (
        Index("idx_txn_created_id", "created_at", "id"),
    )


class Event(Base):
    __tablename__ = "events"

    event_id = Column(
        String(100),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    transaction_id = Column(
        String(50),
        ForeignKey("transactions.id"),
        index=True
    )

    merchant_id = Column(
        String(50),
        ForeignKey("merchants.id"),
        index=True
    )

    event_type = Column(String(50), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), nullable=False)

    timestamp = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

  
    __table_args__ = (
        UniqueConstraint("transaction_id", "event_type", name="uix_txn_event"),
    )