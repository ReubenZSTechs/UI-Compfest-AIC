export const ENDPOINTS = {
  FACTORIES: {
    ROOT: "/factories",
    DETAIL: (factoryId: string) => `/factories/${factoryId}`,
    DIGITAL_TWIN: (factoryId: string) => `/factories/${factoryId}/digital-twin`,
    SIMULATION_CONFIG: (factoryId: string) => `/factories/${factoryId}/simulation-config`,
    SIMULATION_DESIGN: (factoryId: string) => `/factories/${factoryId}/simulation`,
  },
  DOCUMENTS: {
    STEP_4: "/documents/step-4",
    STEP_5_JOBS: "/documents/step-5/jobs",
    STEP_5_JOB: (jobId: string) => `/documents/step-5/jobs/${jobId}`,
  },
  RL_OPTIMIZATION: {
    FACTORY_SCENARIOS: (factoryId: string) => `/rl-optimization/${factoryId}/scenarios`,
    FACTORY_OPTIMIZE: (factoryId: string) => `/rl-optimization/${factoryId}/optimize`,
    FACTORY_OPTIMIZE_STATUS: (factoryId: string) =>
      `/rl-optimization/${factoryId}/optimize/status`,
  },
  AGENTS: {
    NODE_AUTOFILL: "/agents/node-autofill",
    CHAT: "/agents/chat",
  },
} as const;

export type Endpoints = typeof ENDPOINTS;
