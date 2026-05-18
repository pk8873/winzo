# Real-Money Prediction & Card Gaming Platform

Modern Flask webapp with wallet, OTP login, prediction & card games, realtime
SocketIO timers, Razorpay payments, withdrawals, full admin control, anti-fraud,
and Render-ready deployment.

> ⚠️ Real-money gaming is regulated. Ensure you have the required licenses for
> your jurisdiction before going live. This codebase is an engineering template.

## Quickstart (localhost)

```bash
python -m venv venv
source venv/bin/activate         # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Open http://localhost:5000

Default admin (configure in `.env`):
- email: `admin@local.test`
- password: `Admin@12345`

OTP codes are printed to the server console in dev mode.

## With PostgreSQL + Redis (optional locally)

```bash
export DATABASE_URL=postgresql://user:pass@localhost:5432/gaming
export REDIS_URL=redis://localhost:6379/0
flask --app app:create_app db upgrade   # if using migrations
python app.py
```

## Deploy to Render

1. Push this repo to GitHub.
2. On Render → New → Blueprint → select the repo. Render reads `render.yaml`
   and provisions Postgres + Redis automatically.
3. Set secrets in the Render dashboard: `ADMIN_PASSWORD`, `RAZORPAY_KEY_ID`,
   `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`.
4. Deploy. The first boot creates tables and bootstraps the admin user.

## Architecture

- **Flask** app factory with blueprints per domain (auth, wallet, games,
  prediction, cards, payments, withdraw, admin, referrals, api,
  notifications, security).
- **SQLAlchemy** models in `app/models.py` (users, wallets, ledger, games,
  rounds, deposits, withdrawals, referrals, admin logs, fraud flags).
- **Wallet ledger**: balances are *derived* from `wallet_transactions`. Code
  never mutates balance directly — every change is a row with type, amount,
  reference, and idempotency key.
- **RNG**: `secrets.SystemRandom()` only. `random` is forbidden.
- **Realtime**: Flask-SocketIO with Redis message queue when `REDIS_URL` set.
- **Anti-fraud**: rate limiting (Flask-Limiter), IP capture, multi-account &
  abnormal-win detectors, admin fraud flags table.
- **Security**: CSRF (Flask-WTF), bcrypt-style password hashing (Werkzeug),
  HTTPOnly + SameSite cookies, brute-force lockout, audit logs.
- **Payments**: Razorpay order creation + webhook signature verification +
  idempotent ledger credit. Cashfree stub follows the same pattern.

## Game catalog (admin can enable/disable any)

- Color Prediction (Red / Green / Violet) — 60s rounds
- Number Prediction (0–9) — 60s rounds
- Card Prediction (Red/Black, Suit, Higher/Lower) — instant
- Flash Cards (Winzo-style quick rounds) — 30s rounds

All games respect a per-game **RTP** the admin controls.

## File map

See the project tree in this repo. Every blueprint has its own `routes.py`
plus its templates under `app/templates/<area>/`.
