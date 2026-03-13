from pydantic import BaseModel, ConfigDict


class CategoryCreate(BaseModel):
    name: str
    display_order: int = 0


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    display_order: int
