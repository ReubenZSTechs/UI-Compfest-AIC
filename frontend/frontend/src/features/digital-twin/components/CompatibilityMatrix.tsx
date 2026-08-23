// frontend/src/features/digital-twin/components/CompatibilityMatrix.tsx

import { useMemo } from "react";
import type { Worker, JobDesk, CompatibilityEvaluation } from "../types/digitalTwin.types";
import { getInitials } from "../utils/formatMetrics";
import { compatibilityScoreToColor, readableTextColor } from "../utils/colorScale";
import { useDigitalTwinStore } from "../store/digitalTwinStore";
import styles from "./CompatibilityMatrix.module.css";

interface CompatibilityMatrixProps {
  workers?: Worker[] | null;
  jobDesks?: JobDesk[] | null;
  evaluations?: CompatibilityEvaluation[] | null;
}

export function CompatibilityMatrix({
  workers = [],
  jobDesks = [],
  evaluations = [],
}: CompatibilityMatrixProps) {
  // Menjamin variabel selalu berupa array meskipun dikirim `null` secara eksplisit
  const safeWorkers = workers ?? [];
  const safeJobDesks = jobDesks ?? [];
  const safeEvaluations = evaluations ?? [];

  const selectedWorkerId = useDigitalTwinStore((s) => s.selectedWorkerId);
  const selectedJobId = useDigitalTwinStore((s) => s.selectedJobId);
  const selectPair = useDigitalTwinStore((s) => s.selectPair);

  const evaluationLookup = useMemo(() => {
    const map = new Map<string, CompatibilityEvaluation>();
    safeEvaluations.forEach((ev) => {
      if (ev?.workerId && ev?.jobId) {
        map.set(`${ev.workerId}__${ev.jobId}`, ev);
      }
    });
    return map;
  }, [safeEvaluations]);

  const activeEvaluation = useMemo(() => {
    if (!selectedWorkerId || !selectedJobId) return null;
    return evaluationLookup.get(`${selectedWorkerId}__${selectedJobId}`) ?? null;
  }, [evaluationLookup, selectedWorkerId, selectedJobId]);

  function handleCellClick(workerId: string, jobId: string) {
    selectPair(workerId, jobId);
  }

  function handleCellKeyDown(e: React.KeyboardEvent, workerId: string, jobId: string) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      handleCellClick(workerId, jobId);
    }
  }

  // Tampilan cadangan jika data pekerja atau job desk masih kosong
  if (safeWorkers.length === 0 || safeJobDesks.length === 0) {
    return (
      <div className={styles.wrapper}>
        <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted, #888)" }}>
          Data matriks kompatibilitas belum tersedia atau kosong.
        </div>
      </div>
    );
  }

  return (
    <div className={styles.wrapper}>
      {/* Legend — skala pada panel sensor */}
      <div className={styles.legend}>
        <span className={styles.legendLabel}>Skor Kompatibilitas</span>
        <div className={styles.legendBar} />
        <div className={styles.legendTicks}>
          <span>0.0</span>
          <span>0.5</span>
          <span>1.0</span>
        </div>
      </div>

      <div className={styles.matrixScroll}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.cornerCell} />
              {safeJobDesks.map((job) => (
                <th
                  key={job.jobId}
                  className={`${styles.colHeader} ${
                    selectedJobId === job.jobId ? styles.headerActive : ""
                  }`}
                  title={job.jobTitle}
                >
                  <span className={styles.colHeaderText}>{job.jobId}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {safeWorkers.map((worker) => (
              <tr key={worker.workerId}>
                <th
                  className={`${styles.rowHeader} ${
                    selectedWorkerId === worker.workerId ? styles.headerActive : ""
                  }`}
                >
                  <span className={styles.rowAvatar}>{getInitials(worker.name ?? "")}</span>
                  <span className={styles.rowName}>{worker.name ?? worker.workerId}</span>
                </th>

                {safeJobDesks.map((job) => {
                  const evaluation = evaluationLookup.get(
                    `${worker.workerId}__${job.jobId}`
                  );
                  const isSelected =
                    selectedWorkerId === worker.workerId && selectedJobId === job.jobId;
                  const inSelectedRowOrCol =
                    selectedWorkerId === worker.workerId ||
                    selectedJobId === job.jobId;

                  if (!evaluation) {
                    return (
                      <td key={job.jobId} className={styles.cellEmpty} aria-disabled="true">
                        <span className={styles.emptyDash}>—</span>
                      </td>
                    );
                  }

                  const score = evaluation.evaluations?.overallCompatibilityScore ?? 0;
                  const bg = compatibilityScoreToColor(score);
                  const textColor = readableTextColor(score);

                  return (
                    <td
                      key={job.jobId}
                      className={`${styles.cell} ${isSelected ? styles.cellSelected : ""} ${
                        inSelectedRowOrCol && !isSelected ? styles.cellDimmed : ""
                      }`}
                      style={{ backgroundColor: bg, color: textColor }}
                      onClick={() => handleCellClick(worker.workerId, job.jobId)}
                      onKeyDown={(e) => handleCellKeyDown(e, worker.workerId, job.jobId)}
                      tabIndex={0}
                      role="button"
                      aria-pressed={isSelected}
                      aria-label={`Kompatibilitas ${worker.name} dengan ${job.jobTitle}: ${score.toFixed(2)}`}
                    >
                      {score.toFixed(2)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Detail panel — muncul saat sel evaluasi terpilih */}
      {activeEvaluation && (
        <div className={styles.detailPanel}>
          <div className={styles.detailHeader}>
            <span className={styles.detailPairId}>
              {activeEvaluation.workerId} → {activeEvaluation.jobId}
            </span>
            <span
              className={styles.detailScore}
              style={{
                color: compatibilityScoreToColor(
                  activeEvaluation.evaluations?.overallCompatibilityScore ?? 0
                ),
              }}
            >
              {(activeEvaluation.evaluations?.overallCompatibilityScore ?? 0).toFixed(2)}
            </span>
          </div>

          <div className={styles.detailMetricsGrid}>
            <DetailMetric
              label="Throughput"
              value={`${(activeEvaluation.evaluations?.throughputMultiplier ?? 1).toFixed(2)}x`}
            />
            <DetailMetric
              label="Error Multiplier"
              value={`${(activeEvaluation.evaluations?.errorMultiplier ?? 1).toFixed(2)}x`}
            />
            <DetailMetric
              label="Akumulasi Fatigue"
              value={
                activeEvaluation.evaluations?.fatigueAccumulationRate !== undefined &&
                activeEvaluation.evaluations?.fatigueAccumulationRate !== null
                  ? `${activeEvaluation.evaluations.fatigueAccumulationRate.toFixed(2)}x`
                  : "-"
              }
            />
            <DetailMetric
              label="Sensitivitas Stres"
              value={
                activeEvaluation.evaluations?.stressSensitivityFactor !== undefined &&
                activeEvaluation.evaluations?.stressSensitivityFactor !== null
                  ? `${activeEvaluation.evaluations.stressSensitivityFactor.toFixed(2)}x`
                  : "-"
              }
            />
          </div>

          {activeEvaluation.llmReasoning && (
            <p className={styles.detailReasoning}>{activeEvaluation.llmReasoning}</p>
          )}
        </div>
      )}
    </div>
  );
}

function DetailMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className={styles.detailMetricItem}>
      <span className={styles.detailMetricLabel}>{label}</span>
      <span className={styles.detailMetricValue}>{value}</span>
    </div>
  );
}