# NueGo Revenue Desk (frontend)

The screens for NueGo's pricing team, built with:
- React 18, Vite and TypeScript (strict)
- React Router, TanStack Query and Recharts
- Tailwind
- Vitest and Playwright for tests

Everything comes from the real API. There is no seed, mock or synthetic data in the app.

## Run it
```bash
# 1. backend (repo root)
source .venv/bin/activate && uvicorn app.main:app --port 8001

# 2. frontend
cd frontend && npm install
npm run dev                 # http://localhost:5173
```
The dev server forwards `/api/v1/*` to FastAPI and strips the prefix, because the backend has no `/api/v1` yet.
The target is `VITE_API_TARGET`, default `http://localhost:8001`.

## Scripts
| Command | What it does |
|---|---|
| `npm run lint` | ESLint and Prettier check |
| `npm run typecheck` | TypeScript, no output |
| `npm test` | Unit and component tests against a small test-only API stand-in in `src/test/` |
| `npm run e2e` | Playwright smoke tests against the real API. Read-only: it never records a decision |
| `npm run build` | Typecheck and production build into `dist/` |

## The screens
The sidebar has the pages, a red badge with the alert count, the time the data was last refreshed, and a
"Signed in as" menu.

1. **Services to review** (`/`)
   - The ranked list, worst first, with tabs Today, Tomorrow, Next 30 days and Already departed (real dates), and a route filter.
   - Clicking a row opens a **quick-look panel**: the gap to checkpoint, fare on sale, suggested fare, extra seats and margin change, cost floor and reasons.
   - **Open full review** or the **Review** button goes to the full page.
2. **Review page** (`/services/:id`)
   - Four headline numbers, then **Our suggestion**: the predicted fare as a range, the suggested fare inside the pricing rules, the rating, the nearest rival before and after ours, and the reasons.
   - The four buttons: Approve, Change fare, Reject and Something looks wrong. Each opens a dialog. A decision is only recorded; nothing is sent to a pricing system.
   - Five tabs:
     - **Seat pace:** the booking curve.
     - **Fare options:** price response and the what-if table.
     - **Competitors:** rival departures and fares.
     - **Money:** this service's P&L, plus the same weekday over the last 8 weeks.
     - **Past decisions:** with the outcome when one is loaded.
3. **Alerts** (`/warnings`)
   - Services behind pace with no decision. In-app only.
   - It opens on your own routes if you own any, and a "Show alerts for" menu picks a person or everyone.
4. **Money summary** (`/totals`): totals by corridor, date or coach type.
5. **Fare checker** (`/fare-predictor`): a fare range for a route, date, time, seats left and coach type.
6. **Pricing rules** (`/settings`): the rules, and who looks after each route. Only the admin can edit them.

## How it is put together
| Where | What |
|---|---|
| `src/App.tsx` | Routes, plus the query cache, user and toast providers |
| `src/api/client.ts` | One `fetch` wrapper. Sends `X-User-Id` and turns errors (401/403/404/409/422) into an `ApiError` with the API's message and per-field errors |
| `src/api/hooks.ts` | One TanStack Query hook per endpoint |
| `src/api/adapters.ts` | Turns the backend's flat fields (`expected_margin_low/mid/high`, ...) into `Range` shapes. The backend has no response models, so the raw shapes are written by hand from `app/*.py` |
| `src/pages/` | One file per screen |
| `src/components/` | Shared pieces, plus `desk/`, `service/`, `settings/` and `charts/` |
| `src/lib/` | Formatting, labels, fare-step checks, the signed-in user, and the default alert owner |

**State:**
- Server data lives in the query cache.
- The signed-in user is a React context, remembered in `localStorage`.
- Filters and tabs are in the URL.
- Form fields are local state.

## Rules the UI keeps
- Every predicted number is shown as `mid (low–high)` through `<RangeValue>`.
- Money goes through `formatINR` only (`₹1,23,456.50`). A missing value is `—`, never ₹0.
- Reason text is shown exactly as the API sends it.
- A fare that breaks a rule cannot be chosen.
- Rivals are shown as Rival A, Rival B and so on.

## Still needed from the backend
1. An `/api/v1` prefix (the dev proxy strips it today).
2. Real authentication. Today `X-User-Id` picks one of the placeholder users in `app/config.py`.
3. A real file of final seats and revenue after departure, loaded with `python -m scripts.load_outcomes`. Until then "outcome" shows "Not in the data".
4. The competitor file with AC and Sleeper columns (`competitor_preprocessed3.csv`), so the fare model can use the notebook's finer competitor level.
