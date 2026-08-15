# Design Factory Control Center

The Human Control Center for the autonomous Etsy wall-art design factory:
a Next.js (App Router) frontend for the FastAPI backend in `../backend`.

Four screens, matching what the backend actually exposes -- nothing here
calls an endpoint that doesn't exist, and nothing shown is fabricated
client-side:

- **Dashboard** (`/`) -- today's headline KPIs (`GET /api/dashboard/today`)
  and a form to trigger a `DailyProductionPlan`
  (`POST /api/production/plan`).
- **Approval Queue** (`/candidates`) -- the candidate image grid
  (`GET /api/candidates`), with single and multi-select bulk
  approve/reject (`POST /api/candidates/{id}/approval`,
  `POST /api/candidates/bulk-approval`).
- **Market Signals** (`/market-signals`) -- recent real market-intelligence
  signals and today's research plan
  (`GET /api/market-intelligence/signals`,
  `GET /api/market-intelligence/research-queries`), read-only.
- **Getvela Export** (`/getvela`) -- how many approved designs are
  waiting, and a button that exports them as a CSV matching the real
  Getvela "Import new listings" template
  (`POST /api/getvela/export`, `GET /api/getvela/exports` for history) --
  downloads the file for you to upload through Getvela's own Import
  button. See `../docs/ROADMAP.md` "Getvela CSV export" for why this
  exists instead of a direct Etsy API integration.

## Running locally

```bash
npm install
cp .env.example .env.local   # point NEXT_PUBLIC_API_BASE_URL at your backend
npm run dev
```

Requires the backend running separately (see `../backend/README.md`) with
`FRONTEND_ORIGIN=http://localhost:3000` (the default) so its CORS
middleware allows this app's origin.

## What this is not

This is a functional MVP of the Control Center described in
`../docs/ARCHITECTURE.md` and `../docs/SYSTEM_VISION.md`, not the full
keyboard-driven, live-polling version the mission brief describes in
detail (e.g. keyboard shortcuts for bulk actions, live KPI polling/
websockets, per-candidate refinement actions beyond approve/reject). See
`../docs/ROADMAP.md` for what's implemented versus deferred.
