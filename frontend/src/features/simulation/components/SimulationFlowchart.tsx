// features/simulation/components/SimulationFlowchart.tsx
import { useMemo } from "react";
import { useSimulationStore } from "../store/simulationStore";
import { buildFlowLayout } from "../utils/layoutGraph";
import { StepNode } from "./StepNode";
import { StepConnector } from "./StepConnector";
import { WarehouseNode } from "./WarehouseNode";
import { OutputNode } from "./OutputNode";
import { FlowViewport } from "./FlowViewport";
import type { CurrentAssignment, StepBreakdown } from "../types/simulation.types";
import styles from "./SimulationFlowchart.module.css";

interface SimulationFlowchartProps {
  workerNames?: Record<string, string>;
  jobTitles?: Record<string, string>;
  isMock?: boolean;
}

function groupAssignmentsByStep(
  assignments: CurrentAssignment[],
  steps: StepBreakdown[]
): Record<string, CurrentAssignment[]> {
  const stepIdByJobId = new Map<string, string>();

  for (const step of steps) {
    for (const workerId of step.worker_ids ?? []) {
      stepIdByJobId.set(workerId, step.step_id);
    }
  }

  const grouped: Record<string, CurrentAssignment[]> = {};

  for (const assignment of assignments) {
    const stepId = stepIdByJobId.get(assignment.worker_id);
    if (!stepId) continue;
    grouped[stepId] = [...(grouped[stepId] ?? []), assignment];
  }

  return grouped;
}

export function SimulationFlowchart({
  workerNames = {},
  jobTitles = {},
  isMock,
}: SimulationFlowchartProps) {
  const status = useSimulationStore((s) => s.status);
  const data = useSimulationStore((s) => s.data);

  const state = data?.live_simulation_state;
  const steps = useMemo(() => state?.step_breakdown ?? [], [state]);
  const layout = useMemo(() => buildFlowLayout(steps), [steps]);

  const assignmentsByStep = useMemo(
    () => groupAssignmentsByStep(state?.current_assignments ?? [], steps),
    [state, steps]
  );

  const activeTransfers = state?.active_transfers ?? [];
  const bottleneckIds = new Set(state?.system_bottlenecks ?? []);
  const warehouses = state?.warehouses ?? [];
  const outputs = state?.outputs ?? [];

  if (status === "idle" && !data) {
    return (
      <div className={styles.emptyState}>
        <p className={styles.emptyStateText}>
          Simulasi {isMock && <strong>(MOCK)</strong>} belum dijalankan. Tekan{" "}
          <span className={styles.emptyStateAccent}>Mulai Simulasi</span> untuk memvisualisasikan
          alur produksi secara real-time.
        </p>
      </div>
    );
  }

  if (!state) return null;

  function transferBetween(fromId: string, toId: string) {
    return activeTransfers.find((item) => item.from_step_id === fromId && item.to_step_id === toId);
  }

  return (
    <FlowViewport className={styles.viewport}>
      <div className={styles.graph}>
        {warehouses.length > 0 && (
          <div className={styles.column}>
            {warehouses.map((warehouse) => (
              <div key={warehouse.warehouse_id} className={styles.cell}>
                <WarehouseNode
                  warehouse={{
                    capacity: warehouse.capacity,
                    current_stock: warehouse.current_stock,
                  }}
                  name={warehouse.warehouse_name}
                  materialName={warehouse.material_name}
                  materialUnit={warehouse.material_unit}
                />
                <div className={styles.outEdges}>
                  {warehouse.target_step_ids.map((targetId) => (
                    <StepConnector
                      key={`${warehouse.warehouse_id}->${targetId}`}
                      transfer={transferBetween(warehouse.warehouse_id, targetId)}
                      isBottleneckAdjacent={bottleneckIds.has(targetId)}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {layout.columns.map((column) => (
          <div key={column.depth} className={styles.column}>
            {column.nodes.map(({ step }) => {
              const successors = step.next_step_ids ?? [];

              return (
                <div key={step.step_id} className={styles.cell}>
                  <StepNode
                    step={step}
                    assignments={assignmentsByStep[step.step_id] ?? []}
                    workerNames={workerNames}
                    jobTitles={jobTitles}
                    isRunning={status === "running"}
                  />
                  {successors.length > 0 && (
                    <div className={styles.outEdges}>
                      {successors.map((targetId) => (
                        <StepConnector
                          key={`${step.step_id}->${targetId}`}
                          transfer={transferBetween(step.step_id, targetId)}
                          isBottleneckAdjacent={
                            bottleneckIds.has(step.step_id) || bottleneckIds.has(targetId)
                          }
                        />
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}

        {outputs.length > 0 && (
          <div className={styles.column}>
            {outputs.map((output) => (
              <div key={output.output_id} className={styles.cell}>
                <OutputNode output={output} />
              </div>
            ))}
          </div>
        )}
      </div>
    </FlowViewport>
  );
}