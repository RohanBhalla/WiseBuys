# WiseBuys frontend

TanStack Start + React + Vite + Tailwind (Lovable-style template). This app will be wired to the FastAPI backend in `../Backend`.

## Prerequisites

- **Node.js 22 LTS** is recommended (see `.nvmrc`). With **Node 25+**, the `sharp` postinstall may fail because prebuilt binaries are not always available yet; use the workaround below.

## First-time setup on this machine

```bash
cd frontend
cp .env.example .env
```

Install dependencies:

```bash
npm install
```

If `npm install` fails on `sharp` (building from source), either switch to Node 22 (`nvm install 22 && nvm use`) or install without lifecycle scripts (native deps may be incomplete):

```bash
npm install --ignore-scripts
```

## Run the dev server

```bash
npm run dev
```

Open [http://localhost:8080](http://localhost:8080) (default port for this template).

Run the API in another terminal so later integration works:

```bash
cd ../Backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

## Other scripts

| Command        | Description        |
| -------------- | ------------------ |
| `npm run build` | Production build |
| `npm run preview` | Preview production build |
| `npm run lint`  | ESLint             |
| `npm run format` | Prettier          |

## Demo vendors (optional backend seed)

With **`SEED_DEMO_VENDORS=true`** in the Backend `.env`, the API seeds four approved brands (logins in [`Backend/README.md`](../Backend/README.md) — shared password `WiseBuysDemoVendor1!`). Use them alongside your customer account after **Knot sync** to see live recommendations.

## Backend integration (implemented)

- **Auth**: `/login` — JWT stored in `localStorage` (`wb_auth`). Customer vs vendor registration.
- **Customer**: `/onboarding` (values + rewards prefs), `/dashboard` (recommendations, rewards, spending, tag toggles), `/dashboard/connect` (Knot Web SDK + sync).
- **Vendor**: `/vendor` (status), `/vendor/apply`, `/vendor/catalog` (+ new/edit routes).
- **API**: Browser calls use relative `/api/...` so the Vite dev **proxy** forwards to `VITE_API_URL` (avoids CORS during local dev). SSR uses `VITE_API_URL` as an absolute base.
- **Knot**: Set `VITE_KNOT_CLIENT_ID` and `VITE_KNOT_ENVIRONMENT` in `.env`. In the Knot dashboard, allowlist `http://localhost:8080` and set the **webhook** URL to your reachable FastAPI host, e.g. `https://<ngrok-id>.ngrok-free.app/api/knot/webhooks` while `uvicorn` runs behind ngrok (`ngrok http 8000`).

## Manual E2E check

1. Backend: `uvicorn app.main:app --reload` from `Backend/`. Frontend: `npm run dev` from `frontend/`.
2. Register a **customer** → complete `/onboarding` → confirm points on `/dashboard` → `/dashboard/connect` to link (Knot sandbox) and sync.
3. Register a **vendor** → `/vendor/apply` → approve in Swagger `POST /api/admin/applications/{id}/decision` with `allowed_tag_ids` → `/vendor/catalog` CRUD.
