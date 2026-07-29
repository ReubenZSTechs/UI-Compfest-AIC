import { useMemo } from "react";
import type { Worker, JobDesk, CompatibilityEvaluation } from "../types/digitalTwin.types";
import { getInitials } from "../utils/formatMetrics";
import { compatibilityScoreToColor, readableTextColor } from "../utils/colorScale";
import { useDigitalTwinStore } from "../store/digitalTwinStore";
import styles from "./CompatibilityMatrix.module.css";

interface CompatibilityMatrixProps {
  workers: Worker[];
  jobDesks: JobDesk[];
  evaluations: CompatibilityEvaluation[];
}

export function CompatibilityMatrix({
  workers,
  jobDesks,
  evaluations,
}: CompatibilityMatrixProps) {
  const selectedWorkerId = useDigitalTwinStore((s) => s.selectedWorkerId);
  const selectedJobId = useDigitalTwinStore((s) => s.selectedJobId);
  const selectPair = useDigitalTwinStore((s) => s.selectPair);

  const evaluationLookup = useMemo(() => {
    const map = new Map<string, CompatibilityEvaluation>();
    evaluations.forEach((ev) => {
      map.set(`${ev.worker_id}__${ev.job_id}`, ev);
    });
    return map;
  }, [evaluations]);

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

  return (
    <div className={styles.wrapper}>
      {/* Legend — mirip skala pada panel sensor */}
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
              {jobDesks.map((job) => (
                <th
                  key={job.job_id}
                  className={`${styles.colHeader} ${
                    selectedJobId === job.job_id ? styles.headerActive : ""
                  }`}
                  title={job.job_title}
                >
                  <span className={styles.colHeaderText}>{job.job_id}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {workers.map((worker) => (
              <tr key={worker.worker_id}>
                <th
                  className={`${styles.rowHeader} ${
                    selectedWorkerId === worker.worker_id ? styles.headerActive : ""
                  }`}
                >
                  <span className={styles.rowAvatar}>{getInitials(worker.name)}</span>
                  <span className={styles.rowName}>{worker.name}</span>
                </th>

                {jobDesks.map((job) => {
                  const evaluation = evaluationLookup.get(
                    `${worker.worker_id}__${job.job_id}`
                  );
                  const isSelected =
                    selectedWorkerId === worker.worker_id && selectedJobId === job.job_id;
                  const inSelectedRowOrCol =
                    selectedWorkerId === worker.worker_id ||
                    selectedJobId === job.job_id;

                  if (!evaluation) {
                    return (
                      <td key={job.job_id} className={styles.cellEmpty} aria-disabled="true">
                        <span className={styles.emptyDash}>—</span>
                      </td>
                    );
                  }

                  const score = evaluation.evaluations.overall_compatibility_score;
                  const bg = compatibilityScoreToColor(score);
                  const textColor = readableTextColor(score);

                  return (
                    <td
                      key={job.job_id}
                      className={`${styles.cell} ${isSelected ? styles.cellSelected : ""} ${
                        inSelectedRowOrCol && !isSelected ? styles.cellDimmed : ""
                      }`}
                      style={{ backgroundColor: bg, color: textColor }}
                      onClick={() => handleCellClick(worker.worker_id, job.job_id)}
                      onKeyDown={(e) => handleCellKeyDown(e, worker.worker_id, job.job_id)}
                      tabIndex={0}
                      role="button"
                      aria-pressed={isSelected}
                      aria-label={`Kompatibilitas ${worker.name} dengan ${job.job_title}: ${score.toFixed(2)}`}
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
              {activeEvaluation.worker_id} → {activeEvaluation.job_id}
            </span>
            <span
              className={styles.detailScore}
              style={{
                color: compatibilityScoreToColor(
                  activeEvaluation.evaluations.overall_compatibility_score
                ),
              }}
            >
              {activeEvaluation.evaluations.overall_compatibility_score.toFixed(2)}
            </span>
          </div>

          <div className={styles.detailMetricsGrid}>
            <DetailMetric
              label="Throughput"
              value={`${activeEvaluation.evaluations.throughput_multiplier.toFixed(2)}x`}
            />
            <DetailMetric
              label="Error Multiplier"
              value={`${activeEvaluation.evaluations.error_multiplier.toFixed(2)}x`}
            />
            <DetailMetric
              label="Akumulasi Fatigue"
              value={`${activeEvaluation.evaluations.fatigue_accumulation_rate.toFixed(2)}x`}
            />
            <DetailMetric
              label="Sensitivitas Stres"
              value={`${activeEvaluation.evaluations.stress_sensitivity_factor.toFixed(2)}x`}
            />
          </div>

          <p className={styles.detailReasoning}>{activeEvaluation.llm_reasoning}</p>
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