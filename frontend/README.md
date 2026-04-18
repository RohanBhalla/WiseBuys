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

## Next steps (backend alignment)

- Point the UI at `VITE_API_URL` (FastAPI, default `http://localhost:8000`).
- Add CORS on the backend for `http://localhost:8080` if you call the API from the browser.
- Generate or hand-write a typed API client from `/openapi.json`.
