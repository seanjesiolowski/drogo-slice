import argparse
import asyncio
from datetime import date

from sqlalchemy import Float, case, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.digest.brevo import send_email
from app.digest.render import render_digest
from app.models.category import Category
from app.models.item import Item
from app.models.storage_class import StorageClass

_DEFAULT_LOW = 0.99
_DEFAULT_CRITICAL = 0.5


def _status_expr():
    low_t = func.coalesce(StorageClass.low_threshold, literal(_DEFAULT_LOW, Float))
    critical_t = func.coalesce(StorageClass.critical_threshold, literal(_DEFAULT_CRITICAL, Float))
    return case(
        (Item.current_quantity <= Item.par_level * critical_t, "critical"),
        (Item.current_quantity <= Item.par_level * low_t, "low"),
        else_="ok",
    )


async def _fetch_attention_items(db: AsyncSession) -> list[dict]:
    status = _status_expr()
    query = (
        select(
            Item.name,
            Item.unit,
            Item.current_quantity,
            Item.par_level,
            Category.name.label("category_name"),
            status.label("status"),
        )
        .join(Category, Item.category_id == Category.id)
        .outerjoin(StorageClass, Item.storage_class_id == StorageClass.id)
        .where(status.in_(["critical", "low"]))
        .order_by(status, Item.name)
    )
    result = await db.execute(query)
    return [
        {
            "name": row.name,
            "category": row.category_name,
            "current": row.current_quantity,
            "par": row.par_level,
            "unit": row.unit,
            "status": row.status,
        }
        for row in result
    ]


async def _fetch_totals(db: AsyncSession) -> dict[str, int]:
    status = _status_expr()
    query = (
        select(status.label("status"), func.count().label("n"))
        .select_from(Item)
        .outerjoin(StorageClass, Item.storage_class_id == StorageClass.id)
        .group_by(status)
    )
    result = await db.execute(query)
    totals = {"critical": 0, "low": 0, "ok": 0}
    for row in result:
        totals[row.status] = row.n
    return totals


async def build_digest_html(db: AsyncSession, today: date) -> str:
    """Render the digest HTML from an existing DB session. Sends nothing."""
    items = await _fetch_attention_items(db)
    totals = await _fetch_totals(db)
    return render_digest(week_of=today, items=items, totals=totals)


async def _build_digest(today: date) -> str:
    async with async_session() as db:
        return await build_digest_html(db, today)


async def _run(dry_run: bool) -> None:
    today = date.today()
    html = await _build_digest(today)

    if dry_run:
        print(html)
        return

    if not settings.brevo_api_key:
        raise SystemExit("BREVO_API_KEY is not set")
    if not settings.digest_from_email:
        raise SystemExit("DIGEST_FROM_EMAIL is not set")
    if not settings.digest_to_emails:
        raise SystemExit("DIGEST_TO_EMAILS is not set")

    to_list = [addr.strip() for addr in settings.digest_to_emails.split(",") if addr.strip()]

    result = send_email(
        api_key=settings.brevo_api_key,
        from_email=settings.digest_from_email,
        from_name=settings.digest_from_name,
        to_emails=to_list,
        subject=f"Drogo Slice — Weekly Digest ({today.isoformat()})",
        html=html,
    )
    print(f"Sent. Brevo response: {result}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Send the weekly inventory digest.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render the HTML to stdout instead of sending via Brevo.",
    )
    args = parser.parse_args()
    asyncio.run(_run(args.dry_run))


if __name__ == "__main__":
    main()
