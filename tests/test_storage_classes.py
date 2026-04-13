import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_storage_class(client: AsyncClient):
    response = await client.post(
        "/api/storage-classes/",
        json={"name": "Refrigerated", "low_threshold": 0.8, "critical_threshold": 0.3},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Refrigerated"
    assert data["low_threshold"] == 0.8
    assert data["critical_threshold"] == 0.3
    assert "id" in data


@pytest.mark.asyncio
async def test_create_storage_class_defaults(client: AsyncClient):
    response = await client.post(
        "/api/storage-classes/", json={"name": "Dry Goods"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["low_threshold"] == 0.99
    assert data["critical_threshold"] == 0.5


@pytest.mark.asyncio
async def test_list_storage_classes(client: AsyncClient):
    await client.post("/api/storage-classes/", json={"name": "Refrigerated"})
    await client.post("/api/storage-classes/", json={"name": "Dry Goods"})

    response = await client.get("/api/storage-classes/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Dry Goods"  # alphabetical


@pytest.mark.asyncio
async def test_list_storage_classes_empty(client: AsyncClient):
    response = await client.get("/api/storage-classes/")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_storage_class(client: AsyncClient):
    create = await client.post(
        "/api/storage-classes/", json={"name": "Frozen"}
    )
    sc_id = create.json()["id"]

    response = await client.get(f"/api/storage-classes/{sc_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Frozen"


@pytest.mark.asyncio
async def test_get_storage_class_not_found(client: AsyncClient):
    response = await client.get("/api/storage-classes/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_duplicate_name_returns_409(client: AsyncClient):
    await client.post("/api/storage-classes/", json={"name": "Refrigerated"})
    response = await client.post(
        "/api/storage-classes/", json={"name": "Refrigerated"}
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_duplicate_name_case_insensitive(client: AsyncClient):
    await client.post("/api/storage-classes/", json={"name": "Refrigerated"})
    response = await client.post(
        "/api/storage-classes/", json={"name": "refrigerated"}
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_update_storage_class(client: AsyncClient):
    create = await client.post(
        "/api/storage-classes/", json={"name": "Frozen"}
    )
    sc_id = create.json()["id"]

    response = await client.patch(
        f"/api/storage-classes/{sc_id}",
        json={"low_threshold": 0.75},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["low_threshold"] == 0.75
    assert data["name"] == "Frozen"  # unchanged


@pytest.mark.asyncio
async def test_update_storage_class_not_found(client: AsyncClient):
    response = await client.patch(
        "/api/storage-classes/999", json={"name": "Nope"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_storage_class_duplicate_name_returns_409(client: AsyncClient):
    await client.post("/api/storage-classes/", json={"name": "Frozen"})
    create2 = await client.post(
        "/api/storage-classes/", json={"name": "Refrigerated"}
    )
    sc2_id = create2.json()["id"]

    response = await client.patch(
        f"/api/storage-classes/{sc2_id}", json={"name": "Frozen"}
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_delete_storage_class(client: AsyncClient):
    create = await client.post(
        "/api/storage-classes/", json={"name": "Frozen"}
    )
    sc_id = create.json()["id"]

    response = await client.delete(f"/api/storage-classes/{sc_id}")
    assert response.status_code == 204

    response = await client.get("/api/storage-classes/")
    assert response.json() == []


@pytest.mark.asyncio
async def test_delete_storage_class_not_found(client: AsyncClient):
    response = await client.delete("/api/storage-classes/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_storage_class_with_items_returns_409(client: AsyncClient):
    sc = await client.post(
        "/api/storage-classes/", json={"name": "Refrigerated"}
    )
    sc_id = sc.json()["id"]

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
            "storage_class_id": sc_id,
        },
    )

    response = await client.delete(f"/api/storage-classes/{sc_id}")
    assert response.status_code == 409
    assert "still assigned" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_item_with_storage_class(client: AsyncClient):
    sc = await client.post(
        "/api/storage-classes/",
        json={"name": "Frozen", "low_threshold": 0.8, "critical_threshold": 0.3},
    )
    sc_id = sc.json()["id"]

    cat = await client.post("/api/categories/", json={"name": "Milk"})
    cat_id = cat.json()["id"]

    response = await client.post(
        "/api/items/",
        json={
            "name": "Ice Cream",
            "unit": "pints",
            "current_quantity": 3.0,
            "par_level": 10.0,
            "category_id": cat_id,
            "storage_class_id": sc_id,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["storage_class_id"] == sc_id
    assert data["storage_class"]["name"] == "Frozen"
    assert data["storage_class"]["low_threshold"] == 0.8


@pytest.mark.asyncio
async def test_create_item_without_storage_class(client: AsyncClient):
    cat = await client.post("/api/categories/", json={"name": "Milk"})
    cat_id = cat.json()["id"]

    response = await client.post(
        "/api/items/",
        json={
            "name": "Oat Milk",
            "unit": "cartons",
            "current_quantity": 5.0,
            "par_level": 10.0,
            "category_id": cat_id,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["storage_class_id"] is None
    assert data["storage_class"] is None


@pytest.mark.asyncio
async def test_update_item_storage_class(client: AsyncClient):
    sc = await client.post(
        "/api/storage-classes/", json={"name": "Refrigerated"}
    )
    sc_id = sc.json()["id"]

    cat = await client.post("/api/categories/", json={"name": "Dairy"})
    cat_id = cat.json()["id"]

    item = await client.post(
        "/api/items/",
        json={
            "name": "Butter",
            "unit": "sticks",
            "current_quantity": 4.0,
            "par_level": 8.0,
            "category_id": cat_id,
        },
    )
    item_id = item.json()["id"]

    response = await client.patch(
        f"/api/items/{item_id}", json={"storage_class_id": sc_id}
    )
    assert response.status_code == 200
    assert response.json()["storage_class_id"] == sc_id
    assert response.json()["storage_class"]["name"] == "Refrigerated"


@pytest.mark.asyncio
async def test_threshold_validation_rejects_out_of_range(client: AsyncClient):
    response = await client.post(
        "/api/storage-classes/",
        json={"name": "Bad", "low_threshold": 1.5},
    )
    assert response.status_code == 422

    response = await client.post(
        "/api/storage-classes/",
        json={"name": "Bad", "critical_threshold": -0.1},
    )
    assert response.status_code == 422
