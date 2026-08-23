// frontend/src/features/simulation_optimisation/types/digitalTwinRl.types.ts
// Tipe untuk response GET /rl-optimization/digital-twin.
// DRAFT — field di bawah diturunkan dari cara pemakaiannya di simulationApi.ts.
// Tolong cocokkan/sesuaikan dengan skema Pydantic response_model backend
// (kemungkinan ada di app/schemas/digital_twin*.py atau app/api/rl_optimization.py).

export interface DigitalTwinAsset {
  assetId: string;
  assetName?: string;
  baseThroughputCapacity: number;
  operationalCostPerHour: number;
}

export interface DigitalTwinJobDemands {
  taskComplexity: number;
}

export interface DigitalTwinJobDescription {
  jobId: string;
  jobTitle: string;
  workflowStep: string;
  assignedAssetId: string;
  demands: DigitalTwinJobDemands;
}

export interface DigitalTwinEvaluationMetrics {
  errorMultiplier: number;
  throughputMultiplier: number;
}

export interface DigitalTwinCompatibilityEvaluation {
  jobId: string;
  workerId: string;
  evaluations: DigitalTwinEvaluationMetrics;
}

export interface DigitalTwinFactoryInfo {
  factoryId: string;
  workflowSequence: string[];
}

export interface DigitalTwin {
  factoryInfo: DigitalTwinFactoryInfo;
  assets: DigitalTwinAsset[];
  jobDescriptions: DigitalTwinJobDescription[];
  llmCompatibilityAndEvaluations: DigitalTwinCompatibilityEvaluation[];
}