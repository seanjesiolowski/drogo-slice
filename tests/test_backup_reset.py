import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_backup_empty_db_returns_valid_structure(client: AsyncClient):
    """Backup of an empty database has the correct envelope with empty lists."""
    response = await client.get("/api/backup")
    assert response.status_code == 200
    data = response.json()
    assert "exported_at" in data
    assert data["categories"] == []
    assert data["items"] == []


@pytest.mark.asyncio
async def test_backup_content_disposition_header(client: AsyncClient):
    """Backup response includes an attachment Content-Disposition header."""
    response = await client.get("/api/backup")
    assert response.status_code == 200
    cd = response.headers.get("content-disposition", "")
    assert cd.startswith("attachment")
    assert "drogo-slice-backup-" in cd
    assert cd.endswith('.json"')


@pytest.mark.asyncio
async def test_backup_includes_categories_and_items(client: AsyncClient):
    """Backup serializes all categories and items with expected fields."""
    cat = await client.post("/api/categories/", json={"name": "Milk"})
    cat_id = cat.json()["id"]

    await client.post(
        "/api/items/",
        json={
            "name": "Oat Milk",
            "unit": "cartons",
            "current_quantity": 5.0,
            "par_level": 10.0,
            "category_id": cat_id,
        },
    )

    response = await client.get("/api/backup")
    assert response.status_code == 200
    data = response.json()

    assert len(data["categories"]) == 1
    assert data["categories"][0]["name"] == "Milk"

    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["name"] == "Oat Milk"
    assert item["unit"] == "cartons"
    assert item["current_quantity"] == 5.0
    assert item["par_level"] == 10.0
    assert item["category_id"] == cat_id
    assert item["category_name"] == "Milk"
    assert "created_at" in item
    assert "updated_at" in item


@pytest.mark.asyncio
async def test_backup_items_ordered_by_id(client: AsyncClient):
    """Backup returns items sorted by id."""
    cat = await client.post("/api/categories/", json={"name": "Beans"})
    cat_id = cat.json()["id"]

    for name in ["Zebra Blend", "Alpha Blend"]:
        await client.post(
            "/api/items/",
            json={"name": name, "unit": "bags", "current_quantity": 1.0, "par_level": 5.0, "category_id": cat_id},
        )

    response = await client.get("/api/backup")
    items = response.json()["items"]
    assert len(items) == 2
    assert items[0]["id"] < items[1]["id"]


@pytest.mark.asyncio
async def test_reset_wipes_all_data(client: AsyncClient):
    """Reset deletes all items and categories."""
    cat = await client.post("/api/categories/", json={"name": "Milk"})
    cat_id = cat.json()["id"]
    await client.post(
        "/api/items/",
        json={"name": "Oat Milk", "unit": "cartons", "current_quantity": 5.0, "par_level": 10.0, "category_id": cat_id},
    )

    assert len((await client.get("/api/items/")).json()) == 1
    assert len((await client.get("/api/categories/")).json()) == 1

    response = await client.post("/api/reset")
    assert response.status_code == 200

    assert (await client.get("/api/items/")).json() == []
    assert (await client.get("/api/categories/")).json() == []


@pytest.mark.asyncio
async def test_reset_returns_success_payload(client: AsyncClient):
    """Reset returns a JSON body confirming the operation."""
    response = await client.post("/api/reset")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "reset"
    assert "message" in data


@pytest.mark.asyncio
async def test_reset_empty_db_is_idempotent(client: AsyncClient):
    """Resetting an already-empty database succeeds without error."""
    response = await client.post("/api/reset")
    assert response.status_code == 200
    response = await client.post("/api/reset")
    assert response.status_code == 200
