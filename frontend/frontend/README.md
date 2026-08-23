frontend/
├── public/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── vite-env.d.ts
│   │
│   ├── app/                        # setup level aplikasi (bukan domain)
│   │   ├── providers/
│   │   │   ├── QueryProvider.tsx
│   │   │   ├── ThemeProvider.tsx
│   │   │   └── AppProviders.tsx     # gabungkan semua provider
│   │   └── router/
│   │       ├── routes.tsx
│   │       └── ProtectedRoute.tsx
│   │
│   ├── config/
│   │   ├── env.ts                  # validasi env vars (zod), mirror core/config.py
│   │   └── constants.ts
│   │
│   ├── api/                        # infrastruktur komunikasi, mirror services/ backend
│   │   ├── client.ts                # axios instance + interceptors (auth, error)
│   │   ├── endpoints.ts             # konstanta URL versi API (v1)
│   │   └── websocket.ts             # koneksi WS ke simulation engine
│   │
│   ├── features/                   # domain-driven, 1 folder = 1 domain (mirror modules/)
│   │   │
│   │   ├── digital-twin/            # assets, workers, job_desks, compatibility matrix
│   │   │   ├── components/
│   │   │   │   ├── AssetCard.tsx
│   │   │   │   ├── WorkerCard.tsx
│   │   │   │   ├── JobDeskTable.tsx
│   │   │   │   └── CompatibilityMatrix.tsx
│   │   │   ├── hooks/
│   │   │   │   ├── useDigitalTwin.ts
│   │   │   │   └── useCompatibilityMatrix.ts
│   │   │   ├── api/
│   │   │   │   └── digitalTwinApi.ts
│   │   │   ├── store/
│   │   │   │   └── digitalTwinStore.ts
│   │   │   ├── types/
│   │   │   │   └── digitalTwin.types.ts
│   │   │   ├── utils/
│   │   │   │   └── normalizeAssetData.ts
│   │   │   └── index.ts             # barrel export
│   │   │
│   │   ├── simulation/              # kontrol & monitoring RL (PPO, reward, action mask)
│   │   │   ├── components/
│   │   │   │   ├── SimulationControls.tsx
│   │   │   │   ├── RewardChart.tsx
│   │   │   │   ├── ThroughputBottleneckChart.tsx
│   │   │   │   ├── ActionMaskViewer.tsx
│   │   │   │   └── EpisodeTimeline.tsx
│   │   │   ├── hooks/
│   │   │   │   ├── useSimulationSocket.ts   # subscribe real-time observation_space
│   │   │   │   └── useSimulationState.ts
│   │   │   ├── api/
│   │   │   │   └── simulationApi.ts
│   │   │   ├── store/
│   │   │   │   └── simulationStore.ts       # status running/paused, current episode
│   │   │   └── types/
│   │   │       └── simulation.types.ts
│   │   │
│   │   ├── human-factors/           # kelelahan, stres, Yerkes-Dodson, RULA/REBA
│   │   │   ├── components/
│   │   │   │   ├── FatigueGauge.tsx
│   │   │   │   ├── StressPerformanceCurve.tsx
│   │   │   │   ├── ErgonomicsPanel.tsx
│   │   │   │   └── NasaTlxRadar.tsx
│   │   │   ├── hooks/
│   │   │   ├── api/
│   │   │   └── types/
│   │   │
│   │   ├── explainability/          # metric_derivation_reasoning, llm_reasoning
│   │   │   ├── components/
│   │   │   │   ├── ReasoningPanel.tsx
│   │   │   │   └── MetricDerivationCard.tsx
│   │   │   ├── api/
│   │   │   └── types/
│   │   │
│   │   ├── document-parser/         # upload dokumen -> LLM parser -> JSON digital twin
│   │   │   ├── components/
│   │   │   │   ├── UploadDropzone.tsx
│   │   │   │   └── ParseStatusBanner.tsx
│   │   │   ├── hooks/
│   │   │   ├── api/
│   │   │   └── types/
│   │   │
│   │   └── auth/
│   │       ├── components/
│   │       │   ├── LoginForm.tsx
│   │       │   └── AuthGuard.tsx
│   │       ├── hooks/
│   │       │   └── useAuth.ts
│   │       ├── api/
│   │       │   └── authApi.ts
│   │       └── store/
│   │           └── authStore.ts
│   │
│   ├── pages/                      # routing-level, compose beberapa feature
│   │   ├── DashboardPage.tsx
│   │   ├── DigitalTwinPage.tsx
│   │   ├── SimulationPage.tsx
│   │   ├── HumanFactorsPage.tsx
│   │   ├── LoginPage.tsx
│   │   └── NotFoundPage.tsx
│   │
│   ├── components/                 # shared UI, tidak spesifik domain
│   │   ├── ui/                      # shadcn/ui primitives (button, card, table, dsb)
│   │   ├── charts/                  # wrapper generik recharts/visx
│   │   ├── layout/
│   │   │   ├── AppShell.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── Topbar.tsx
│   │   └── feedback/
│   │       ├── LoadingSpinner.tsx
│   │       └── ErrorBoundary.tsx
│   │
│   ├── hooks/                      # shared hooks lintas domain
│   │   ├── useDebounce.ts
│   │   └── useWebSocket.ts          # generic WS hook (dipakai simulation/ & lainnya)
│   │
│   ├── lib/                        # wrapper library eksternal
│   │   ├── queryClient.ts
│   │   └── zodSchemas.ts
│   │
│   ├── types/                      # tipe global lintas domain
│   │   ├── api.types.ts
│   │   └── global.d.ts
│   │
│   ├── styles/
│   │   └── globals.css
│   │
│   └── test/
│       ├── setupTests.ts
│       └── mocks/
│           └── handlers.ts          # MSW mock API untuk unit test
│
├── e2e/                            # Playwright/Cypress
├── .env.example
├── eslint.config.js
├── .prettierrc
├── tsconfig.json                    # path alias @/features, @/components, dst
├── tsconfig.app.json
├── tsconfig.node.json
├── vite.config.ts
├── package.json
├── package-lock.json
└── Dockerfile