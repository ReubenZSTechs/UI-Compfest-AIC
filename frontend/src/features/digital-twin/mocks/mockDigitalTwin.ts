// frontend/src/features/digital-twin/mocks/mockDigitalTwin.ts
//
// Data dummy (mock) untuk keperluan pengujian tampilan DigitalTwinPage
// tanpa perlu memanggil API backend. Diaktifkan lewat query param
// `?mock=true` pada halaman (lihat useDigitalTwin.ts).

import type { DigitalTwin } from "../types/digitalTwin.types";

export const mockDigitalTwin: DigitalTwin = {
  simulationId: "mock-sim-001",
  jobId: "mock-job-001",

  factoryInfo: {
    factoryId: "FAC-MOCK-001",
    factoryName: "PT Mock Garment Nusantara",
    workflowSequence: ["cutting", "sewing", "quality_control", "packing"],
    processType: "garment_manufacturing",
    declaredWorkerCount: 6,
    layoutDescription:
      "Layout linear dari area pemotongan kain hingga area pengepakan akhir.",
    parallelGroups: [
      {
        groupId: "PG-1",
        steps: ["sewing", "quality_control"],
        reasoning:
          "Sewing dan quality control dapat berjalan paralel pada batch berbeda.",
      },
    ],
  },

  assets: [
    {
      assetId: "AST-001",
      assetName: "Mesin Potong Otomatis CX-200",
      category: "cutting_machine",
      workflowStep: "cutting",
      isAutomated: true,
      baseThroughputCapacity: 120,
      operationalCostPerHour: 45000,
      environmentalFactors: {
        noiseLevelDb: 72,
        vibrationHazardLevel: "medium",
        physicalStrainIndex: 0.3,
      },
      metricDerivationReasoning:
        "Diturunkan dari spesifikasi pabrikan mesin CX-200.",
      unitsAvailable: 2,
    },
    {
      assetId: "AST-002",
      assetName: "Mesin Jahit Industri JX-9",
      category: "sewing_machine",
      workflowStep: "sewing",
      isAutomated: false,
      baseThroughputCapacity: 60,
      operationalCostPerHour: 20000,
      environmentalFactors: {
        noiseLevelDb: 68,
        vibrationHazardLevel: "low",
        physicalStrainIndex: 0.45,
      },
      metricDerivationReasoning: "Estimasi berdasarkan rata-rata output operator.",
      unitsAvailable: 4,
    },
    {
      assetId: "AST-003",
      assetName: "Meja Inspeksi QC Digital",
      category: "inspection_station",
      workflowStep: "quality_control",
      isAutomated: false,
      baseThroughputCapacity: 90,
      operationalCostPerHour: 15000,
      environmentalFactors: {
        noiseLevelDb: 45,
        vibrationHazardLevel: "low",
        physicalStrainIndex: 0.2,
      },
      unitsAvailable: 2,
    },
    {
      assetId: "AST-004",
      assetName: "Conveyor Packing Line PL-3",
      category: "packing_line",
      workflowStep: "packing",
      isAutomated: true,
      baseThroughputCapacity: 150,
      operationalCostPerHour: 30000,
      environmentalFactors: {
        noiseLevelDb: 60,
        vibrationHazardLevel: "medium",
        physicalStrainIndex: 0.25,
      },
      unitsAvailable: 1,
    },
  ],

  jobDesks: [
    {
      jobId: "JOB-001",
      jobTitle: "Operator Mesin Potong",
      workflowStep: "cutting",
      assignedAssetId: "AST-001",
      demands: {
        requiredCognitiveFocus: 0.6,
        physicalDemandLevel: "medium",
        taskComplexity: 0.5,
        errorSeverity: "moderate",
      },
      qcRequirement: "Toleransi potong maksimal 2mm",
      metricDerivationReasoning: "Berdasarkan SOP pemotongan kain standar.",
    },
    {
      jobId: "JOB-002",
      jobTitle: "Penjahit Utama",
      workflowStep: "sewing",
      assignedAssetId: "AST-002",
      demands: {
        requiredCognitiveFocus: 0.7,
        physicalDemandLevel: "high",
        taskComplexity: 0.65,
        errorSeverity: "high",
      },
      qcRequirement: "Jahitan rapi, tanpa loncat benang",
    },
    {
      jobId: "JOB-003",
      jobTitle: "Inspektur Kualitas",
      workflowStep: "quality_control",
      assignedAssetId: "AST-003",
      demands: {
        requiredCognitiveFocus: 0.85,
        physicalDemandLevel: "low",
        taskComplexity: 0.55,
        errorSeverity: "critical",
      },
      qcRequirement: "Lolos checklist 15 poin QC",
    },
    {
      jobId: "JOB-004",
      jobTitle: "Staf Pengepakan",
      workflowStep: "packing",
      assignedAssetId: "AST-004",
      demands: {
        requiredCognitiveFocus: 0.4,
        physicalDemandLevel: "medium",
        taskComplexity: 0.3,
        errorSeverity: "low",
      },
      qcRequirement: "Label dan jumlah sesuai packing list",
    },
  ],

  workers: [
    {
      workerId: "WRK-001",
      name: "Siti Aminah",
      demographics: {
        age: 29,
        gender: "female",
        yearsOfExperience: 5,
        baselinePhysicalStamina: 0.75,
        cognitiveResilience: 0.7,
      },
      shiftContext: {
        hoursWorkedToday: 4.5,
        consecutiveShifts: 3,
      },
      skills: ["cutting", "pattern_reading"],
      certifications: ["K3 Dasar"],
      capabilities: ["cutting_machine_operation"],
    },
    {
      workerId: "WRK-002",
      name: "Budi Santoso",
      demographics: {
        age: 34,
        gender: "male",
        yearsOfExperience: 8,
        baselinePhysicalStamina: 0.8,
        cognitiveResilience: 0.65,
      },
      shiftContext: {
        hoursWorkedToday: 6,
        consecutiveShifts: 5,
      },
      skills: ["sewing", "machine_maintenance"],
      certifications: ["K3 Dasar", "Sertifikasi Menjahit Level 2"],
      capabilities: ["sewing_machine_operation"],
    },
    {
      workerId: "WRK-003",
      name: "Dewi Lestari",
      demographics: {
        age: 26,
        gender: "female",
        yearsOfExperience: 3,
        baselinePhysicalStamina: 0.7,
        cognitiveResilience: 0.85,
      },
      shiftContext: {
        hoursWorkedToday: 3,
        consecutiveShifts: 2,
      },
      skills: ["quality_inspection", "detail_orientation"],
      certifications: ["Sertifikasi QC Garmen"],
      capabilities: ["visual_inspection"],
    },
    {
      workerId: "WRK-004",
      name: "Agus Wijaya",
      demographics: {
        age: 41,
        gender: "male",
        yearsOfExperience: 12,
        baselinePhysicalStamina: 0.6,
        cognitiveResilience: 0.6,
      },
      shiftContext: {
        hoursWorkedToday: 7,
        consecutiveShifts: 6,
      },
      skills: ["packing", "inventory_handling"],
      certifications: ["K3 Dasar"],
      capabilities: ["packing_line_operation"],
    },
  ],

  factoryFlowRightnow: {
    snapshotTimestamp: new Date().toISOString(),
    note: "Snapshot simulasi (mock) untuk pengujian frontend.",
    staffCurrentPositions: [
      {
        workerId: "WRK-001",
        name: "Siti Aminah",
        currentStation: "cutting",
        currentAssetId: "AST-001",
        activityStatus: "active",
        movingToNextStep: "sewing",
        handoffItem: "Potongan kain batch #12",
      },
      {
        workerId: "WRK-002",
        name: "Budi Santoso",
        currentStation: "sewing",
        currentAssetId: "AST-002",
        activityStatus: "active",
        movingToNextStep: "quality_control",
        handoffItem: "Produk jadi batch #11",
      },
      {
        workerId: "WRK-003",
        name: "Dewi Lestari",
        currentStation: "quality_control",
        currentAssetId: "AST-003",
        activityStatus: "idle",
        movingToNextStep: "packing",
        handoffItem: "",
      },
      {
        workerId: "WRK-004",
        name: "Agus Wijaya",
        currentStation: "packing",
        currentAssetId: "AST-004",
        activityStatus: "active",
        movingToNextStep: "",
        handoffItem: "Karton siap kirim #7",
      },
    ],
  },

  llmCompatibilityAndEvaluations: [
    {
      workerId: "WRK-001",
      jobId: "JOB-001",
      assetId: "AST-001",
      evaluations: {
        overallCompatibilityScore: 0.88,
        throughputMultiplier: 1.05,
        errorMultiplier: 0.9,
        fatigueAccumulationRate: 0.15,
        stressSensitivityFactor: 0.2,
      },
      llmReasoning:
        "Pengalaman 5 tahun di cutting membuat kecocokan tinggi dengan risiko error rendah.",
    },
    {
      workerId: "WRK-002",
      jobId: "JOB-002",
      assetId: "AST-002",
      evaluations: {
        overallCompatibilityScore: 0.81,
        throughputMultiplier: 1.1,
        errorMultiplier: 1.0,
        fatigueAccumulationRate: 0.25,
        stressSensitivityFactor: 0.3,
      },
      llmReasoning: "Kompatibel namun beban shift tinggi meningkatkan risiko kelelahan.",
    },
    {
      workerId: "WRK-003",
      jobId: "JOB-003",
      assetId: "AST-003",
      evaluations: {
        overallCompatibilityScore: 0.93,
        throughputMultiplier: 0.95,
        errorMultiplier: 0.6,
        fatigueAccumulationRate: 0.1,
        stressSensitivityFactor: 0.15,
      },
      llmReasoning: "Ketelitian tinggi sangat cocok untuk peran QC kritikal.",
    },
    {
      workerId: "WRK-004",
      jobId: "JOB-004",
      assetId: "AST-004",
      evaluations: {
        overallCompatibilityScore: 0.7,
        throughputMultiplier: 0.9,
        errorMultiplier: 1.2,
        fatigueAccumulationRate: 0.35,
        stressSensitivityFactor: 0.4,
      },
      llmReasoning: "Kompatibilitas cukup, namun shift beruntun 6x menurunkan performa.",
    },
    {
      workerId: "WRK-001",
      jobId: "JOB-002",
      evaluations: {
        overallCompatibilityScore: 0.4,
        throughputMultiplier: 0.6,
        errorMultiplier: 1.6,
        fatigueAccumulationRate: 0.3,
        stressSensitivityFactor: 0.5,
      },
      llmReasoning: "Minim pengalaman menjahit, kecocokan silang rendah.",
    },
  ],

  warnings: [
    "Ini adalah data mock untuk pengujian frontend, bukan data produksi.",
  ],
};
