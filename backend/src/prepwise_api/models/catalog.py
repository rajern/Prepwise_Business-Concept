from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from prepwise_api.models.base import Base, TimestampMixin, UuidPrimaryKeyMixin

if TYPE_CHECKING:
    from prepwise_api.models.cart import CartItem
    from prepwise_api.models.order import Order, OrderItem

meal_ingredients = Table(
    "meal_ingredients",
    Base.metadata,
    Column("meal_id", Uuid, ForeignKey("meals.id", ondelete="CASCADE"), nullable=False),
    Column(
        "ingredient_id",
        Uuid,
        ForeignKey("ingredients.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("position", SmallInteger, nullable=False),
    PrimaryKeyConstraint("meal_id", "ingredient_id"),
    UniqueConstraint("meal_id", "position"),
    CheckConstraint("position >= 0", name="position_non_negative"),
)

meal_allergens = Table(
    "meal_allergens",
    Base.metadata,
    Column("meal_id", Uuid, ForeignKey("meals.id", ondelete="CASCADE"), nullable=False),
    Column(
        "allergen_id",
        Uuid,
        ForeignKey("allergens.id", ondelete="CASCADE"),
        nullable=False,
    ),
    PrimaryKeyConstraint("meal_id", "allergen_id"),
)


class Meal(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "meals"
    __table_args__ = (
        CheckConstraint("price_nok >= 0", name="price_non_negative"),
        CheckConstraint("calories >= 0", name="calories_non_negative"),
        CheckConstraint("protein_grams >= 0", name="protein_non_negative"),
        CheckConstraint("carbohydrate_grams >= 0", name="carbohydrate_non_negative"),
        CheckConstraint("fat_grams >= 0", name="fat_non_negative"),
    )

    name: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(2048))
    price_nok: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    calories: Mapped[int] = mapped_column(Integer)
    protein_grams: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    carbohydrate_grams: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    fat_grams: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    available: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    ingredients: Mapped[list[Ingredient]] = relationship(
        secondary=meal_ingredients,
        back_populates="meals",
        order_by=meal_ingredients.c.position,
    )
    allergens: Mapped[list[Allergen]] = relationship(
        secondary=meal_allergens,
        back_populates="meals",
    )
    cart_items: Mapped[list[CartItem]] = relationship(back_populates="meal")
    order_items: Mapped[list[OrderItem]] = relationship(back_populates="meal")


class Ingredient(UuidPrimaryKeyMixin, Base):
    __tablename__ = "ingredients"

    name: Mapped[str] = mapped_column(String(200), unique=True)

    meals: Mapped[list[Meal]] = relationship(
        secondary=meal_ingredients,
        back_populates="ingredients",
    )


class Allergen(UuidPrimaryKeyMixin, Base):
    __tablename__ = "allergens"

    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)

    meals: Mapped[list[Meal]] = relationship(
        secondary=meal_allergens,
        back_populates="allergens",
    )


class PickupLocation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pickup_locations"

    name: Mapped[str] = mapped_column(String(200), unique=True)
    address_line: Mapped[str] = mapped_column(String(255))
    postal_code: Mapped[str] = mapped_column(String(20))
    city: Mapped[str] = mapped_column(String(100), default="Oslo", server_default="Oslo")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    orders: Mapped[list[Order]] = relationship(back_populates="pickup_location")
