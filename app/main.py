import asyncio
import base64
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from fastapi import Depends, FastAPI, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import session
from app.accounts import PRIMARY, SECONDARY, Account, configured_accounts
from app.config import settings
from app.database import Base, async_session, engine, sessionmaker_for_name
from app.dependencies import get_db
from app.observability import init_sentry
from app.models.category import Category
from app.models.item import Item
from app.routers import categories, digest, items, reports


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Primary only, by design: the secondary database's schema is brought up
    # to date by alembic via app/bootstrap.py at boot, not by create_all here.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


init_sentry(settings)

app = FastAPI(
    title="Drogo Slice",
    description="Shop inventory tracking API",
    version="0.1.0",
    lifespan=lifespan,
)


static_path = Path(__file__).parent / "static"

PUBLIC_PATHS = {"/login", "/logout"}


def authenticate(username: str, password: str) -> Account | None:
    """Return the account these credentials belong to, or None."""
    for account in configured_accounts():
        # compare_digest rejects non-ASCII str with a TypeError; comparing
        # the UTF-8 bytes instead makes an accented username a rejection
        # (401) rather than an unhandled 500.
        if secrets.compare_digest(
            username.encode("utf-8"), account.username.encode("utf-8")
        ) and secrets.compare_digest(
            password.encode("utf-8"), account.password.encode("utf-8")
        ):
            return account
    return None


def _account_from_cookie(request: Request) -> str | None:
    """The account named by a valid session cookie, if there is one.

    A good signature is not enough. The account must still be configured:
    a cookie issued while the secondary login existed must stop working
    once that login is removed from the environment, rather than routing
    its holder at a database that is no longer set up.
    """
    token = request.cookies.get(session.COOKIE_NAME)
    if not token:
        return None

    name = session.verify(token, secret=session.current_secret())
    if name is None:
        return None
    if not any(account.name == name for account in configured_accounts()):
        return None
    return name


def _safe_next(raw: str | None) -> str:
    r"""Where to send the browser after login -- only ever a path on this site.

    An open redirect on a login form is a credential-phishing stepping
    stone, so anything that could resolve to another origin becomes "/".
    Backslash is rejected because some browsers normalise it to a slash,
    making "/\evil.example" a protocol-relative URL.
    """
    if not raw or not raw.startswith("/"):
        return "/"
    if raw.startswith("//") or raw.startswith("/\\"):
        return "/"
    return raw


def _wants_html_page(request: Request) -> bool:
    """Is this a browser navigating to a page, rather than a tool or a fetch()?"""
    return request.method == "GET" and "text/html" in request.headers.get("accept", "")


def _login_redirect(request: Request) -> Response:
    """Send a browser to the login form, remembering where it was headed.

    Deliberately carries no WWW-Authenticate header: that is what would make
    the browser throw its own Basic prompt over the top of the login page.
    """
    destination = request.url.path
    if request.url.query:
        destination = f"{destination}?{request.url.query}"
    return RedirectResponse(f"/login?next={quote(destination, safe='')}", status_code=303)


def _unauthorized_response() -> Response:
    return Response(
        "Unauthorized",
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="Drogo Slice"'},
    )


class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path == "/health":
            request.state.account = PRIMARY
            return await call_next(request)

        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        cookie_account = _account_from_cookie(request)
        if cookie_account is not None:
            request.state.account = cookie_account
            return await call_next(request)

        # A browser that has ever answered the native Basic prompt replays
        # that credential forever, so honouring it here would undo every
        # log-off: the cookie would clear and the next page load would sign
        # the person straight back in. Pages authenticate by cookie only;
        # the Basic header below is for curl, /docs and scripts.
        if _wants_html_page(request):
            return _login_redirect(request)

        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Basic "):
            return _unauthorized_response()

        try:
            decoded = base64.b64decode(auth[6:]).decode("utf-8")
            username, password = decoded.split(":", 1)
        except Exception:
            return _unauthorized_response()

        matched = authenticate(username, password)
        if matched is None:
            return _unauthorized_response()

        request.state.account = matched.name
        return await call_next(request)


app.add_middleware(BasicAuthMiddleware)


@app.get("/login")
async def login_page():
    return FileResponse(
        static_path / "login.html", media_type="text/html", headers={"Cache-Control": "no-cache"}
    )


