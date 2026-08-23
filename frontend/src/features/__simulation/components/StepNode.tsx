// features/simulation/components/StepNode.tsx
import { useSimulationStore } from "../store/simulationStore";
import type { BurnoutRisk, CurrentAssignment, StepBreakdown } from "../types/simulation.types";
import styles from "./StepNode.module.css";

interface StepNodeProps {
  step: StepBreakdown;
  assignments?: CurrentAssignment[];
  workerNames?: Record<string, string>;
  jobTitles?: Record<string, string>;
  assignment?: CurrentAssignment;
  workerName?: string;
  jobTitle?: string;
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

function fillTone(pct: number) {
  if (pct > 85) return styles.fillDanger;
  if (pct > 55) return styles.fillWarning;
  return styles.fillSafe;
}

function formatQuantity(quantity: number, unit: string) {
  return unit === "kg" ? quantity.toFixed(1) : Math.round(quantity).toString();
}

export function StepNode({
  step,
  assignments,
  workerNames,
  jobTitles,
  assignment,
  workerName,
  jobTitle,
  isRunning,
}: StepNodeProps) {
  const selectedStepId = useSimulationStore((state) => state.selectedStepId);
  const selectStep = useSimulationStore((state) => state.selectStep);

  const isSelected = selectedStepId === step.step_id;
  const isBottleneck = step.status === "bottleneck";
  const isIdle = step.status === "idle";

  const material = step.current_material;
  const inProcessQty = material?.in_process_quantity ?? 0;
  const waitingQty = material?.quantity ?? 0;
  const fillPct = Math.max(0, Math.min(100, step.wip_fill_pct));

  const activeAssignments: CurrentAssignment[] =
    assignments && assignments.length > 0
      ? assignments
      : assignment
      ? [assignment]
      : [];

  const unitLabel = material?.unit ?? "unit";
  const hourlyOutput = step.output_per_hour ?? step.output_generated ?? 0;

  return (
    <button
      type="button"
      onClick={() => selectStep(step.step_id)}
      className={[
        styles.node,
        isBottleneck ? styles.nodeBottleneck : "",
        isIdle ? styles.nodeIdle : "",
        isSelected ? styles.nodeSelected : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {/* Header Node */}
      <div className={styles.nodeTop}>
        <div className={styles.nodeTitleGroup}>
          {isBottleneck && <span className={styles.bottleneckBadge}>⚠ Bottleneck · WIP {fillPct.toFixed(0)}%</span>}
          <h3 className={styles.stepName}>{step.step_name}</h3>
        </div>
        {isRunning && !isIdle && (
          <span className={[styles.pulseDot, isBottleneck ? styles.pulseDotBottleneck : ""].filter(Boolean).join(" ")} />
        )}
      </div>

      {/* Informasi Material & Kapasitas */}
      {material && (
        <div className={styles.materialBlock}>
          <div className={styles.materialRow}>
            <span className={[styles.materialDot, isIdle ? styles.materialDotIdle : ""].filter(Boolean).join(" ")} />
            {isIdle ? (
              <span className={styles.materialIdleText}>Menunggu pasokan…</span>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem", width: "100%" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span className={styles.materialName}>{material.material_name}</span>
                  <span className={styles.materialBatch}>{material.batch_code}</span>
                </div>
                
                {/* Rincian Status Material */}
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", opacity: 0.9 }}>
                  <span>
                    Mengantre: <strong>{formatQuantity(waitingQty, material.unit)}</strong> / {material.capacity} {material.unit}
                  </span>
                  {inProcessQty > 0 && (
                    <span style={{ color: "#f59e0b", fontWeight: 600 }}>
                      Diproses: {formatQuantity(inProcessQty, material.unit)} {material.unit}
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>
          <div className={styles.stockTrack} title={`Total WIP (Mengantre + Diproses): ${fillPct.toFixed(0)}% dari kapasitas`}>
            <div className={`${styles.stockFill} ${fillTone(fillPct)}`} style={{ width: `${fillPct}%` }} />
          </div>
        </div>
      )}

      {/* Kecepatan & Output Stats (Output/Jam dan Total Output) */}
      <div className={styles.speedBadgeRow}>
        <span className={styles.speedMultiplierBadge}>
          Laju: <strong>{step.speed_multiplier.toFixed(2)}x</strong>
        </span>
        <span className={styles.outputBadge}>
          Output/Jam: <strong>{formatQuantity(hourlyOutput, unitLabel)}</strong> {unitLabel}/jam
        </span>
        <span className={styles.outputBadge}>
          Total: <strong>{formatQuantity(step.total_output_produced ?? 0, unitLabel)}</strong> {unitLabel}
        </span>
      </div>

      {/* Daftar Pekerja (Assignments) - Sekarang dapat di-scroll jika > 2 pekerja */}
      <div className={styles.workersContainer}>
        {activeAssignments.length > 0 ? (
          activeAssignments.map((a) => {
            const displayName = workerNames?.[a.worker_id] ?? workerName ?? a.worker_id;
            const displayTitle = jobTitles?.[a.assigned_job_id] ?? jobTitle ?? a.assigned_job_id;
            const metrics = a.calculated_realtime_metrics;
            const riskInfo = RISK_META[metrics.burnout_hazard_risk] ?? RISK_META.low;

            return (
              <div key={a.worker_id} className={styles.workerCard}>
                <div className={styles.workerHeader}>
                  <div className={styles.workerMeta}>
                    <span className={styles.workerName}>{displayName}</span>
                    <span className={styles.jobTitle}>{displayTitle}</span>
                  </div>
                  <span className={`${styles.riskBadge} ${riskInfo.className}`}>
                    {riskInfo.label}
                  </span>
                </div>

                <div className={styles.metersGrid}>
                  <MiniMeter
                    label="Lelah"
                    value={metrics.current_fatigue_level}
                    thresholds={{ warning: 40, danger: 65 }}
                  />
                  <MiniMeter
                    label="Stres"
                    value={metrics.current_stress_level}
                    thresholds={{ warning: 35, danger: 55 }}
                  />
                </div>
              </div>
            );
          })
        ) : (
          <div className={styles.unassignedText}>Tidak ada pekerja ditugaskan</div>
        )}
      </div>
    </button>
  );
}