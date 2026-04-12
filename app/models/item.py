from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.storage_class import StorageClass


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        Index("ix_items_category_id", "category_id"),
        Index("ix_items_name", "name"),
        Index("ix_items_storage_class_id", "storage_class_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    current_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    par_level: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("categories.id"), nullable=False
    )
    storage_class_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("storage_classes.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    category: Mapped["Category"] = relationship(back_populates="items")
    storage_class: Mapped["StorageClass | None"] = relationship(back_populates="items")
