from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

UserRole = Literal["user", "admin", "chef"]
OrderStatus = Literal[
    "awaiting_approval",
    "confirmed",
    "placed",
    "preparing",
    "ready",
    "on_ride",
    "delivered",
    "rejected",
]
PaymentMode = Literal["now", "later"]
PaymentStatus = Literal["paid", "due"]


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[str]:
    return mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(
        Enum("user", "admin", "chef", name="user_role"), default="user"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    orders: Mapped[list[Order]] = relationship(back_populates="user")


class MenuItem(Base):
    __tablename__ = "menu_items"
    __table_args__ = (UniqueConstraint("name", "size", name="uq_menu_name_size"),)

    id: Mapped[str] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str] = mapped_column(String(60), index=True)
    size: Mapped[str | None] = mapped_column(String(40), nullable=True)
    price: Mapped[float] = mapped_column(Float)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = _uuid_pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    thread_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(
        Enum(
            "awaiting_approval",
            "confirmed",
            "placed",
            "preparing",
            "ready",
            "on_ride",
            "delivered",
            "rejected",
            name="order_status",
        ),
        default="awaiting_approval",
    )
    payment_mode: Mapped[str] = mapped_column(
        Enum("now", "later", name="payment_mode"), default="now"
    )
    total: Mapped[float] = mapped_column(Float)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    admin_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="orders")
    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    payments: Mapped[list[Payment]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[str] = _uuid_pk()
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    item_name: Mapped[str] = mapped_column(String(120))
    size: Mapped[str | None] = mapped_column(String(40), nullable=True)
    qty: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Float)
    line_total: Mapped[float] = mapped_column(Float)

    order: Mapped[Order] = relationship(back_populates="items")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = _uuid_pk()
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    amount: Mapped[float] = mapped_column(Float)
    method: Mapped[str] = mapped_column(Enum("now", "later", name="payment_method"))
    status: Mapped[str] = mapped_column(Enum("paid", "due", name="payment_status"))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped[Order] = relationship(back_populates="payments")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = _uuid_pk()
    thread_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # user | assistant | system
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PendingApproval(Base):
    """Borrow orders waiting for admin approval (written on interrupt, deleted on decide)."""

    __tablename__ = "pending_approvals"

    id: Mapped[str] = _uuid_pk()
    thread_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    payload: Mapped[str] = mapped_column(Text)  # JSON of the interrupt payload
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
