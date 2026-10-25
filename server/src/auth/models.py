from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base


class Account(Base):
    __tablename__ = "auth_account"
    __table_args__ = (
        CheckConstraint("color_id BETWEEN 1 AND 12", name="color_range"),
        CheckConstraint("age BETWEEN 1 AND 100", name="age_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    is_admin: Mapped[bool] = mapped_column(default=False, server_default="0")
    experience: Mapped[int] = mapped_column(default=0, server_default="0")
    username: Mapped[str] = mapped_column(String(15))
    username_key: Mapped[str] = mapped_column(String(30), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    color_id: Mapped[int]
    age: Mapped[int]
    chat_mode: Mapped[str] = mapped_column(String(6))
    newsletter: Mapped[bool] = mapped_column(default=False)
    parent_email: Mapped[str | None] = mapped_column(String(254))
    terms_accepted_at: Mapped[datetime | None]
    created_at: Mapped[datetime]


class Session(Base):
    __tablename__ = "auth_session"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("auth_account.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(index=True)


class RegistrationDraft(Base):
    __tablename__ = "auth_registration_draft"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(15))
    username_key: Mapped[str] = mapped_column(String(30))
    password_hash: Mapped[str] = mapped_column(String(255))
    color_id: Mapped[int]
    expires_at: Mapped[datetime] = mapped_column(index=True)
