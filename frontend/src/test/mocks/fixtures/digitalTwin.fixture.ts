import type { DigitalTwin } from "@/features/digital-twin/types/digitalTwin.types";

// Data ini persis mengikuti sample factory_workflow_digital_twin.json
// yang sudah divalidasi di dokumen arsitektur.
export const digitalTwinFixture: DigitalTwin = {
  factory_info: {
    factory_id: "fac-xyz-ygy-01",
    factory_name: "Sweet Bread, PT XYZ Yogyakarta",
    workflow_sequence: [
      "step_01_weighing",
      "step_02_mixing",
      "step_03_dough_dividing",
      "step_04_dough_shaping",
      "step_05_filling_panning",
      "step_06_proofing",
      "step_07_baking",
      "step_08_cooling",
      "step_09_sorting",
      "step_10_packaging",
    ],
  },
  assets: [
    {
      asset_id: "ast-01",
      asset_name: "Digital Weighing Scale",
      category: "measuring_equipment",
      workflow_step: "step_01_weighing",
      is_automated: true,
      base_throughput_capacity: 300,
      operational_cost_per_hour: 4.0,
      environmental_factors: {
        noise_level_db: 45,
        vibration_hazard_level: "low",
        physical_strain_index: 0.15,
      },
      metric_derivation_reasoning:
        "Timbangan digital tidak menghasilkan getaran/kebisingan signifikan.",
    },
    {
      asset_id: "ast-07",
      asset_name: "Deck Oven / Combi Oven",
      category: "machine",
      workflow_step: "step_07_baking",
      is_automated: true,
      base_throughput_capacity: 220,
      operational_cost_per_hour: 18.0,
      environmental_factors: {
        noise_level_db: 58,
        vibration_hazard_level: "low",
        physical_strain_index: 0.55,
      },
      metric_derivation_reasoning:
        "Oven menghasilkan panas tinggi sehingga physical_strain_index dinaikkan.",
    },
    // TODO: lengkapi ast-02 s/d ast-10 dari dokumen arsitektur
  ],
  job_desks: [
    {
      job_id: "job-07",
      job_title: "Operator Baking",
      workflow_step: "step_07_baking",
      assigned_asset_id: "ast-07",
      demands: {
        required_cognitive_focus: 0.85,
        physical_demand_level: "high",
        task_complexity: 0.7,
        error_severity: "critical",
      },
      qc_requirement: "Memastikan suhu 170°C selama 8-10 menit.",
      metric_derivation_reasoning: "Tahap paling kritikal dalam workflow.",
    },
    // TODO: lengkapi job-01 s/d job-10
  ],
  workers: [
    {
      worker_id: "wrk-07",
      name: "Bambang Setiawan",
      demographics: {
        age: 45,
        gender: "male",
        years_of_experience: 18,
        baseline_physical_stamina: 0.65,
        cognitive_resilience: 0.9,
      },
      shift_context: { hours_worked_today: 5.0, consecutive_shifts: 5 },
    },
    // TODO: lengkapi wrk-01 s/d wrk-10
  ],
  factory_flow_rightnow: {
    snapshot_timestamp: "2026-07-27T09:30:00+07:00",
    note: "Snapshot kondisi lantai produksi saat ini.",
    staff_current_positions: [
      {
        worker_id: "wrk-07",
        name: "Bambang Setiawan",
        current_station: "step_07_baking",
        current_asset_id: "ast-07",
        activity_status: "processing",
        moving_to_next_step: "step_08_cooling",
        handoff_item: "loyang panggang #B-235",
      },
      // TODO: lengkapi posisi wrk-01 s/d wrk-10
    ],
  },
  llm_compatibility_and_evaluations: [
    {
      worker_id: "wrk-07",
      job_id: "job-07",
      asset_id: "ast-07",
      evaluations: {
        overall_compatibility_score: 0.9,
        throughput_multiplier: 1.15,
        error_multiplier: 0.4,
        fatigue_accumulation_rate: 1.35,
        stress_sensitivity_factor: 0.8,
      },
      llm_reasoning:
        "Bambang sangat presisi di baking, namun burnout risk tertinggi saat ini.",
    },
    // TODO: lengkapi evaluasi wrk-01 s/d wrk-10
  ],
};