import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class GameSession(Base):
    __tablename__ = "game_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    dofirstshot: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    turn: Mapped[str] = mapped_column(String(16), nullable=False)
    pending_shot: Mapped[str | None] = mapped_column(String(3), nullable=True)
    ships: Mapped[list] = mapped_column(JSONB, nullable=False)
    own_hits: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    close_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    shots: Mapped[list["Shot"]] = relationship(back_populates="session", cascade="all, delete-orphan")


Index(
    "ix_game_sessions_active",
    GameSession.status,
    postgresql_where=(GameSession.status == "active"),
)


class Shot(Base):
    __tablename__ = "shots"
    __table_args__ = (UniqueConstraint("session_id", "seq", name="uq_shots_session_id_seq"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    coordinate: Mapped[str] = mapped_column(String(3), nullable=False)
    result: Mapped[str | None] = mapped_column(String(4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    session: Mapped[GameSession] = relationship(back_populates="shots")
