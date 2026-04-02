import base64
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import Base, engine
from app.dependencies import get_db
from app.routers import categories, items, reports


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Drogo Slice",
    description="Shop inventory tracking API",
    version="0.1.0",
    lifespan=lifespan,
)


class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path == "/health":
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Basic "):
            return Response(
                "Unauthorized",
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Drogo Slice"'},
            )

        try:
            decoded = base64.b64decode(auth[6:]).decode("utf-8")
            username, password = decoded.split(":", 1)
        except Exception:
            return Response(
                "Unauthorized",
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Drogo Slice"'},
            )

        valid = secrets.compare_digest(username, settings.admin_username) and secrets.compare_digest(
            password, settings.admin_password
        )
        if not valid:
            return Response(
                "Unauthorized",
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Drogo Slice"'},
            )

        return await call_next(request)


app.add_middleware(BasicAuthMiddleware)

app.include_router(items.router)
app.include_router(categories.router)
app.include_router(reports.router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/api/reset")
async def reset_database(db: AsyncSession = Depends(get_db)):
    """Wipe all items and categories, reset ID sequences to 1."""
    await db.execute(text("DELETE FROM items"))
    await db.execute(text("DELETE FROM categories"))
    await db.execute(text("ALTER SEQUENCE items_id_seq RESTART WITH 1"))
    await db.execute(text("ALTER SEQUENCE categories_id_seq RESTART WITH 1"))
    await db.commit()
    return {"status": "reset", "message": "All data wiped, IDs restart at 1"}


# Serve index.html at root
static_path = Path(__file__).parent / "static"
index_path = static_path / "index.html"


@app.get("/")
async def root():
    if index_path.exists():
        return FileResponse(index_path, media_type="text/html", headers={"Cache-Control": "no-cache"})
    return {"message": "Welcome to Drogo Slice API"}


@app.get("/manage")
async def manage():
    manage_path = static_path / "manage.html"
    if manage_path.exists():
        return FileResponse(manage_path, media_type="text/html", headers={"Cache-Control": "no-cache"})
    return {"message": "Manage page not found"}


@app.get("/qr")
async def qr_manager():
    qr_path = static_path / "qr.html"
    if qr_path.exists():
        return FileResponse(qr_path, media_type="text/html", headers={"Cache-Control": "no-cache"})
    return {"message": "QR page not found"}


# Serve other static files (CSS, JS, etc) from /static if they exist
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
