# StorageClass Feature

## Overview

`StorageClass` is a user-managed entity that defines low-stock and critical-stock threshold multipliers for groups of items. It is distinct from `Category`, which is purely organizational — `StorageClass` carries behavioral configuration.

### Thresholds

Each `StorageClass` stores two multipliers applied against an item's `par_level`:

| Field | Default | Meaning |
|-------|---------|---------|
| `low_threshold` | `0.99` | Item is flagged **low** when `current_quantity <= par_level * low_threshold` |
| `critical_threshold` | `0.5` | Item is flagged **critical** when `current_quantity <= par_level * critical_threshold` |

Items with no `storage_class_id` fall back to these same defaults via `COALESCE` in the database query.

---

## Data Model

### New table: `storage_classes`

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | integer | primary key |
| `name` | varchar(100) | unique, not null |
| `low_threshold` | float | not null, default `0.99` |
| `critical_threshold` | float | not null, default `0.5` |

### Changes to `items`

| Column | Type | Constraints |
|--------|------|-------------|
| `storage_class_id` | integer | nullable, FK → `storage_classes.id` |

Relationship: one `StorageClass` → many `Item`s (mirrors `Category` → `Item`).

---

## Files Changed

| File | Change |
|------|--------|
| `app/models/storage_class.py` | New SQLAlchemy model |
| `app/models/item.py` | Added `storage_class_id` FK + `storage_class` relationship |
| `app/models/__init__.py` | Exported `StorageClass` |
| `app/schemas/storage_class.py` | New Pydantic schemas — Create, Update, Response |
| `app/schemas/item.py` | Added `storage_class_id` + nested `StorageClassResponse` to item schemas |
| `alembic/versions/003_add_storage_classes.py` | Migration — new table + FK column on `items` |
| `app/routers/storage_classes.py` | New router — full CRUD |
| `app/routers/reports.py` | Low-stock query uses `COALESCE` + `outerjoin` for per-item thresholds |
| `app/routers/items.py` | Same threshold-aware filter for `low_stock` query param + `selectinload` on all item fetches |
| `app/main.py` | Registered `storage_classes` router |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/storage-classes/` | List all storage classes |
| `GET` | `/api/storage-classes/{id}` | Get one storage class |
| `POST` | `/api/storage-classes/` | Create a storage class |
| `PATCH` | `/api/storage-classes/{id}` | Update a storage class |
| `DELETE` | `/api/storage-classes/{id}` | Delete (blocked if items are assigned) |

---

## Migration

```bash
alembic upgrade head
```

Revision: `003_add_storage_classes` — revises `002_drop_display_order`.

---

## Design Notes

- `storage_class_id` is **nullable** — existing items are unaffected and use default thresholds.
- Thresholds are resolved at query time via SQL `COALESCE`, so no backfill is required.
- `StorageClass` names are case-insensitively unique (checked at the application layer on create).
- DELETE is blocked if any items are still assigned to the storage class.
- `low_threshold` and `critical_threshold` are validated to `[0.0, 1.0]` at the API boundary.
