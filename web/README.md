# FastAPI Admin Dashboard

Production-style web dashboard for the Telegram shop bot data.

## Features

- Admin auth by secret key (`WEB_ADMIN_KEY`)
- Optional simple token login (`/tg-login?token=...`)
- Dark theme UI with sidebar
- Pages:
  - `/dashboard`: overview + revenue/orders charts
  - `/orders`: recent orders + filters + search
  - `/users`: users + balance + F1 count
  - `/analytics`: top referrers
- Protected API routes:
  - `/api/stats`
  - `/api/orders`
  - `/api/users`
  - `/api/revenue`

## Run

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Set environment values (`.env`):

- `MONGO_URI`
- `MONGO_DB_NAME` (optional, default: `telegram_shop`)
- `WEB_ADMIN_KEY`
- `WEB_SESSION_SECRET`

3. Start server:

```bash
uvicorn web.main:app --reload
```

4. Open:

- `http://127.0.0.1:8000/login`

## Security notes

- All dashboard pages and `/api/*` endpoints are protected.
- API can be authenticated by browser session cookie or `X-Admin-Key` header.
