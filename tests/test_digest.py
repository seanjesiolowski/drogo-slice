import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def seeded_data(client: AsyncClient):
    """One critical item, one low item, one OK item across two categories."""
    cat = await client.post("/api/categories/", json={"name": "Milk"})
    cat_id = cat.json()["id"]

    # Critical: 2 <= 10 * 0.5
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
    # Low: 6 > 10 * 0.5 and 6 <= 10 * 0.99
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
    # OK: 12 >= par
    await client.post(
        "/api/items/",
        json={
            "name": "Espresso Blend",
            "unit": "bags",
            "current_quantity": 12.0,
            "par_level": 5.0,
            "category_id": cat_id,
        },
    )


@pytest.mark.asyncio
async def test_preview_returns_html(client: AsyncClient):
    response = await client.get("/admin/digest/preview")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Weekly Digest" in response.text


@pytest.mark.asyncio
async def test_preview_empty_db_shows_nothing_to_flag(client: AsyncClient):
    response = await client.get("/admin/digest/preview")
    assert "Nothing to flag." in response.text


@pytest.mark.asyncio
async def test_preview_lists_attention_items(client: AsyncClient, seeded_data):
    response = await client.get("/admin/digest/preview")
    body = response.text

    # Critical and low items appear; OK item does not.
    assert "Oat Milk" in body
    assert "Whole Milk" in body
    assert "Espresso Blend" not in body
    assert "critical" in body
    assert "low" in body


@pytest.mark.asyncio
async def test_send_returns_400_when_unconfigured(client: AsyncClient):
    # No BREVO_API_KEY / DIGEST_* set in the test env -> guarded, never calls Brevo.
    response = await client.post("/admin/digest/send")
    assert response.status_code == 400
    assert "Missing config" in response.json()["detail"]
