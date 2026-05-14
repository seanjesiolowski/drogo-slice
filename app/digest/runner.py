from datetime import date

from app.config import settings
from app.digest.brevo import send_email
from app.digest.render import render_digest

_FAKE_ITEMS = [
    {"name": "Espresso beans", "category": "Coffee", "current": 1.2, "par": 5.0, "unit": "kg", "status": "critical"},
    {"name": "Oat milk", "category": "Dairy alt", "current": 4, "par": 12, "unit": "cartons", "status": "critical"},
    {"name": "Sugar packets", "category": "Sweeteners", "current": 80, "par": 200, "unit": "ct", "status": "low"},
    {"name": "12oz cups", "category": "Supplies", "current": 150, "par": 500, "unit": "ct", "status": "low"},
    {"name": "Vanilla syrup", "category": "Syrups", "current": 2, "par": 4, "unit": "bottles", "status": "low"},
]

_FAKE_TOTALS = {"critical": 2, "low": 3, "ok": 47}


def main() -> None:
    if not settings.brevo_api_key:
        raise SystemExit("BREVO_API_KEY is not set")
    if not settings.digest_from_email:
        raise SystemExit("DIGEST_FROM_EMAIL is not set")
    if not settings.digest_to_emails:
        raise SystemExit("DIGEST_TO_EMAILS is not set")

    to_list = [addr.strip() for addr in settings.digest_to_emails.split(",") if addr.strip()]
    today = date.today()

    html = render_digest(week_of=today, items=_FAKE_ITEMS, totals=_FAKE_TOTALS)

    result = send_email(
        api_key=settings.brevo_api_key,
        from_email=settings.digest_from_email,
        from_name=settings.digest_from_name,
        to_emails=to_list,
        subject=f"Drogo Slice — Weekly Digest ({today.isoformat()})",
        html=html,
    )
    print(f"Sent. Brevo response: {result}")


if __name__ == "__main__":
    main()
