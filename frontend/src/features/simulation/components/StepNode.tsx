// features/simulation/components/StepNode.tsx
import { useSimulationStore } from "../store/simulationStore";
import type { BurnoutRisk, CurrentAssignment, StepBreakdown } from "../types/simulation.types";
import styles from "./StepNode.module.css";

interface StepNodeProps {
  step: StepBreakdown;
  assignment?: CurrentAssignment;
  /** Resolved display name for the assigned worker, e.g. from useDigitalTwin(). Falls back to worker_id. */
  workerName?: string;
  /** Resolved job title for the assigned job, e.g. from useDigitalTwin(). Falls back to assigned_job_id. */
  jobTitle?: string;
  isLast: boolean;
  isRunning: boolean;
}

const RISK_META: Record<BurnoutRisk, { className: string; label: string }> = {
  low: { className: styles.riskLow, label: "Aman" },
  medium: { className: styles.riskMedium, label: "Waspada" },
  high: { className: styles.riskHigh, label: "Kritis" },
};

function meterTone(pct: number, thresholds: { warning: number; danger: number }) {
  if (pct > thresholds.danger) return styles.meterDanger;
  if (pct > thresholds.warning) return styles.meterWarning;
  return styles.meterSafe;
}

function MiniMeter({
  label,
  value,
  thresholds,
}: {
  label: string;
  value: number;
  thresholds: { warning: number; danger: number };
}) {
  const pct = Math.round(value * 100);
  return (
    <div className={styles.meterRow}>
      <span className={styles.meterLabel}>{label}</span>
      <div className={styles.meterTrack}>
        <div className={`${styles.meterFill} ${meterTone(pct, thresholds)}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={styles.meterValue}>{pct}%</span>
    </div>
  );
}

export function StepNode({ step, assignment, workerName, jobTitle, isLast, isRunning }: StepNodeProps) {
  const selectedStepId = useSimulationStore((s) => s.selectedStepId);
  const selectStep = useSimulationStore((s) => s.selectStep);
  const isBottleneck = step.status === "bottleneck";
  const isSelected = selectedStepId === step.step_id;
  const metrics = assignment?.calculated_realtime_metrics;
  const risk = metrics ? RISK_META[metrics.burnout_hazard_risk] : undefined;

  return (
    <div className={styles.wrapper}>
      <button
        type="button"
        onClick={() => selectStep(step.step_id)}
        className={[styles.node, isBottleneck ? styles.nodeBottleneck : "", isSelected ? styles.nodeSelected : ""]
          .filter(Boolean)
          .join(" ")}
      >
        <div className={styles.nodeTop}>
          <div className={styles.nodeTitleGroup}>
            {isBottleneck && <span className={styles.bottleneckBadge}>Bottleneck</span>}
            <h3 className={styles.stepName}>{step.step_name}</h3>
          </div>
          {isRunning && (
            <span className={[styles.pulseDot, isBottleneck ? styles.pulseDotBottleneck : ""].filter(Boolean).join(" ")} />
          )}
        </div>

        <div className={styles.nodeMetrics}>
          <span>
            Output <strong>{step.output_generated.toFixed(0)}</strong> u/h
          </span>
          <span>
            Cost <strong>Rp{Math.round(step.operational_cost_idr).toLocaleString("id-ID")}</strong>
          </span>
        </div>

        {assignment && metrics && (
          <div className={styles.assignment}>
            <div className={styles.assignmentTop}>
              <span className={styles.assignmentName}>
                {workerName ?? assignment.worker_id}
                <span> · {jobTitle ?? assignment.assigned_job_id}</span>
              </span>
              {risk && (
                <span className={[styles.riskBadge, risk.className].join(" ")}>
                  <span className={styles.riskDot} />
                  {risk.label}
                </span>
              )}
            </div>
            <div className={styles.meters}>
              <MiniMeter label="Fatigue" value={metrics.current_fatigue_level} thresholds={{ warning: 40, danger: 65 }} />
              <MiniMeter label="Stress" value={metrics.current_stress_level} thresholds={{ warning: 35, danger: 55 }} />
            </div>
          </div>
        )}
      </button>

      {!isLast && (
        <div className={styles.connector}>
          {isRunning && (
            <div
              className={[styles.connectorFlow, isBottleneck ? styles.connectorFlowBottleneck : ""]
                .filter(Boolean)
                .join(" ")}
            />
          )}
        </div>
      )}
    </div>
  );
}