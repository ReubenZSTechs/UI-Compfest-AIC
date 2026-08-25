// frontend/src/api/endpoints.ts

export const ENDPOINTS = {
  FACTORIES: {
    ROOT: "/factories",
    DETAIL: (factoryId: string) => `/factories/${factoryId}`,
    DIGITAL_TWIN: (factoryId: string) => `/factories/${factoryId}/digital-twin`,
    SIMULATION_CONFIG: (factoryId: string) => `/factories/${factoryId}/simulation-config`,
    SIMULATION_DESIGN: (factoryId: string) => `/factories/${factoryId}/simulation`,
  },
  DIGITAL_TWIN: {
    BY_FACTORY: (factoryId: string) => `/digital-twin/${factoryId}`,
    COMPATIBILITY_MATRIX: (factoryId: string) => `/digital-twin/${factoryId}/compatibility-matrix`,
    ASSETS: "/digital-twin/assets",
    WORKERS: "/digital-twin/workers",
    JOB_DESKS: "/digital-twin/job-desks",
    LIVE_FLOW: "/digital-twin/live-flow",
  },
  SIMULATION: {
    OVERVIEW: (factoryId: string) => `/simulation/${factoryId}`,
    SAVE_DESIGN: (factoryId: string) => `/simulation/${factoryId}`,
  },
  // Kunci DOCUMENTS diubah menjadi DOCUMENT_PARSER agar cocok 
  // dengan ekspektasi di `Documentparserapi.ts`
  DOCUMENT_PARSER: {
    FACTORY_LIST: "/documents/factories",
    PROCESS_FACTORY: "/documents/process-factory-document",
    PROCESS_COMBINED: "/documents/process-combined-documents",
    PROCESS_COMBINED_MANUAL: "/documents/process-combined-documents-manual",
    STEP_3: "/documents/step-3",
    STEP_4: "/documents/step-4",
    STEP_5: "/documents/step-5",
    STEP_5_JOBS: "/documents/step-5/jobs",
    STEP_5_JOB: (jobId: string) => `/documents/step-5/jobs/${jobId}`,
    PARSE_JOB: (jobId: string) => `/documents/jobs/${jobId}`,
  },
  // Sebagai cadangan (alias) untuk berjaga-jaga jika ada file lain yang
  // masih menggunakan `ENDPOINTS.DOCUMENTS`
  DOCUMENTS: {
    STEP_4: "/documents/step-4",
    STEP_5_JOBS: "/documents/step-5/jobs",
    STEP_5_JOB: (jobId: string) => `/documents/step-5/jobs/${jobId}`,
  },
  RL_OPTIMIZATION: {
    DIGITAL_TWIN: "/rl-optimization/digital-twin",
    OPTIMIZE: "/rl-optimization/optimize",
    JOB: (jobId: string) => `/rl-optimization/optimize/${jobId}`,
    SCENARIOS: (jobId: string) => `/rl-optimization/optimize/${jobId}/scenarios`,
    SCENARIO_DETAIL: (jobId: string, scenarioId: string) =>
      `/rl-optimization/optimize/${jobId}/scenarios/${scenarioId}`,
    APPLY_SCENARIO: (jobId: string, scenarioId: string) =>
      `/rl-optimization/optimize/${jobId}/scenarios/${scenarioId}/apply`,
  },
  AGENTS: {
    NODE_AUTOFILL: "/agents/node-autofill",
  },
} as const;

export type Endpoints = typeof ENDPOINTS;