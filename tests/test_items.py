import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def category_id(client: AsyncClient) -> int:
    response = await client.post(
        "/api/categories/", json={"name": "Milk", "display_order": 1}
    )
    return response.json()["id"]


@pytest.mark.asyncio
async def test_create_item(client: AsyncClient, category_id: int):
    response = await client.post(
        "/api/items/",
        json={
            "name": "Oat Milk",
            "unit": "cartons",
            "current_quantity": 5.0,
            "par_level": 10.0,
            "category_id": category_id,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Oat Milk"
    assert data["category"]["name"] == "Milk"


@pytest.mark.asyncio
async def test_get_item_not_found(client: AsyncClient):
    response = await client.get("/api/items/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_item(client: AsyncClient, category_id: int):
    create = await client.post(
        "/api/items/",
        json={
            "name": "Whole Milk",
            "unit": "gallons",
            "current_quantity": 3.0,
            "par_level": 5.0,
            "category_id": category_id,
        },
    )
    item_id = create.json()["id"]

    response = await client.patch(
        f"/api/items/{item_id}", json={"current_quantity": 8.0}
    )
    assert response.status_code == 200
    assert response.json()["current_quantity"] == 8.0


@pytest.mark.asyncio
async def test_delete_item(client: AsyncClient, category_id: int):
    create = await client.post(
        "/api/items/",
        json={
            "name": "2% Milk",
            "unit": "gallons",
            "current_quantity": 2.0,
            "par_level": 4.0,
            "category_id": category_id,
        },
    )
    item_id = create.json()["id"]

    response = await client.delete(f"/api/items/{item_id}")
    assert response.status_code == 204

    response = await client.get(f"/api/items/{item_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_low_stock_filter(client: AsyncClient, category_id: int):
    await client.post(
        "/api/items/",
        json={
            "name": "Oat Milk",
            "unit": "cartons",
            "current_quantity": 2.0,
            "par_level": 10.0,
            "category_id": category_id,
        },
    )
    await client.post(
        "/api/items/",
        json={
            "name": "Whole Milk",
            "unit": "gallons",
            "current_quantity": 10.0,
            "par_level": 5.0,
            "category_id": category_id,
        },
    )

    response = await client.get("/api/items/", params={"low_stock": True})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Oat Milk"


@pytest.mark.asyncio
async def test_update_item_not_found(client: AsyncClient):
    response = await client.patch("/api/items/999", json={"current_quantity": 5.0})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_item_not_found(client: AsyncClient):
    response = await client.delete("/api/items/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_items_empty(client: AsyncClient):
    response = await client.get("/api/items/")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_items_filter_by_category(client: AsyncClient, category_id: int):
    # Create item in known category
    await client.post(
        "/api/items/",
        json={
            "name": "Oat Milk",
            "unit": "cartons",
            "current_quantity": 5.0,
            "par_level": 10.0,
            "category_id": category_id,
        },
    )

    # Filter by this category
    response = await client.get("/api/items/", params={"category_id": category_id})
    assert response.status_code == 200
    assert len(response.json()) == 1

    # Filter by non-existent category
    response = await client.get("/api/items/", params={"category_id": 9999})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_item_response_includes_timestamps(client: AsyncClient, category_id: int):
    response = await client.post(
        "/api/items/",
        json={
            "name": "Test Item",
            "unit": "units",
            "current_quantity": 1.0,
            "par_level": 5.0,
            "category_id": category_id,
        },
    )
    data = response.json()
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_get_next_id_empty(client: AsyncClient):
    """Next ID should be 1 when no items exist."""
    response = await client.get("/api/items/next-id")
    assert response.status_code == 200
    assert response.json()["next_id"] == 1


@pytest.mark.asyncio
async def test_get_next_id_after_items_created(client: AsyncClient, category_id: int):
    """Next ID should be max(id) + 1."""
    # Create a few items
    for i in range(3):
        await client.post(
            "/api/items/",
            json={
                "name": f"Item {i}",
                "unit": "units",
                "current_quantity": 1.0,
                "par_level": 5.0,
                "category_id": category_id,
            },
        )

    response = await client.get("/api/items/next-id")
    assert response.status_code == 200
    assert response.json()["next_id"] == 4


@pytest.mark.asyncio
async def test_reassign_item_id(client: AsyncClient, category_id: int):
    """Reassign endpoint should change item's primary key."""
    # Create an item
    create = await client.post(
        "/api/items/",
        json={
            "name": "Oat Milk",
            "unit": "cartons",
            "current_quantity": 5.0,
            "par_level": 10.0,
            "category_id": category_id,
        },
    )
    old_id = create.json()["id"]

    # Reassign to new ID
    response = await client.post(f"/api/items/{old_id}/reassign?new_id=100")
    assert response.status_code == 200
    assert response.json()["id"] == 100
    assert response.json()["name"] == "Oat Milk"

    # Old ID should no longer exist
    response = await client.get(f"/api/items/{old_id}")
    assert response.status_code == 404

    # New ID should exist
    response = await client.get("/api/items/100")
    assert response.status_code == 200
    assert response.json()["id"] == 100


@pytest.mark.asyncio
async def test_reassign_item_id_not_found(client: AsyncClient):
    """Reassign non-existent item should return 404."""
    response = await client.post("/api/items/999/reassign?new_id=100")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_reassign_item_id_target_exists(client: AsyncClient, category_id: int):
    """Reassign to existing ID should return 409."""
    # Create two items
    item1 = await client.post(
        "/api/items/",
        json={
            "name": "Item 1",
            "unit": "units",
            "current_quantity": 1.0,
            "par_level": 5.0,
            "category_id": category_id,
        },
    )
    item1_id = item1.json()["id"]

    item2 = await client.post(
        "/api/items/",
        json={
            "name": "Item 2",
            "unit": "units",
            "current_quantity": 2.0,
            "par_level": 5.0,
            "category_id": category_id,
        },
    )
    item2_id = item2.json()["id"]

    # Try to reassign item1 to item2's ID
    response = await client.post(f"/api/items/{item1_id}/reassign?new_id={item2_id}")
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_item_partial_update_preserves_other_fields(
    client: AsyncClient, category_id: int
):
    """Partial PATCH should only update specified fields."""
    # Create an item
    create = await client.post(
        "/api/items/",
        json={
            "name": "Original Item",
            "unit": "cartons",
            "current_quantity": 5.0,
            "par_level": 10.0,
            "category_id": category_id,
        },
    )
    item_id = create.json()["id"]

    # Update only the quantity
    response = await client.patch(
        f"/api/items/{item_id}",
        json={"current_quantity": 8.0},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Original Item"  # Unchanged
    assert data["unit"] == "cartons"  # Unchanged
    assert data["current_quantity"] == 8.0  # Updated
    assert data["par_level"] == 10.0  # Unchanged


@pytest.mark.asyncio
async def test_list_items_filter_multiple_results(client: AsyncClient, category_id: int):
    """Test listing items with multiple results maintains ordering."""
    # Create multiple items
    for name in ["Zebra Milk", "Apple Milk", "Banana Beans"]:
        await client.post(
            "/api/items/",
            json={
                "name": name,
                "unit": "units",
                "current_quantity": 1.0,
                "par_level": 5.0,
                "category_id": category_id,
            },
        )

    response = await client.get("/api/items/")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 3
    # Items should be sorted by name
    assert items[0]["name"] == "Apple Milk"
    assert items[1]["name"] == "Banana Beans"
    assert items[2]["name"] == "Zebra Milk"
