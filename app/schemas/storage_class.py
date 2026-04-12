from pydantic import BaseModel, ConfigDict, Field


class StorageClassCreate(BaseModel):
    name: str
    low_threshold: float = Field(default=0.99, ge=0.0, le=1.0)
    critical_threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class StorageClassUpdate(BaseModel):
    name: str | None = None
    low_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    critical_threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class StorageClassResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    low_threshold: float
    critical_threshold: float
