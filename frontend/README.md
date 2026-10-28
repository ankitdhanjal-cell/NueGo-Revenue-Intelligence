# NueGo Revenue Desk (frontend)

React 18 + Vite + TypeScript (strict), React Router, TanStack Query, Recharts, Tailwind, Vitest, Playwright.
Everything comes from the real API. There is no seed, mock or synthetic data in the app.

## Run it
```bash
# 1. backend (repo root)
source .venv/bin/activate && uvicorn app.main:app --port 8001

# 2. frontend
cd frontend && npm install
npm run dev                 # http://localhost:5173
```
The dev server forwards `/api/v1/*` to FastAPI (`VITE_API_TARGET`, default `http://localhost:8001`) and strips the prefix,
because the backend has no `/api/v1` yet.

## Scripts
`npm run lint` · `npm run typecheck` · `npm test` (unit and component tests; they use a tiny test-only API stand-in in `src/test/`) ·
`npm run e2e` (Playwright, needs the backend running; read-only, writes nothing) · `npm run build`.

## The journey
1. **Services to review** (`/`): a short list, worst first. Tabs are real dates: Today, Tomorrow, Next 30 days, Already departed. The data is a historical sample (Jan 2023 to Dec 2026), so Today and Tomorrow are often empty. Each row shows the departure date and when the seats were counted.
2. **Review page** (`/services/:id`): four numbers, then **Our suggestion**: the fare predicted by the decision-tree model in `notebooks/decision_tree.ipynb` (as a range), the suggested fare inside the pricing rules, why, and Approve / Change fare / Reject / Something looks wrong. More detail is in five tabs.
3. A decision is only recorded in the `decisions` table. Nothing is pushed to a pricing system.

Other pages: Alerts, Money summary, Fare checker (notebook model), Pricing rules (editable by an admin only).

## Where the data comes from
- `src/api/client.ts`: one `fetch` wrapper. Sends `X-User-Id`; turns 401/403/404/409/422 into an `ApiError` with the API's message and per-field errors.
- `src/api/adapters.ts`: turns the backend's flat fields (`expected_margin_low/mid/high`, ...) into `Range` shapes. The backend defines no response models, so the raw shapes are written by hand from `app/*.py`.
- `src/api/hooks.ts`: one hook per resource. Routes and users also come from the API (`/routes`, `/users`).

## Rules the UI keeps
Every predicted number is `mid (low–high)` through `<RangeValue>`. Money goes through `formatINR` only (`₹1,23,456.50`; missing is `—`, never ₹0). Reason text is shown as sent. A blocked fare cannot be chosen.

## Still needed from the backend
1. An `/api/v1` prefix (the dev proxy strips it today).
2. Real authentication (today `X-User-Id` picks one of the placeholder users in `app/config.py`).
3. Final seats and revenue after departure, to fill "outcome" in past decisions (the data has none, so it shows "Not in the data").
4. The competitor file with AC and Sleeper columns (`competitor_preprocessed3.csv`), so the fare model can use the notebook's first, finer competitor level.