@app.post("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(session.COOKIE_NAME, httponly=True, samesite="lax")
    return response


@app.post("/login")
async def login(request: Request, username: str = Form(""), password: str = Form("")):
    destination = _safe_next(request.query_params.get("next"))

    account = authenticate(username, password)
    if account is None:
        # Back to the form, never a 401: a 401 here carries WWW-Authenticate
        # and the browser would answer it with its own prompt.
        return RedirectResponse(
            f"/login?error=1&next={quote(destination, safe='')}", status_code=303
        )

    response = RedirectResponse(destination, status_code=303)
    response.set_cookie(
        session.COOKIE_NAME,
        session.issue(account.name, secret=session.current_secret()),
        max_age=session.ONE_YEAR,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
    )
    return response


@app.get("/api/whoami")
async def whoami(request: Request):
    """Which login the caller is using, so the page can say so."""
    return {"account": request.state.account}


@app.exception_handler(OperationalError)
@app.exception_handler(OSError)
async def database_unavailable(request: Request, exc: Exception) -> JSONResponse:
    """A database that cannot be reached is a 503, not an opaque 500.

    SQLAlchemy wraps some connection failures (an auth rejection, for
    example) in OperationalError, but a DNS lookup failure raises
    socket.gaierror and a refused port raises ConnectionRefusedError --
    both OSError subclasses that never touch OperationalError. Both
    handlers are registered on the same function so either path lands
    here. Deliberately not a bare Exception handler: that would turn
    every genuine bug into a silent 503.

    Never include exc's message or the database URL in the response --
    the URL carries the account's password.
    """
    account = getattr(request.state, "account", "unknown")
    return JSONResponse(
        status_code=503,
        content={"detail": f"Database for account '{account}' is unavailable"},
    )


app.include_router(items.router)
app.include_router(categories.router)
app.include_router(reports.router)
app.include_router(digest.router)


async def _secondary_status() -> str:
    """Report the secondary database without ever affecting /health's status code."""
    if not any(account.name == SECONDARY for account in configured_accounts()):
        return "not_configured"
    try:
        async with asyncio.timeout(2):
            async with sessionmaker_for_name(SECONDARY)() as db:
                await db.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "error"


@app.get("/health")
async def health_check():
    # Pinned to the primary database. /health bypasses auth, so no account is
    # on the request and routed get_db would correctly refuse. It is also
    # Railway's deploy healthcheck, so a broken secondary must never fail it.
    try:
        async with async_session() as db:
            await db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "error"},
        )

    return {"status": "healthy", "database": "ok", "secondary": await _secondary_status()}


@app.get("/api/backup")
async def download_backup(db: AsyncSession = Depends(get_db)):
    """Export all categories and items as a JSON backup file."""
    cat_rows = await db.execute(select(Category).order_by(Category.id))
    item_rows = await db.execute(
        select(Item).options(selectinload(Item.category)).order_by(Item.id)
    )

    cats = [{"id": c.id, "name": c.name} for c in cat_rows.scalars().all()]
    items_list = [
        {
            "id": i.id,
            "name": i.name,
            "unit": i.unit,
            "current_quantity": i.current_quantity,
            "par_level": i.par_level,
            "category_id": i.category_id,
            "category_name": i.category.name if i.category else None,
            "created_at": i.created_at.isoformat(),
            "updated_at": i.updated_at.isoformat(),
        }
        for i in item_rows.scalars().all()
    ]

    backup = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "categories": cats,
        "items": items_list,
    }

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return JSONResponse(
        content=backup,
        headers={
            "Content-Disposition": f'attachment; filename="drogo-slice-backup-{timestamp}.json"'
        },
    )


@app.post("/api/reset")
async def reset_database(confirm: str = "", db: AsyncSession = Depends(get_db)):
    """Wipe all items and categories, reset ID sequences to 1.

    Requires ?confirm=RESET to guard against an accidental or leaked-credential call.
    """
    if confirm != "RESET":
        return JSONResponse(
            status_code=400,
            content={
                "status": "confirmation_required",
                "message": "Pass ?confirm=RESET to wipe all data.",
            },
        )
    await db.execute(text("DELETE FROM items"))
    await db.execute(text("DELETE FROM categories"))
    conn = await db.connection()
    if conn.dialect.name == "postgresql":
        await db.execute(text("ALTER SEQUENCE items_id_seq RESTART WITH 1"))
        await db.execute(text("ALTER SEQUENCE categories_id_seq RESTART WITH 1"))
    await db.commit()
    return {"status": "reset", "message": "All data wiped, IDs restart at 1"}


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
