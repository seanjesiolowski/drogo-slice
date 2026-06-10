import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_category(client: AsyncClient):
    response = await client.post(
        "/api/categories/", json={"name": "Milk"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Milk"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_categories(client: AsyncClient):
    await client.post("/api/categories/", json={"name": "Syrups"})
    await client.post("/api/categories/", json={"name": "Beans"})

    response = await client.get("/api/categories/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Beans"  # alphabetical order


@pytest.mark.asyncio
async def test_list_categories_empty(client: AsyncClient):
    response = await client.get("/api/categories/")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_category_duplicate_name_returns_409(client: AsyncClient):
    # Create first category
    await client.post("/api/categories/", json={"name": "Milk"})

    # Try to create duplicate - should return 409 Conflict
    response = await client.post(
        "/api/categories/", json={"name": "Milk"}
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_category(client: AsyncClient):
    # Create a category
    create_response = await client.post(
        "/api/categories/", json={"name": "Syrups"}
    )
    category_id = create_response.json()["id"]

    # Delete it
    delete_response = await client.delete(f"/api/categories/{category_id}")
    assert delete_response.status_code == 204

    # Verify it's gone - list should be empty
    list_response = await client.get("/api/categories/")
    assert len(list_response.json()) == 0


@pytest.mark.asyncio
async def test_delete_category_not_found(client: AsyncClient):
    response = await client.delete("/api/categories/999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_category_returns_204_no_content(client: AsyncClient):
    # Create a category
    cat_response = await client.post(
        "/api/categories/", json={"name": "Milk"}
    )
    category_id = cat_response.json()["id"]

    # Delete the category
    delete_response = await client.delete(f"/api/categories/{category_id}")
    assert delete_response.status_code == 204


@pytest.mark.asyncio
async def test_delete_category_with_items_returns_409(client: AsyncClient):
    cat = await client.post("/api/categories/", json={"name": "Milk"})
    category_id = cat.json()["id"]

    await client.post("/api/items/", json={
        "name": "Whole Milk",
        "category_id": category_id,
        "current_quantity": 5.0,
        "par_level": 10.0,
        "unit": "gal",
    })

    response = await client.delete(f"/api/categories/{category_id}")
    assert response.status_code == 409
    assert "still has 1 item" in response.json()["detail"]


@pytest.mark.asyncio
async def test_recreate_deleted_category(client: AsyncClient):
    cat = await client.post("/api/categories/", json={"name": "Seasonal"})
    category_id = cat.json()["id"]

    delete_response = await client.delete(f"/api/categories/{category_id}")
    assert delete_response.status_code == 204

    recreate = await client.post("/api/categories/", json={"name": "Seasonal"})
    assert recreate.status_code == 201
    assert recreate.json()["name"] == "Seasonal"
