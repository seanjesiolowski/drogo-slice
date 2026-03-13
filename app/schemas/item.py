from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.category import CategoryResponse


class ItemCreate(BaseModel):
    id: int | None = None
    name: str
    unit: str
    current_quantity: float = 0.0
    par_level: float = 0.0
    category_id: int


class ItemUpdate(BaseModel):
    name: str | None = None
    unit: str | None = None
    current_quantity: float | None = None
    par_level: float | None = None
    category_id: int | None = None


class ItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    unit: str
    current_quantity: float
    par_level: float
    category_id: int
    category: CategoryResponse
    created_at: datetime
    updated_at: datetime


class LowStockItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    unit: str
    current_quantity: float
    par_level: float
    category_name: str
    status: str
