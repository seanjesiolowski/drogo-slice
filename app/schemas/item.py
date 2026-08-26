from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.category import CategoryResponse

# Largest value the items.id BIGINT column can hold. Item ids are QR label
# numbers supplied by clients, so cap them here to reject out-of-range values
# (e.g. mis-scanned barcodes) before they overflow the DB driver.
BIGINT_MAX = 9_223_372_036_854_775_807


class ItemCreate(BaseModel):
    id: int | None = Field(default=None, ge=1, le=BIGINT_MAX)
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
