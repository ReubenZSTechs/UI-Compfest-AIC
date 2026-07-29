export const ENDPOINTS = {
  DIGITAL_TWIN: {
    ROOT: "/digital-twin",
    ASSETS: "/digital-twin/assets",
    WORKERS: "/digital-twin/workers",
    JOB_DESKS: "/digital-twin/job-desks",
    COMPATIBILITY_MATRIX: "/digital-twin/compatibility-matrix",
    LIVE_FLOW: "/digital-twin/live-flow",
  },
  SIMULATION: {
    STATE: "/simulation/state",
    SCENARIOS: "/simulation/scenarios",
    RUN: "/simulation/run",
  },
  AUTH: {
    LOGIN: "/auth/login",
    LOGOUT: "/auth/logout",
    ME: "/auth/me",
  },
} as const;