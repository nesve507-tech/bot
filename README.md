# Telegram Shop Bot (aiogram + MongoDB)

Production-ready Telegram bot to sell digital goods with auto-payment verification, auto-delivery, referral commission, and admin controls.

## Features

- User:
  - `/start` with referral support (`/start ref_<user_id>`)
  - Product listing + inline buy buttons
  - Create order + VietQR link
  - Payment check button
  - Auto delivery when paid
  - Dashboard (balance, orders, referral stats)
- Referral:
  - F1: 10%, F2: 5%, F3: 2%
- Admin:
  - Add product via FSM (`/add_product`)
  - Manual approve (`/approve ORDXXXX`)
  - Broadcast (`/broadcast`)
  - System statistics (`/stats`)
- System:
  - Background payment checker loop
  - Anti-spam middleware
  - Logging and Mongo indexes

## Project structure

```text
bot/
  main.py
  config.py
  db.py
  services/
    payment.py
    delivery.py
    referral.py
    anti_spam.py
  handlers/
    user.py
    admin.py
    dashboard.py
    payment.py
  keyboards/
    menu.py
```

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Configure environment:

```bash
cp .env.example .env
```

3. Edit `.env` with your real values.

4. Run bot:

```bash
python main.py
```

## Product stock format

When adding product stock in admin flow:

- Simple line: `account:password`
- Extended line: `account:password|note`

Each line is one deliverable item.

## Payment integration notes

`services/payment.py` includes API-ready hooks:

- `find_matching_transactions(...)` is where you integrate your bank/payment provider API.
- If `PAYMENT_MOCK_ENABLED=true`, pending orders auto-complete after `PAYMENT_MOCK_AFTER_SEC` seconds for testing.
