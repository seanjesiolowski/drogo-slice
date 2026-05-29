from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.digest.brevo import send_email
from app.digest.runner import build_digest_html

router = APIRouter(prefix="/admin/digest", tags=["digest"])


@router.get("/preview", response_class=HTMLResponse)
async def preview_digest(db: AsyncSession = Depends(get_db)):
    """Render the weekly digest from live data and return it as HTML. Sends nothing."""
    html = await build_digest_html(db, date.today())
    return HTMLResponse(html)


@router.post("/send")
async def send_digest(db: AsyncSession = Depends(get_db)):
    """Render and actually send the digest via Brevo to DIGEST_TO_EMAILS."""
    today = date.today()
    html = await build_digest_html(db, today)

    missing = [
        name
        for name, value in (
            ("BREVO_API_KEY", settings.brevo_api_key),
            ("DIGEST_FROM_EMAIL", settings.digest_from_email),
            ("DIGEST_TO_EMAILS", settings.digest_to_emails),
        )
        if not value
    ]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing config: {', '.join(missing)}")

    to_list = [addr.strip() for addr in settings.digest_to_emails.split(",") if addr.strip()]
    result = send_email(
        api_key=settings.brevo_api_key,
        from_email=settings.digest_from_email,
        from_name=settings.digest_from_name,
        to_emails=to_list,
        subject=f"Drogo Slice — Weekly Digest ({today.isoformat()})",
        html=html,
    )
    return {"status": "sent", "to": to_list, "brevo": result}
