// features/simulation/components/SimulationFlowchart.tsx
import { useMemo } from "react";
import { useSimulationStore } from "../store/simulationStore";
import { stepOrdinal, WAREHOUSE_STEP_ID } from "../types/simulation.types";
import { StepNode } from "./StepNode";
import { StepConnector } from "./StepConnector";
import { WarehouseNode } from "./WarehouseNode";
import styles from "./SimulationFlowchart.module.css";

interface SimulationFlowchartProps {
  /** worker_id -> display name, e.g. built from useDigitalTwin()'s worker list */
  workerNames?: Record<string, string>;
  /** job_id -> job title, e.g. built from useDigitalTwin()'s job_desks list */
  jobTitles?: Record<string, string>;
  // --- PEMBARUAN: Tambahkan isMock ke tipe Props ---
  isMock?: boolean;
}

// --- PEMBARUAN: Terima isMock sebagai prop ---
export function SimulationFlowchart({ workerNames = {}, jobTitles = {}, isMock }: SimulationFlowchartProps) {
  const status = useSimulationStore((s) => s.status);
  const data = useSimulationStore((s) => s.data);

  const steps = useMemo(
    () =>
      [...(data?.live_simulation_state?.step_breakdown ?? [])].sort(
        (a, b) => stepOrdinal(a.step_id) - stepOrdinal(b.step_id),
      ),
    [data],
  );

  const assignments = data?.live_simulation_state?.current_assignments ?? [];
  const activeTransfers = data?.live_simulation_state?.active_transfers ?? [];
  const bottleneckIds = new Set(data?.live_simulation_state?.system_bottlenecks ?? []);

  if (status === "idle" && !data) {
    return (
      <div className={styles.emptyState}>
        <p className={styles.emptyStateText}>
          Simulasi {isMock && <strong>(MOCK)</strong>} belum dijalankan. Tekan <span className={styles.emptyStateAccent}>Mulai Simulasi</span> untuk
          memvisualisasikan alur produksi secara real-time.
        </p>
      </div>
    );
  }

  if (!data?.live_simulation_state) return null;

  const firstStep = steps[0];
  const warehouseTransfer = firstStep
    ? activeTransfers.find((t) => t.from_step_id === WAREHOUSE_STEP_ID && t.to_step_id === firstStep.step_id)
    : undefined;

  return (
    <div className={styles.flowchart}>
      <div className={styles.stepGroup}>
        {data.live_simulation_state.warehouse && (
          <WarehouseNode warehouse={data.live_simulation_state.warehouse} />
        )}
        {firstStep && <StepConnector transfer={warehouseTransfer} isBottleneckAdjacent={bottleneckIds.has(firstStep.step_id)} />}
      </div>

      {steps.map((step, index) => {
        const currentOrdinal = stepOrdinal(step.step_id);

        // Filter SELURUH worker yang ditugaskan di pos ini (berdasarkan nomor job, misal job-06 -> ordinal 6)
        const stepAssignments = assignments.filter((a) => {
          const jobOrdinal = parseInt(a.assigned_job_id.replace(/\D/g, ""), 10);
          return jobOrdinal === currentOrdinal;
        });

        const nextStep = steps[index + 1];
        const transfer = nextStep
          ? activeTransfers.find((t) => t.from_step_id === step.step_id && t.to_step_id === nextStep.step_id)
          : undefined;

        return (
          <div key={step.step_id} className={styles.stepGroup}>
            <StepNode
              step={step}
              assignments={stepAssignments}
              workerNames={workerNames}
              jobTitles={jobTitles}
              isRunning={status === "running"}
            />
            {nextStep && (
              <StepConnector
                transfer={transfer}
                isBottleneckAdjacent={bottleneckIds.has(step.step_id) || bottleneckIds.has(nextStep.step_id)}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}