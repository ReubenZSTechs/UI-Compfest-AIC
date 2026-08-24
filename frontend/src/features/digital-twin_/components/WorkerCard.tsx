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

  const isSelected = selectedWorkerId === worker.workerId;
  const { demographics, shiftContext } = worker;

  const staminaLevel = capacityLevelFromValue(demographics?.baselinePhysicalStamina ?? 0);
  const resilienceLevel = capacityLevelFromValue(demographics?.cognitiveResilience ?? 0);
  const consecutiveShifts = shiftContext?.consecutiveShifts ?? 0;
  const isOverworked = consecutiveShifts >= CONSECUTIVE_SHIFTS_WARNING_THRESHOLD;

  return (
    <button
      type="button"
      className={`${styles.card} ${isSelected ? styles.cardSelected : ""}`}
      onClick={() => selectWorker(worker.workerId)}
      aria-pressed={isSelected}
    >
      {/* Header: avatar + identitas */}
      <div className={styles.header}>
        <span className={styles.avatar}>{getInitials(worker.name)}</span>
        <div className={styles.identity}>
          <h3 className={styles.name}>{worker.name}</h3>
          <span className={styles.workerId}>{worker.workerId}</span>
        </div>
        {realtimeMetrics?.burnoutHazardRisk !== undefined && (
          <span
            className={`${styles.burnoutBadge} ${
              styles[`burnout-${realtimeMetrics.burnoutHazardRisk}`]
            }`}
          >
            {realtimeMetrics.burnoutHazardRisk}
          </span>
        )}
      </div>

      {/* Demografi */}
      <div className={styles.demographicsRow}>
        <span>{demographics?.age ?? 0} tahun</span>
        <span className={styles.dividerDot}>·</span>
        <span>{formatExperience(demographics?.yearsOfExperience ?? 0)}</span>
      </div>

      {/* Kapasitas baseline: stamina & resiliensi kognitif */}
      <div className={styles.capacityGrid}>
        <div className={styles.capacityItem}>
          <div className={styles.capacityLabelRow}>
            <span className={styles.readoutLabel}>Stamina Fisik</span>
            <span className={styles.readoutValue}>
              {((demographics?.baselinePhysicalStamina ?? 0) * 100).toFixed(0)}%
            </span>
          </div>
          <div className={styles.capacityBar}>
            <div
              className={`${styles.capacityFill} ${styles[`capacity-${staminaLevel}`]}`}
              style={{ width: `${(demographics?.baselinePhysicalStamina ?? 0) * 100}%` }}
            />
          </div>
        </div>
        <div className={styles.capacityItem}>
          <div className={styles.capacityLabelRow}>
            <span className={styles.readoutLabel}>Resiliensi Kognitif</span>
            <span className={styles.readoutValue}>
              {((demographics?.cognitiveResilience ?? 0) * 100).toFixed(0)}%
            </span>
          </div>
          <div className={styles.capacityBar}>
            <div
              className={`${styles.capacityFill} ${styles[`capacity-${resilienceLevel}`]}`}
              style={{ width: `${(demographics?.cognitiveResilience ?? 0) * 100}%` }}
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
            {consecutiveShifts}x
          </span>
        </div>
        <div className={styles.shiftTally} aria-hidden="true">
          {Array.from({ length: Math.max(consecutiveShifts, 5) }).map((_, i) => {
            const filled = i < consecutiveShifts;
            const warning = filled && i >= CONSECUTIVE_SHIFTS_WARNING_THRESHOLD - 1;
            return (
              <span
                key={i}
                className={`${styles.tallyMark} ${filled ? styles.tallyFilled : ""} ${
                  warning ? styles.tallyWarning : ""
                }`}
              />
            );
          })}
        </div>
        <span className={styles.hoursToday}>
          {formatHoursWorked(shiftContext?.hoursWorkedToday ?? 0)}
        </span>
      </div>

      {/* Real-time fatigue/stress, hanya tampil kalau data tersedia */}
      {realtimeMetrics && (
        <div className={styles.realtimeRow}>
          <RealtimeMeter
            label="Fatigue"
            value={realtimeMetrics.currentFatigueLevel ?? 0}
          />
          <RealtimeMeter
            label="Stres"
            value={realtimeMetrics.currentStressLevel ?? 0}
          />
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