import httpx

_BREVO_URL = "https://api.brevo.com/v3/smtp/email"


def send_email(
    *,
    api_key: str,
    from_email: str,
    from_name: str,
    to_emails: list[str],
    subject: str,
    html: str,
) -> dict:
    payload = {
        "sender": {"name": from_name, "email": from_email},
        "to": [{"email": addr} for addr in to_emails],
        "subject": subject,
        "htmlContent": html,
    }
    headers = {"api-key": api_key, "content-type": "application/json", "accept": "application/json"}

    resp = httpx.post(_BREVO_URL, json=payload, headers=headers, timeout=30.0)
    resp.raise_for_status()
    return resp.json()
