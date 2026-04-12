from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.item import Item


class StorageClass(Base):
    __tablename__ = "storage_classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    low_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.99)
    critical_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

    items: Mapped[list["Item"]] = relationship(back_populates="storage_class")
