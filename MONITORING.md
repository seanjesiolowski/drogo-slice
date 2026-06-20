# Monitoring

## Health endpoint

`GET /health` (no auth required) checks database connectivity:

- `200 {"status": "healthy", "database": "ok"}` — app and DB reachable
- `503 {"status": "unhealthy", "database": "error"}` — DB unreachable / pool exhausted

Railway uses this at **deploy time** to gate new builds (see `railway.json`). It does
**not** poll continuously at runtime, so a DB outage hours after a healthy deploy goes
unnoticed by Railway. An external uptime monitor covers that gap.

## External uptime monitor (manual one-time setup)

Use any free uptime service (UptimeRobot, Better Stack, Cron-Monitor, etc.).

1. **Create an HTTP(S) monitor** pointed at:
   `https://<your-railway-domain>/health`
   (Railway dashboard → service → Settings → Networking → public domain.)
2. **Interval:** every 1–5 minutes.
3. **Up condition:** HTTP status `200`. Treat `503` (and timeouts) as **down** —
   `/health` deliberately returns `503` when the database is unreachable.
   If the tool supports it, also assert the body contains `"database": "ok"`.
4. **Alerts:** email/SMS/Slack to yourself. Alert after 2 consecutive failures to
   avoid flapping on a single blip.
5. **No credentials needed** — `/health` is exempt from Basic Auth.

## What this catches

- App down / crash-looping (no response or non-200)
- Database down or connection pool exhausted (503 from `/health`)

## What it does NOT catch

- Application errors that still return 200 (use error tracking, e.g. Sentry)
- Failed weekly digest sends (`app/digest/runner.py` is a separate scheduled job)
