import enum
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TransactionType(str, enum.Enum):
    income = "income"
    expense = "expense"


class TransactionSource(str, enum.Enum):
    manual_text = "manual_text"
    receipt_photo = "receipt_photo"
    bank_statement = "bank_statement"
    voice_message = "voice_message"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="current_project")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="project")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    username: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    current_project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    current_project: Mapped["Project | None"] = relationship(back_populates="users")

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="created_by")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType))

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="category")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType))
    source: Mapped[TransactionSource] = mapped_column(Enum(TransactionSource))
    amount: Mapped[float] = mapped_column(Numeric(14, 2))
    description: Mapped[str] = mapped_column(Text, default="")
    counterparty: Mapped[str] = mapped_column(String(255), default="")
    occurred_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    confirmed: Mapped[bool] = mapped_column(Boolean, default=True)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3), default=0)
    unit: Mapped[str] = mapped_column(String(50), default="")
    unit_price: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    payment_type: Mapped[str] = mapped_column(String(20), default="naqd")
    raw_text: Mapped[str] = mapped_column(Text, default="")

    # For native Telegram message-edit support: which of the user's own
    # messages produced this row, and which bot ack message to update in
    # place when they edit it. Persisted in the DB (not process memory) so
    # editing keeps working across deploys/restarts.
    source_message_id: Mapped[int | None] = mapped_column(nullable=True)
    ack_message_id: Mapped[int | None] = mapped_column(nullable=True)

    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    category: Mapped["Category"] = relationship(back_populates="transactions")

    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped["User"] = relationship(back_populates="transactions")

    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    project: Mapped["Project | None"] = relationship(back_populates="transactions")
