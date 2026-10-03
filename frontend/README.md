# Pabrikers Frontend

This is the React single-page app for Pabrikers. It covers:
- the factory design canvas,
- the digital twin dashboard with a client-side shift simulation,
- the RL recommendations and analytics report,
- the AI chat panels.

See the [root README](../README.md) for full setup and the backend.

## Scripts

```bash
npm ci
cp .env.example .env     # set VITE_API_BASE_URL=http://localhost:8000/api for local dev
npm run dev              # Vite dev server on http://localhost:5173
npm run build            # type check (tsc -b) + production build to dist/
npm run lint             # ESLint
npm run preview          # serve the production build
```

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `/api` | Backend root; the client appends `/<VITE_API_VERSION>` |
| `VITE_API_VERSION` | `v1` | API version |
| `VITE_AUTH_TOKEN_KEY` | `auth_token` | localStorage key for a bearer token (auth is not implemented yet) |
| `VITE_APP_ENV` | `development` | `development`, `staging` or `production` |

In Docker, the app is built with `VITE_API_URL=/api` and served by nginx, which proxies `/api` to the backend (`deployment/nginx/nginx.conf`).

## Routes

Defined in `src/app/router/routes.tsx`:

| Path | Page | Purpose |
|---|---|---|
| `/`, `/landing` | `LandingPage` | Product landing page |
| `/login` | `LoginPage` | Placeholder login |
| `/intro` | `IntroPage` | Choose a factory template |
| `/live` (`/canvas` redirects here) | `CanvasPage` | Design the factory, auto-fill nodes, upload worker CVs, build the twin |
| `/agent` | `AgentPage` | Full-screen chat about the canvas and factory |
| `/parser` | `DocumentParserPage` | Polls the factory build and compatibility job |
| `/digital-twin?factoryId=` | `DigitalTwinPage` | Twin dashboard, live simulation and RL training trigger |
| `/dashboard` | `DashboardPage` | Saved projects (local drafts) |
| `/project/:projectId/recommendations` | `RecommendationsPage` | The three RL scenarios |
| `/project/:projectId/recommendation/:cardId` | `ExecutionPage` | Analytics report for one scenario (`scenario_0N` or `rec_N`) |

## Source layout

```
src/
├── app/            Providers (React Query, toast host) and router
├── api/            Axios client (error normalization) and endpoint constants
├── config/env.ts   Zod-validated environment variables
├── store/          Global Zustand stores: drafts, canvas UI, agent chat history, toasts
├── hooks/          Shared hooks (draft auto-sync)
├── pages/          Route components
├── components/     Layout (AppShell, Topbar) and shared canvas node / feedback components
└── features/
    ├── canvas/           Canvas board, side panels, autofill, templates, build pipeline (runFactoryBuild)
    ├── document-parser/  Build-status polling and parsed-data inspector
    ├── digital-twin/     Twin API, store and cards (assets, workers, job desks, compatibility matrix)
    ├── simulation/       Client-side shift simulation engine, runner hook, store and flowchart UI
    ├── optimization/     RL API, job polling, scenario mapping, report charts, RL flow animation, what-if chat
    ├── agent/            Chat API client and the Agent page chat
    └── project/          Project / draft types
```

## How the pieces connect

1. **Simulation.**
   - `features/simulation/api/simulationApi.ts` loads `GET /factories/{id}/simulation-config` and maps warehouse and output ordinals onto step ids.
   - It then runs each tick locally.
   - `useSimulationRunner` drives the loop. `simulationStore` keeps `data`, the last snapshot taken during working hours (`lastWorkingData`), and a `completed` status once the shift ends.
2. **Simulation → RL.**
   - When the store reaches `completed`, `DigitalTwinPage` calls `useRlOptimizationJob().start(...)` with the end state and the last working snapshot. This hits `POST /rl-optimization/{id}/optimize`.
   - The hook polls `/optimize/status` every 2 s while the job is queued or running.
   - When the job finishes, the hook invalidates the `rl-scenarios` query.
3. **Results.**
   - `useRlScenarios` loads `GET /rl-optimization/{id}/scenarios`.
   - `RecommendationsPage` lists the scenarios.
   - `ExecutionPage` maps each one with `mapRlScenarioToScenarioData` for the KPI cards and charts, and renders `RlFlowSimulation`.
   - When no RL result exists yet, the report falls back to sample data from `optimization/data/analyticsScenariosData.ts` and shows a "MENGGUNAKAN DATA CONTOH" (sample data) badge.
4. **Chat.**
   - `WhatIfPlayground` (report page) and `AgentChat` (`/agent`) send the question plus the stored history (`store/agentChat.ts`) to `POST /agents/chat`, using `features/agent/api/agentChatApi.ts`.
   - If the backend returns an error, both fall back to their local replies.
   - `AgentChat` answers canvas summary, help and navigation requests locally.
5. **Factory id resolution.**
   - `features/optimization/utils/resolveFactory.ts` turns a route id into a backend factory id. The route id can be a draft's project id or the factory id itself.
