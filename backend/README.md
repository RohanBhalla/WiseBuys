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
- **Recommendation engine (hybrid on Postgres)** — with `DATABASE_URL`
  pointing at **Postgres + pgvector** and `GEMINI_API_KEY` set, ranked
  products use **Gemini `gemini-embedding-001`** (768-d, asymmetric
  `RETRIEVAL_DOCUMENT` / `RETRIEVAL_QUERY`) plus tag overlap, category
  heuristics, token overlap evidence, and optional recency. On **SQLite**
  (default dev), the same API falls back to the **rules-only v0** engine.
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

The React app lives in `../frontend` (Vite dev server defaults to port **8080**). CORS allows `http://localhost:8080` and `http://127.0.0.1:8080` with credentials enabled for future cookie-based auth.

**Knot webhooks (local):** Knot must POST to a public URL. Expose the API
with `ngrok http 8000`, then set the webhook in the Knot customer dashboard
([Webhooks settings](https://dashboard.knotapi.com/webhooks)) to
`https://<your-ngrok-host>/api/knot/webhooks` for the **development**
environment. The same `KNOT_SECRET` is used to verify the
`Knot-Signature` HMAC-SHA256 header (per
[Webhook Verification](https://docs.knotapi.com/webhooks#webhook-verification)).
Knot retries non-2xx responses up to twice, so the receiver always 200s
and logs/queues failures internally.

In production set `KNOT_WEBHOOK_REQUIRE_SIGNATURE=true` so unsigned
requests are rejected. Knot's webhook traffic comes from `35.232.249.218`
(allowlist if needed).

The first run creates the SQLite database, seeds the value tags, and (if
`BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` are set) creates the first
admin account.

### Demo vendors (Knot + recommendation testing)

Set **`SEED_DEMO_VENDORS=true`** in `.env` and restart Uvicorn. On startup the
API inserts **four** pre-approved vendors with **published** SKUs (see
[`app/seeds/demo_vendors.py`](app/seeds/demo_vendors.py)). Product names and
`category` values (`food-delivery`, `apparel`, `everyday`) are chosen to score
against real **Transaction Link** history (e.g. DoorDash → `food-delivery` in
[`app/services/recommendations.py`](app/services/recommendations.py)) via token
overlap and category match.

| Vendor | Sign-in email | Password | Allowed tags |
| --- | --- | --- | --- |
| GreenBasket Foods | `demo.v.greenbasket@wisebuys.example.com` | `WiseBuysDemoVendor1!` | sustainability, local |
| Roots & Marrow Supply | `demo.v.rootsandmarrow@wisebuys.example.com` | same | black_owned, ethically_sourced |
| Sunrise Roasters Collective | `demo.v.sunriseroasters@wisebuys.example.com` | same | women_owned, local |
| Ethical Essentials Refill Co. | `demo.v.ethicalessentials@wisebuys.example.com` | same | fair_trade, sustainability |

The seed is **idempotent** (skips if `demo.v.greenbasket@wisebuys.example.com`
already exists). To re-run from scratch, delete your local SQLite file and
start again.

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

1. `GET /api/knot/merchants` (customer JWT) calls Knot **POST /merchant/list**
   with `type: transaction_link` and `platform: web` (List Merchants) so the UI
   can populate merchant pickers / Knot SDK `merchantIds` (Amazon, Walmart,
   DoorDash, etc., depending on your Knot product access).
2. As a customer, `POST /api/knot/sessions` with `{ "merchant_id": <id> }` (e.g.
   `19` for DoorDash in quickstart docs). The
   response contains a `session_id` you pass to the Knot Web SDK on the
   client. WiseBuys uses `wb-user-{user.id}` as the `external_user_id`.
3. After the user completes link, Knot calls `POST /api/knot/webhooks` with
   `event = AUTHENTICATED`, then `NEW_TRANSACTIONS_AVAILABLE`. WiseBuys
   verifies the `Knot-Signature` header (HMAC-SHA256, base64) and persists the
   merchant account / triggers a sync. `UPDATED_TRANSACTIONS_AVAILABLE` is
   handled by calling `Get Transaction By ID` for each id in the payload's
   `data.transactions` array (per
   [docs](https://docs.knotapi.com/transaction-link/webhook-events/updated-transactions-available)).
   `MERCHANT_STATUS_UPDATE` and `ACCOUNT_LOGIN_REQUIRED` are also handled.
4. `POST /api/knot/sync { "merchant_id": 19 }` manually paginates through
   `/transactions/sync` (cursor-based) and upserts `knot_purchases` +
   `knot_line_items`.
5. `GET /api/knot/purchases` lists the customer's normalized purchase history.
6. `GET /api/knot/merchant-accounts` shows linked merchants and last sync
   status (`connected` / `disconnected`).

#### Dev-only webhook simulation

When `KNOT_ENVIRONMENT=development` and
`KNOT_DEV_SIMULATION_ENABLED=true` (default), the API exposes two
customer-auth helpers that hit Knot's
[`/development/accounts/link`](https://docs.knotapi.com/api-reference/development/link-account)
and `/development/accounts/disconnect` endpoints so your webhook
listener actually fires without invoking the SDK:

- `POST /api/knot/dev/simulate-link` `{ "merchant_id": 19, "new_transactions": true, "updated_transactions": false }`
  → Knot fires `AUTHENTICATED` then `NEW_TRANSACTIONS_AVAILABLE` (and
  `UPDATED_TRANSACTIONS_AVAILABLE` if requested) at your subscribed
  webhook URL.
- `POST /api/knot/dev/simulate-disconnect` `{ "merchant_id": 19 }`
  → Knot fires `ACCOUNT_LOGIN_REQUIRED`.

These let you exercise the full webhook → sync pipeline against the
**development** environment without needing to log in via the Knot SDK.

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

### Vector embeddings (Gemini + pgvector)

**Postgres (recommended for production ANN index):**

1. Create DB and enable extension: `CREATE EXTENSION IF NOT EXISTS vector;`
2. Run migrations: `alembic upgrade head` (adds `embedding` / `embedding_signature` /
   `embedded_at` on `vendor_products` and `customer_profiles`).

**SQLite (local dev):** embedding columns are added on startup when missing; no Alembic step.

**All backends:** set `GEMINI_API_KEY` in `.env`. After Knot sync or catalog changes, vectors
refresh automatically; to backfill published products + all customer profiles once:

```bash
PYTHONPATH=. python -m app.scripts.embed_backfill
```

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
