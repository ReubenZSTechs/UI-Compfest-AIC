import type { Worker, RealtimeMetrics } from "../types/digitalTwin.types";
import {
  formatExperience,
  formatHoursWorked,
  getInitials,
  capacityLevelFromValue,
  strainLevelFromIndex,
  CONSECUTIVE_SHIFTS_WARNING_THRESHOLD,
} from "../utils/formatMetrics";
import { useDigitalTwinStore } from "../store/digitalTwinStore";
import styles from "./WorkerCard.module.css";

interface WorkerCardProps {
  worker: Worker;
  /** Opsional: data real-time dari simulation engine, kalau tersedia */
  realtimeMetrics?: RealtimeMetrics;
}

export function WorkerCard({ worker, realtimeMetrics }: WorkerCardProps) {
  const selectedWorkerId = useDigitalTwinStore((s) => s.selectedWorkerId);
  const selectWorker = useDigitalTwinStore((s) => s.selectWorker);

  const isSelected = selectedWorkerId === worker.worker_id;
  const { demographics, shift_context } = worker;

  const staminaLevel = capacityLevelFromValue(demographics.baseline_physical_stamina);
  const resilienceLevel = capacityLevelFromValue(demographics.cognitive_resilience);
  const isOverworked =
    shift_context.consecutive_shifts >= CONSECUTIVE_SHIFTS_WARNING_THRESHOLD;

  return (
    <button
      type="button"
      className={`${styles.card} ${isSelected ? styles.cardSelected : ""}`}
      onClick={() => selectWorker(worker.worker_id)}
      aria-pressed={isSelected}
    >
      {/* Header: avatar + identitas */}
      <div className={styles.header}>
        <span className={styles.avatar}>{getInitials(worker.name)}</span>
        <div className={styles.identity}>
          <h3 className={styles.name}>{worker.name}</h3>
          <span className={styles.workerId}>{worker.worker_id}</span>
        </div>
        {realtimeMetrics && (
          <span
            className={`${styles.burnoutBadge} ${
              styles[`burnout-${realtimeMetrics.burnout_hazard_risk}`]
            }`}
          >
            {realtimeMetrics.burnout_hazard_risk}
          </span>
        )}
      </div>

      {/* Demografi */}
      <div className={styles.demographicsRow}>
        <span>{demographics.age} tahun</span>
        <span className={styles.dividerDot}>·</span>
        <span>{formatExperience(demographics.years_of_experience)}</span>
      </div>

      {/* Kapasitas baseline: stamina & resiliensi kognitif */}
      <div className={styles.capacityGrid}>
        <div className={styles.capacityItem}>
          <div className={styles.capacityLabelRow}>
            <span className={styles.readoutLabel}>Stamina Fisik</span>
            <span className={styles.readoutValue}>
              {(demographics.baseline_physical_stamina * 100).toFixed(0)}%
            </span>
          </div>
          <div className={styles.capacityBar}>
            <div
              className={`${styles.capacityFill} ${styles[`capacity-${staminaLevel}`]}`}
              style={{ width: `${demographics.baseline_physical_stamina * 100}%` }}
            />
          </div>
        </div>
        <div className={styles.capacityItem}>
          <div className={styles.capacityLabelRow}>
            <span className={styles.readoutLabel}>Resiliensi Kognitif</span>
            <span className={styles.readoutValue}>
              {(demographics.cognitive_resilience * 100).toFixed(0)}%
            </span>
          </div>
          <div className={styles.capacityBar}>
            <div
              className={`${styles.capacityFill} ${styles[`capacity-${resilienceLevel}`]}`}
              style={{ width: `${demographics.cognitive_resilience * 100}%` }}
            />
          </div>
        </div>
      </div>

      {/* Signature element: shift tally — kartu absen shift beruntun */}
      <div className={styles.shiftBlock}>
        <div className={styles.shiftLabelRow}>
          <span className={styles.readoutLabel}>Shift Beruntun</span>
          <span
            className={`${styles.shiftCount} ${isOverworked ? styles.shiftCountWarning : ""}`}
          >
            {shift_context.consecutive_shifts}x
          </span>
        </div>
        <div className={styles.shiftTally} aria-hidden="true">
          {Array.from({ length: Math.max(shift_context.consecutive_shifts, 5) }).map(
            (_, i) => {
              const filled = i < shift_context.consecutive_shifts;
              const warning = filled && i >= CONSECUTIVE_SHIFTS_WARNING_THRESHOLD - 1;
              return (
                <span
                  key={i}
                  className={`${styles.tallyMark} ${filled ? styles.tallyFilled : ""} ${
                    warning ? styles.tallyWarning : ""
                  }`}
                />
              );
            }
          )}
        </div>
        <span className={styles.hoursToday}>
          {formatHoursWorked(shift_context.hours_worked_today)}
        </span>
      </div>

      {/* Real-time fatigue/stress, hanya tampil kalau data tersedia */}
      {realtimeMetrics && (
        <div className={styles.realtimeRow}>
          <RealtimeMeter label="Fatigue" value={realtimeMetrics.current_fatigue_level} />
          <RealtimeMeter label="Stres" value={realtimeMetrics.current_stress_level} />
        </div>
      )}
    </button>
  );
}

function RealtimeMeter({ label, value }: { label: string; value: number }) {
  const level = strainLevelFromIndex(value);
  return (
    <div className={styles.realtimeMeterItem}>
      <span className={styles.readoutLabel}>{label}</span>
      <div className={styles.capacityBar}>
        <div
          className={`${styles.capacityFill} ${styles[`strainbar-${level}`]}`}
          style={{ width: `${value * 100}%` }}
        />
      </div>
    </div>
  );
}