// frontend/src/features/digital-twin/types/digitalTwin.types.ts

/**
 * Tipe data TypeScript Modul Digital Twin & Document Parser (Frontend UI).
 * Menggunakan format camelCase sesuai serializer FastAPI (Pydantic to_camel).
 */

export interface ParallelGroup {
  groupId: string;
  steps: string[];
  reasoning?: string;
}

export interface FactoryInfo {
  factoryId: string;
  factoryName: string;
  workflowSequence: string[];
  processType?: string;
  declaredWorkerCount?: number;
  layoutDescription?: string;
  parallelGroups?: ParallelGroup[];
}

export type VibrationHazardLevel = "low" | "medium" | "high";
export type PhysicalDemandLevel = "low" | "medium" | "high";
export type ErrorSeverity = "low" | "moderate" | "high" | "critical";
export type BurnoutHazardRisk = "low" | "medium" | "high" | "critical";

export interface RealtimeMetrics {
  currentFatigueLevel: number;
  currentStressLevel: number;
  burnoutHazardRisk: BurnoutHazardRisk;
}

export interface EnvironmentalFactors {
  noiseLevelDb: number;
  vibrationHazardLevel: VibrationHazardLevel;
  physicalStrainIndex: number;
}

export interface Asset {
  assetId: string;
  assetName: string;
  category: string;
  workflowStep: string;
  isAutomated: boolean;
  baseThroughputCapacity: number;
  operationalCostPerHour: number;
  environmentalFactors: EnvironmentalFactors;
  metricDerivationReasoning?: string;
  unitsAvailable?: number;
}

export type AssetCategory = Asset["category"];

export interface Demands {
  requiredCognitiveFocus: number;
  physicalDemandLevel: PhysicalDemandLevel;
  taskComplexity: number;
  errorSeverity: ErrorSeverity;
}

export interface JobDesk {
  jobId: string;
  jobTitle: string;
  workflowStep: string;
  assignedAssetId: string;
  demands: Demands;
  qcRequirement: string;
  metricDerivationReasoning?: string;
}

export interface Demographics {
  age: number;
  gender: string;
  yearsOfExperience: number;
  baselinePhysicalStamina: number;
  cognitiveResilience: number;
}

export interface ShiftContext {
  hoursWorkedToday: number;
  consecutiveShifts: number;
}

export interface Worker {
  workerId: string;
  name: string;
  demographics: Demographics;
  shiftContext: ShiftContext;
  skills?: string[];
  certifications?: string[];
  capabilities?: string[];
}

export interface StaffPosition {
  workerId: string;
  name: string;
  currentStation: string;
  currentAssetId: string;
  activityStatus: string;
  movingToNextStep: string;
  handoffItem: string;
}

export interface FactoryFlowRightNow {
  snapshotTimestamp: string;
  note?: string;
  staffCurrentPositions: StaffPosition[];
}

export interface Evaluations {
  overallCompatibilityScore: number;
  throughputMultiplier: number;
  errorMultiplier: number;
  fatigueAccumulationRate?: number;
  stressSensitivityFactor?: number;
}

export interface CompatibilityEvaluation {
  workerId: string;
  jobId: string;
  assetId?: string;
  evaluations: Evaluations;
  llmReasoning?: string;
}

export interface DigitalTwin {
  simulationId?: string;
  jobId?: string;
  factoryInfo: FactoryInfo;
  assets: Asset[];
  jobDesks: JobDesk[];
  workers: Worker[];
  factoryFlowRightnow?: FactoryFlowRightNow;
  llmCompatibilityAndEvaluations: CompatibilityEvaluation[];
  warnings?: string[];
}

// --- Payload Response API Gateway (Document Parser) ---

export interface ExtractionSummary {
  extractedFields?: Record<string, string>;
  tablesCount?: number;
  rawText?: string;
  warnings?: string[];
}

export interface ProcessFactoryDocumentResponse {
  parseJobId?: string;
  agentInput: string;
  factoryStructure: {
    factoryInfo: FactoryInfo;
    assets: Asset[];
    jobDesks: JobDesk[];
  };
  extractionSummary?: ExtractionSummary;
}

export interface Step4Response {
  workerProfile: {
    workers: Worker[];
  };
  workerAgentInput?: string;
  candidatesFound: number;
  rejectedBlocksCount: number;
  archiveReports?: any[];
  warnings?: string[];
}

export interface Step5Response {
  compatibilityMatrix: CompatibilityEvaluation[];
  warnings?: string[];
}

export interface ProcessCombinedDocumentsResponse {
  parseJobId?: string;
  extractionSummary?: ExtractionSummary;
  agentInput?: string;
  factoryStructure: {
    factoryInfo: FactoryInfo;
    assets: Asset[];
    jobDesks: JobDesk[];
  };
  workerProfile: {
    workers: Worker[];
  };
  workerAgentInput?: string;
  candidatesFound?: number;
  rejectedBlocksCount?: number;
  archiveReports?: any[];
  compatibilityMatrix: CompatibilityEvaluation[];
}

export interface ParseJobResult {
  id: string;
  factoryId?: string;
  status: "pending" | "in_progress" | "success" | "error";
  templateFilename?: string;
  cvBundleFilename?: string;
  workersParsed: number;
  jobDesksParsed: number;
  warnings?: string[];
  errorStage?: string;
  errorMessage?: string;
  errorDetails?: any[];
  factoryStructure?: Record<string, any>;
  workerProfile?: Record<string, any>;
  compatibilityMatrix?: CompatibilityEvaluation[] | Record<string, any>;
  createdAt?: string;
}