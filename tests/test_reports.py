import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def seeded_data(client: AsyncClient):
    """Create categories and items with various stock levels."""
    cat = await client.post(
        "/api/categories/", json={"name": "Milk", "display_order": 1}
    )
    cat_id = cat.json()["id"]

    cat2 = await client.post(
        "/api/categories/", json={"name": "Beans", "display_order": 2}
    )
    cat2_id = cat2.json()["id"]

    # Critical: 2 < 10 * 0.5 = 5
    await client.post(
        "/api/items/",
        json={
            "name": "Oat Milk",
            "unit": "cartons",
            "current_quantity": 2.0,
            "par_level": 10.0,
            "category_id": cat_id,
        },
    )

    # Low: 6 >= 10 * 0.5 but 6 < 10
    await client.post(
        "/api/items/",
        json={
            "name": "Whole Milk",
            "unit": "gallons",
            "current_quantity": 6.0,
            "par_level": 10.0,
            "category_id": cat_id,
        },
    )

    # OK: 12 >= 5 (not low stock, should NOT appear)
    await client.post(
        "/api/items/",
        json={
            "name": "Espresso Blend",
            "unit": "bags",
            "current_quantity": 12.0,
            "par_level": 5.0,
            "category_id": cat2_id,
        },
    )

    # Critical: 1 < 8 * 0.5 = 4
    await client.post(
        "/api/items/",
        json={
            "name": "Decaf Blend",
            "unit": "bags",
            "current_quantity": 1.0,
            "par_level": 8.0,
            "category_id": cat2_id,
        },
    )

    return {"cat_id": cat_id, "cat2_id": cat2_id}


@pytest.mark.asyncio
async def test_low_stock_report_returns_only_low_items(
    client: AsyncClient, seeded_data
):
    response = await client.get("/api/reports/low-stock")
    assert response.status_code == 200
    data = response.json()

    # Should exclude Espresso Blend (ok stock)
    assert len(data) == 3
    names = [item["name"] for item in data]
    assert "Espresso Blend" not in names


@pytest.mark.asyncio
async def test_low_stock_report_critical_status(client: AsyncClient, seeded_data):
    response = await client.get("/api/reports/low-stock")
    data = response.json()

    # Critical items ordered first (by status_expr, then name)
    critical_items = [i for i in data if i["status"] == "critical"]
    assert len(critical_items) == 2
    critical_names = {i["name"] for i in critical_items}
    assert critical_names == {"Oat Milk", "Decaf Blend"}


@pytest.mark.asyncio
async def test_low_stock_report_low_status(client: AsyncClient, seeded_data):
    response = await client.get("/api/reports/low-stock")
    data = response.json()

    low_items = [i for i in data if i["status"] == "low"]
    assert len(low_items) == 1
    assert low_items[0]["name"] == "Whole Milk"


@pytest.mark.asyncio
async def test_low_stock_report_includes_category_name(
    client: AsyncClient, seeded_data
):
    response = await client.get("/api/reports/low-stock")
    data = response.json()

    oat = next(i for i in data if i["name"] == "Oat Milk")
    assert oat["category_name"] == "Milk"

    decaf = next(i for i in data if i["name"] == "Decaf Blend")
    assert decaf["category_name"] == "Beans"


@pytest.mark.asyncio
async def test_low_stock_report_empty_when_all_stocked(client: AsyncClient):
    cat = await client.post(
        "/api/categories/", json={"name": "Cups", "display_order": 1}
    )
    cat_id = cat.json()["id"]

    await client.post(
        "/api/items/",
        json={
            "name": "Large Cups",
            "unit": "sleeves",
            "current_quantity": 20.0,
            "par_level": 10.0,
            "category_id": cat_id,
        },
    )

    response = await client.get("/api/reports/low-stock")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_low_stock_report_schema_fields(client: AsyncClient, seeded_data):
    response = await client.get("/api/reports/low-stock")
    data = response.json()

    item = data[0]
    assert "id" in item
    assert "name" in item
    assert "unit" in item
    assert "current_quantity" in item
    assert "par_level" in item
    assert "category_name" in item
    assert "status" in item
