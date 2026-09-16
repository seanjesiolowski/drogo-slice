# Drogo Slice

Coffee shop inventory tracker built with FastAPI and PostgreSQL

***Currently in production ( internal tooling ) at [Saint Drogo's](https://saintdrogoscoffee.com) in Lowville, NY***

![alt text](image.png)


## Running locally (Docker installed and running)

```bash
docker compose up --build
```

App runs at `http://localhost:8000`. API docs at `/docs`.

## Development workflow

The Docker setup supports **hot-reloading** — edit code in VS Code and changes appear automatically without rebuilding.

1. Start the stack once: `docker compose up --build`
2. Edit code in VS Code — files sync into the container via a volume mount
3. Uvicorn detects changes and auto-restarts the API
4. Only rebuild (`docker compose up --build`) when you change `requirements.txt`

For subsequent sessions, just run `docker compose up` (no `--build` needed).

## Testing

```bash
docker compose exec api pytest
```

## Sandbox environment

The sandbox is a second login on this same app, backed by its own Postgres database.
There is one app service, not two — the second login just points at a different
database, so nothing done under it can reach the production inventory at Saint
Drogo's. Isolation is physical (separate databases), not a permissions check.


## Signing in and switching accounts

Pages are behind a login form at `/login`, and a successful sign-in sets a
signed cookie that lasts a year. "Log off" in the header clears it and returns
you to the form, which is how you switch between the production login and the
sandbox one without quitting the browser. When you are signed in as the
sandbox, a **Sandbox** badge sits in the header — production is the everyday
case and stays unlabelled.

Set `SESSION_SECRET` to any long random string to keep people signed in across
deploys. Left blank, the app generates one at boot, so every restart signs
everyone out.

The API still accepts HTTP Basic auth, so `curl`, scripts and `/docs` keep
working unchanged:

```bash
curl -u "$ADMIN_USERNAME:$ADMIN_PASSWORD" http://localhost:8000/api/items/
```

Page loads deliberately ignore Basic credentials and use the cookie only.
Browsers replay an answered Basic prompt forever, so honouring it on page loads
would undo every log-off — clear the cookie, and the next page load would sign
you straight back in. One consequence worth knowing: logging off ends the
browser session, but it does not revoke the password. Credentials already
cached in a browser can still reach `/api/...` directly until that browser is
closed.
