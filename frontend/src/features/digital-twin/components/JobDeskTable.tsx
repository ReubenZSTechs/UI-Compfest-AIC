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
  jobDesks: JobDesk[];
}

export function JobDeskTable({ jobDesks }: JobDeskTableProps) {
  const selectedWorkflowStep = useDigitalTwinStore((s) => s.selectedWorkflowStep);
  const searchQuery = useDigitalTwinStore((s) => s.searchQuery);
  const selectedJobId = useDigitalTwinStore((s) => s.selectedJobId);
  const selectJob = useDigitalTwinStore((s) => s.selectJob);

  const filteredJobDesks = useMemo(() => {
    return jobDesks.filter((job) => {
      const matchesStep = selectedWorkflowStep
        ? job.workflow_step === selectedWorkflowStep
        : true;
      const matchesSearch = searchQuery
        ? job.job_title.toLowerCase().includes(searchQuery.toLowerCase()) ||
          job.job_id.toLowerCase().includes(searchQuery.toLowerCase())
        : true;
      return matchesStep && matchesSearch;
    });
  }, [jobDesks, selectedWorkflowStep, searchQuery]);

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
            const isSelected = selectedJobId === job.job_id;
            const demandLevel = PHYSICAL_DEMAND_LEVEL[job.demands.physical_demand_level];
            const severityLevel = ERROR_SEVERITY_LEVEL[job.demands.error_severity];

            return (
              <tr
                key={job.job_id}
                className={`${styles.row} ${isSelected ? styles.rowSelected : ""}`}
                onClick={() => selectJob(job.job_id)}
                onKeyDown={(e) => handleRowKeyDown(e, job.job_id)}
                tabIndex={0}
                role="button"
                aria-pressed={isSelected}
              >
                <td className={styles.td}>
                  <div className={styles.jobTitleCell}>
                    <span className={styles.jobTitle}>{job.job_title}</span>
                    <span className={styles.jobId}>{job.job_id}</span>
                  </div>
                </td>

                <td className={styles.td}>
                  <span className={styles.stepTag}>
                    {formatWorkflowStepLabel(job.workflow_step)}
                  </span>
                </td>

                <td className={styles.td}>
                  <span
                    className={`${styles.demandBadge} ${styles[`badge-${demandLevel}`]}`}
                  >
                    {PHYSICAL_DEMAND_LABEL[job.demands.physical_demand_level]}
                  </span>
                </td>

                <td className={styles.td}>
                  <div className={styles.dualBar}>
                    <MiniBar
                      label="Fokus"
                      value={job.demands.required_cognitive_focus}
                    />
                    <MiniBar label="Kompleksitas" value={job.demands.task_complexity} />
                  </div>
                </td>

                <td className={styles.td}>
                  <span
                    className={`${styles.severityBadge} ${styles[`badge-${severityLevel}`]}`}
                  >
                    {ERROR_SEVERITY_LABEL[job.demands.error_severity]}
                  </span>
                </td>

                <td className={styles.td}>
                  <span className={styles.qcText} title={job.qc_requirement}>
                    {job.qc_requirement}
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
  return (
    <div className={styles.miniBarItem}>
      <span className={styles.miniBarLabel}>{label}</span>
      <div className={styles.miniBarTrack}>
        <div className={styles.miniBarFill} style={{ width: `${value * 100}%` }} />
      </div>
    </div>
  );
}