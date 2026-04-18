# WiseBuys Backend (FastAPI)

Backend for **WiseBuys** — a two-sided platform that uses Knot TransactionLink
data to drive brand discovery, loyalty, and values-based shopping.

This first slice ships **only the backend** with:

- Auth (JWT) and role-based access (`customer`, `vendor`, `admin`)
- Customer onboarding: primary focus, secondary focuses, rewards preferences
- Vendor application + admin vetting (`submitted` → `needs_info` / `approved` / `rejected`)
- Platform-controlled **value tags** (sustainability, ethically sourced, Black-owned, women-owned, local, …)
- Vendor catalog CRUD with **differentiator** + **key features**
- **Knot TransactionLink** adapter: server-side `Create Session`,
  webhooks (`AUTHENTICATED`, `NEW_TRANSACTIONS_AVAILABLE`,
  `UPDATED_TRANSACTIONS_AVAILABLE`, `ACCOUNT_LOGIN_REQUIRED`) with
  HMAC-SHA256 signature verification, cursor-paginated `Sync Transactions`,
  and normalized purchases / line items
- **Recommendation engine (rules-based v0)** ranking approved vendor
  products by overlap with the customer's primary/secondary focus tags
  and token similarity to recent Knot line items, with human-readable
  reasons + line-item evidence
- **Spending insights** aggregated per merchant from Knot purchases
- **Rewards ledger** (append-only `reward_events` with idempotent dedupe
  keys) with automatic earn rules:
  - +50 for completing values onboarding (primary + ≥1 secondary focus)
  - +100 for linking a new merchant via Knot (`AUTHENTICATED` webhook or
    first sync)
  - +1 point/dollar (capped at 250) for purchases at merchants whose
    name matches an approved vendor whose allowed tags overlap the
    customer's focuses
  - Admin adjustments / credits via `/api/admin/rewards/adjust`

The React frontend is the next milestone.

## Quick start

```bash
cd Backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

uvicorn app.main:app --reload
```

Then open [http://localhost:8000/docs](http://localhost:8000/docs) for Swagger UI.

The React app lives in `../frontend` (Vite dev server defaults to port **8080**; CORS is open for local development).

The first run creates the SQLite database, seeds the value tags, and (if
`BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` are set) creates the first
admin account.

## Tests

```bash
pytest
```

## Demo flow (Swagger or curl)

1. `POST /api/auth/register` (role `customer`) → token.
2. `GET /api/tags` → pick tag IDs.
3. `PATCH /api/customers/me` with `primary_focus_tag_id`, `secondary_focus_tag_ids`, `rewards_preferences`.
4. `POST /api/auth/register` (role `vendor`).
5. `POST /api/vendors/applications` with company info + `requested_tag_ids` + evidence URLs.
6. Login as bootstrapped admin → `GET /api/admin/applications`.
7. `POST /api/admin/applications/{id}/decision` with `status: approved` and `allowed_tag_ids`.
8. As the vendor, `POST /api/catalog/products` with `differentiator` and `key_features`.

### Knot TransactionLink (purchase data)

> Requires `KNOT_CLIENT_ID` / `KNOT_SECRET` in `.env`. In dev these live at
> `https://development.knotapi.com`.

1. As a customer, `POST /api/knot/sessions` with `{ "merchant_id": 19 }`. The
   response contains a `session_id` you pass to the Knot Web SDK on the
   client. WiseBuys uses `wb-user-{user.id}` as the `external_user_id`.
2. After the user completes link, Knot calls `POST /api/knot/webhooks` with
   `event = AUTHENTICATED`, then `NEW_TRANSACTIONS_AVAILABLE`. WiseBuys
   verifies the `Knot-Signature` header (HMAC-SHA256, base64) and persists the
   merchant account / triggers a sync.
3. `POST /api/knot/sync { "merchant_id": 19 }` manually paginates through
   `/transactions/sync` (cursor-based) and upserts `knot_purchases` +
   `knot_line_items`.
4. `GET /api/knot/purchases` lists the customer's normalized purchase history.
5. `GET /api/knot/merchant-accounts` shows linked merchants and last sync
   status (`connected` / `disconnected`).

### Recommendations & insights

- `GET /api/recommendations/me?limit=10` — ranked vendor products with
  human-readable `reasons` and `evidence_line_item_ids` referencing the
  Knot purchases that drove the score.
- `GET /api/insights/spending` — per-merchant totals (`purchase_count`,
  `total_spent`, `currency`) computed from `knot_purchases`.

### Rewards

- `GET /api/rewards/me` → `{ balance, events[] }` (append-only ledger).
- `POST /api/rewards/me/recompute` re-sweeps recent purchases for
  aligned-purchase rewards (idempotent, safe to call repeatedly).
- `POST /api/admin/rewards/adjust` (admin) credits/debits a user with a
  `dedupe_key` to prevent double-application.

## Database

- Default: SQLite at `wisebuys.db` (zero config).
- For Postgres set `DATABASE_URL=postgresql+psycopg://...` in `.env`.
- Alembic is wired (`alembic/`); the app also calls `Base.metadata.create_all` on
  startup so SQLite dev works without running migrations.

## Project structure

```text
Backend/
  app/
    config.py        # Pydantic Settings (env)
    database.py      # SQLAlchemy engine, Base, get_db
    deps.py          # Auth/role dependencies
    security.py      # Password hashing + JWT
    main.py          # App factory + lifespan (create_all + seeds)
    models/          # SQLAlchemy models (incl. knot_*)
    schemas/         # Pydantic v2 schemas
    routers/         # FastAPI routers (auth, tags, customers, vendors, admin, catalog, knot, knot_webhooks)
    knot/            # Knot HTTP client + webhook signature helper
    services/        # knot_sync (cursor pagination, purchase upserts)
    seeds/           # Default tags + bootstrap admin
  alembic/           # Migration scaffolding
  tests/             # Pytest end-to-end coverage
```

## Roadmap

See [`/Users/ronballer/.cursor/plans/knot-driven_commerce_platform_b2062d7e.plan.md`](../../../.cursor/plans/knot-driven_commerce_platform_b2062d7e.plan.md)
(plan document) for Knot adapter, recommendation engine, rewards, and React UI.
