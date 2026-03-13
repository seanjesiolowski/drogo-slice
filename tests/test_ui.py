import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_serves_index(client: AsyncClient):
    """Happy path: root (/) serves scanner interface."""
    resp = await client.get("/")
    assert resp.status_code == 200
    text = resp.text
    assert "Drogo Slice" in text
    assert "<html" in text
    # Verify it's the scanner page with QR reader
    assert "QR Item Lookup" in text or "qr-reader" in text


@pytest.mark.asyncio
async def test_root_returns_html(client: AsyncClient):
    """Happy path: root returns HTML content type."""
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_root_has_scanner_elements(client: AsyncClient):
    """Happy path: root has scanner UI elements."""
    resp = await client.get("/")
    assert resp.status_code == 200
    text = resp.text
    assert "startScanner" in text
    assert "stopScanner" in text


@pytest.mark.asyncio
async def test_manage_page_serves(client: AsyncClient):
    """Happy path: /manage serves management interface."""
    resp = await client.get("/manage")
    assert resp.status_code == 200
    text = resp.text
    assert "Drogo Slice" in text
    assert "Manage Inventory" in text


@pytest.mark.asyncio
async def test_manage_returns_html(client: AsyncClient):
    """Happy path: /manage returns HTML content type."""
    resp = await client.get("/manage")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_manage_has_category_form(client: AsyncClient):
    """Happy path: /manage has category creation form."""
    resp = await client.get("/manage")
    assert resp.status_code == 200
    text = resp.text
    assert "Add Category" in text
    assert "createCategory" in text


@pytest.mark.asyncio
async def test_manage_has_item_form(client: AsyncClient):
    """Happy path: /manage has item creation form."""
    resp = await client.get("/manage")
    assert resp.status_code == 200
    text = resp.text
    assert "Add Item" in text
    assert "createItem" in text


@pytest.mark.asyncio
async def test_root_has_manage_link(client: AsyncClient):
    """Happy path: root page has link to /manage."""
    resp = await client.get("/")
    assert resp.status_code == 200
    text = resp.text
    assert "/manage" in text


@pytest.mark.asyncio
async def test_manage_has_scan_link(client: AsyncClient):
    """Happy path: /manage page has link to scanner (/)."""
    resp = await client.get("/manage")
    assert resp.status_code == 200
    text = resp.text
    # Should have nav link back to scanner
    assert "href=\"/\"" in text or "/</a>" in text
