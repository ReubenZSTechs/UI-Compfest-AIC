// frontend/src/features/digital-twin/components/JobDeskTable.tsx

import { useMemo } from "react";
import type { JobDesk } from "../types/digitalTwin.types";
import {
  formatWorkflowStepLabel,
  ERROR_SEVERITY_LABEL,
  ERROR_SEVERITY_LEVEL,
  PHYSICAL_DEMAND_LABEL,
  PHYSICAL_DEMAND_LEVEL,
} from "../utils/formatMetrics";
import { useDigitalTwinStore } from "../store/digitalTwinStore";
import styles from "./JobDeskTable.module.css";

interface JobDeskTableProps {
  jobDesks?: JobDesk[] | null;
}

export function JobDeskTable({ jobDesks = [] }: JobDeskTableProps) {
  // Menjamin array selalu terdefinisi meskipun prop dikirim bernilai null
  const safeJobDesks = jobDesks ?? [];

  const selectedWorkflowStep = useDigitalTwinStore((s) => s.selectedWorkflowStep);
  const searchQuery = useDigitalTwinStore((s) => s.searchQuery);
  const selectedJobId = useDigitalTwinStore((s) => s.selectedJobId);
  const selectJob = useDigitalTwinStore((s) => s.selectJob);

  const filteredJobDesks = useMemo(() => {
    return safeJobDesks.filter((job) => {
      if (!job) return false;

      const matchesStep = selectedWorkflowStep
        ? job.workflowStep === selectedWorkflowStep
        : true;

      const query = searchQuery?.toLowerCase() ?? "";
      const matchesSearch = query
        ? (job.jobTitle?.toLowerCase().includes(query) ?? false) ||
          (job.jobId?.toLowerCase().includes(query) ?? false)
        : true;

      return matchesStep && matchesSearch;
    });
  }, [safeJobDesks, selectedWorkflowStep, searchQuery]);

  function handleRowKeyDown(e: React.KeyboardEvent, jobId: string) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      selectJob(jobId);
    }
  }

  if (filteredJobDesks.length === 0) {
    return (
      <div className={styles.emptyState}>
        Tidak ada job desk yang cocok dengan filter saat ini.
      </div>
    );
  }

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th className={styles.th}>Tugas</th>
            <th className={styles.th}>Tahap</th>
            <th className={styles.th}>Beban Fisik</th>
            <th className={styles.th}>Fokus &amp; Kompleksitas</th>
            <th className={styles.th}>Severitas Error</th>
            <th className={styles.th}>Syarat QC</th>
          </tr>
        </thead>
        <tbody>
          {filteredJobDesks.map((job) => {
            const isSelected = selectedJobId === job.jobId;

            // Safe fallback untuk objek demands
            const physicalDemand = job.demands?.physicalDemandLevel ?? "low";
            const errorSeverity = job.demands?.errorSeverity ?? "low";

            const demandLevel = PHYSICAL_DEMAND_LEVEL[physicalDemand] ?? "low";
            const severityLevel = ERROR_SEVERITY_LEVEL[errorSeverity] ?? "low";

            return (
              <tr
                key={job.jobId}
                className={`${styles.row} ${isSelected ? styles.rowSelected : ""}`}
                onClick={() => selectJob(job.jobId)}
                onKeyDown={(e) => handleRowKeyDown(e, job.jobId)}
                tabIndex={0}
                role="button"
                aria-pressed={isSelected}
              >
                <td className={styles.td}>
                  <div className={styles.jobTitleCell}>
                    <span className={styles.jobTitle}>
                      {job.jobTitle ?? job.jobId}
                    </span>
                    <span className={styles.jobId}>{job.jobId}</span>
                  </div>
                </td>

                <td className={styles.td}>
                  <span className={styles.stepTag}>
                    {formatWorkflowStepLabel(job.workflowStep ?? "")}
                  </span>
                </td>

                <td className={styles.td}>
                  <span
                    className={`${styles.demandBadge} ${styles[`badge-${demandLevel}`]}`}
                  >
                    {PHYSICAL_DEMAND_LABEL[physicalDemand] ?? physicalDemand}
                  </span>
                </td>

                <td className={styles.td}>
                  <div className={styles.dualBar}>
                    <MiniBar
                      label="Fokus"
                      value={job.demands?.requiredCognitiveFocus ?? 0}
                    />
                    <MiniBar
                      label="Kompleksitas"
                      value={job.demands?.taskComplexity ?? 0}
                    />
                  </div>
                </td>

                <td className={styles.td}>
                  <span
                    className={`${styles.severityBadge} ${styles[`badge-${severityLevel}`]}`}
                  >
                    {ERROR_SEVERITY_LABEL[errorSeverity] ?? errorSeverity}
                  </span>
                </td>

                <td className={styles.td}>
                  <span
                    className={styles.qcText}
                    title={job.qcRequirement ?? "-"}
                  >
                    {job.qcRequirement ?? "-"}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function MiniBar({ label, value }: { label: string; value: number }) {
  // Memastikan nilai persentase aman berada di rentang 0 - 1
  const safeValue = Math.min(Math.max(value ?? 0, 0), 1);

  return (
    <div className={styles.miniBarItem}>
      <span className={styles.miniBarLabel}>{label}</span>
      <div className={styles.miniBarTrack}>
        <div
          className={styles.miniBarFill}
          style={{ width: `${safeValue * 100}%` }}
        />
      </div>
    </div>
  );
}