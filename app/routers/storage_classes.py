from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.item import Item
from app.models.storage_class import StorageClass
from app.schemas.storage_class import (
    StorageClassCreate,
    StorageClassResponse,
    StorageClassUpdate,
)

router = APIRouter(prefix="/api/storage-classes", tags=["storage-classes"])


@router.get("/", response_model=list[StorageClassResponse])
async def list_storage_classes(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(StorageClass).order_by(StorageClass.name))
    return result.scalars().all()


@router.get("/{storage_class_id}", response_model=StorageClassResponse)
async def get_storage_class(storage_class_id: int, db: AsyncSession = Depends(get_db)):
    sc = await db.get(StorageClass, storage_class_id)
    if sc is None:
        raise HTTPException(status_code=404, detail="Storage class not found")
    return sc


@router.post("/", response_model=StorageClassResponse, status_code=status.HTTP_201_CREATED)
async def create_storage_class(
    payload: StorageClassCreate, db: AsyncSession = Depends(get_db)
):
    existing = await db.execute(
        select(StorageClass).where(
            func.lower(StorageClass.name) == payload.name.strip().lower()
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Storage class '{payload.name}' already exists",
        )
    sc = StorageClass(**payload.model_dump())
    db.add(sc)
    await db.commit()
    await db.refresh(sc)
    return sc


@router.patch("/{storage_class_id}", response_model=StorageClassResponse)
async def update_storage_class(
    storage_class_id: int,
    payload: StorageClassUpdate,
    db: AsyncSession = Depends(get_db),
):
    sc = await db.get(StorageClass, storage_class_id)
    if sc is None:
        raise HTTPException(status_code=404, detail="Storage class not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(sc, field, value)
    try:
        await db.commit()
        await db.refresh(sc)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Storage class name already exists",
        )
    return sc


@router.delete("/{storage_class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_storage_class(
    storage_class_id: int, db: AsyncSession = Depends(get_db)
):
    sc = await db.get(StorageClass, storage_class_id)
    if sc is None:
        raise HTTPException(status_code=404, detail="Storage class not found")
    item_count = await db.scalar(
        select(func.count())
        .select_from(Item)
        .where(Item.storage_class_id == storage_class_id)
    )
    if item_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete — {item_count} item{'s' if item_count != 1 else ''} still assigned. Reassign them first.",
        )
    await db.delete(sc)
    await db.commit()
