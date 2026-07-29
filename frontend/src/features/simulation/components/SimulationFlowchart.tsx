// features/simulation/components/SimulationFlowchart.tsx
import { useMemo } from "react";
import { useSimulationStore } from "../store/simulationStore";
import { stepOrdinal } from "../types/simulation.types";
import { StepNode } from "./StepNode";
import styles from "./SimulationFlowchart.module.css";

interface SimulationFlowchartProps {
  /** worker_id -> display name, e.g. built from useDigitalTwin()'s worker list */
  workerNames?: Record<string, string>;
  /** job_id -> job title, e.g. built from useDigitalTwin()'s job_desks list */
  jobTitles?: Record<string, string>;
}

export function SimulationFlowchart({ workerNames = {}, jobTitles = {} }: SimulationFlowchartProps) {
  const status = useSimulationStore((s) => s.status);
  const data = useSimulationStore((s) => s.data);

  const steps = useMemo(
    () =>
      [...(data?.live_simulation_state.step_breakdown ?? [])].sort(
        (a, b) => stepOrdinal(a.step_id) - stepOrdinal(b.step_id),
      ),
    [data],
  );

  const assignments = data?.live_simulation_state.current_assignments ?? [];

  if (status === "idle" && !data) {
    return (
      <div className={styles.emptyState}>
        <p className={styles.emptyStateText}>
          Simulasi belum dijalankan. Tekan <span className={styles.emptyStateAccent}>Mulai Simulasi</span> untuk
          memvisualisasikan alur produksi secara real-time.
        </p>
      </div>
    );
  }

  return (
    <div className={styles.flowchart}>
      {steps.map((step, index) => {
        // Positional matching: current_assignments is ordered by workflow position (job-01..job-10),
        // sama seperti step_breakdown. Kalau backend nanti menambahkan field workflow_step eksplisit
        // pada tiap assignment, ganti pencocokan ini dari index ke field itu.
        const assignment = assignments[index];
        return (
          <StepNode
            key={step.step_id}
            step={step}
            assignment={assignment}
            workerName={assignment ? workerNames[assignment.worker_id] : undefined}
            jobTitle={assignment ? jobTitles[assignment.assigned_job_id] : undefined}
            isLast={index === steps.length - 1}
            isRunning={status === "running"}
          />
        );
      })}
    </div>
  );
}