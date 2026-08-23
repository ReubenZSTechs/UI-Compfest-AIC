export const ENDPOINTS = {
  DIGITAL_TWIN: {
    ROOT: "/digital-twin",
    ASSETS: "/digital-twin/assets",
    WORKERS: "/digital-twin/workers",
    JOB_DESKS: "/digital-twin/job-desks",
    COMPATIBILITY_MATRIX: "/digital-twin/compatibility-matrix",
    LIVE_FLOW: "/digital-twin/live-flow",
  },
  DOCUMENT_PARSER: {
    PROCESS_COMBINED: "/documents/process-combined-documents",
    PARSE: "/documents/process-combined-documents",
    PROCESS_FACTORY: "/documents/process-factory-document",
    STEP_4: "/documents/step-4",
    STEP_5: "/documents/step-5",
  },
  SIMULATION: {
    STATE: "/simulation/state",
    SCENARIOS: "/simulation/scenarios",
    RUN: "/simulation/run",
  },
  // BARU: dipakai oleh features/canvas/api/canvasApi.ts dan store/draftStore.ts
  CANVAS: {
    ANALYZE: "/canvas/analyze",
    PROJECTS: "/canvas/projects",
    PROJECTS_LATEST: "/canvas/projects/latest",
  },
  // BARU: dipakai oleh features/simulation_optimisation/api/simulationApi.ts
  RL_OPTIMIZATION: {
    DIGITAL_TWIN: "/rl-optimization/digital-twin",
  },
  AUTH: {
    LOGIN: "/auth/login",
    LOGOUT: "/auth/logout",
    ME: "/auth/me",
  },
} as const;
export type Endpoints = typeof ENDPOINTS;