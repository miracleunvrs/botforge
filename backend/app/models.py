from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    definition: Mapped[dict[str, Any]] = mapped_column(JSON)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    telegram_bot_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    telegram_bot_username: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("idx_workflows_updated_at", updated_at.desc()),)

    @property
    def has_token(self) -> bool:
        return bool(self.telegram_bot_token)


class BotUser(Base):
    __tablename__ = "bot_users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    workflow_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("workflows.id", ondelete="CASCADE"))
    telegram_user_id: Mapped[int] = mapped_column(BigInteger)
    username: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    current_node_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    workflow_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("workflows.id", ondelete="CASCADE"))
    bot_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("bot_users.id", ondelete="SET NULL"), nullable=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    direction: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)
    node_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TelegramUpdate(Base):
    __tablename__ = "telegram_updates"

    workflow_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("workflows.id", ondelete="CASCADE"), primary_key=True
    )
    update_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
