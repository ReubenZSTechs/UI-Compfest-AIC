// features/simulation/components/SimulationSummaryPanel.tsx
import { useSimulationStore } from "../store/simulationStore";
import styles from "./SimulationSummaryPanel.module.css";

function formatIdr(value: number) {
  return `Rp${Math.round(value).toLocaleString("id-ID")}`;
}

export function SimulationSummaryPanel() {
  const data = useSimulationStore((s) => s.data);
  const summary = data?.live_simulation_state.simulation_summary;
  const insight = data?.live_simulation_state.analytical_insight_summary;
  const bottlenecks = data?.live_simulation_state.system_bottlenecks ?? [];

  if (!summary) {
    return <div className={styles.waiting}>Menunggu data simulasi…</div>;
  }

  const achievementTone =
    summary.production_achievement_percentage >= 95
      ? styles.toneSafe
      : summary.production_achievement_percentage >= 80
        ? styles.toneWarning
        : styles.toneDanger;

  return (
    <div className={styles.panel}>
      <div className={styles.metricGrid}>
        <Metric label="Output" value={summary.total_output_units.toFixed(0)} unit={`/ ${summary.target_output_units.toFixed(0)} unit`} />
        <Metric
          label="Pencapaian"
          value={`${summary.production_achievement_percentage.toFixed(1)}%`}
          toneClassName={achievementTone}
        />
        <Metric label="Efisiensi" value={summary.efficiency_score.toFixed(1)} unit="/ 100" />
        <Metric label="Biaya Total" value={formatIdr(summary.total_operational_cost_idr)} />
        <Metric label="Biaya / Unit" value={formatIdr(summary.cost_per_unit_idr)} />
        <Metric
          label="Bottleneck Aktif"
          value={String(bottlenecks.length)}
          unit="stasiun"
          toneClassName={bottlenecks.length > 0 ? styles.toneDanger : styles.toneSafe}
        />
      </div>

      <div className={styles.progressTrack}>
        <div className={styles.progressFill} style={{ width: `${Math.min(100, summary.production_achievement_percentage)}%` }} />
      </div>

      {insight && (
        <div className={styles.insight}>
          <p className={styles.insightLabel}>Analytical Insight</p>
          <p className={styles.insightText}>{insight}</p>
        </div>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  unit,
  toneClassName,
}: {
  label: string;
  value: string;
  unit?: string;
  toneClassName?: string;
}) {
  return (
    <div className={styles.metric}>
      <p className={styles.metricLabel}>{label}</p>
      <p className={[styles.metricValue, toneClassName ?? ""].filter(Boolean).join(" ")}>
        {value}
        {unit && <span className={styles.metricUnit}>{unit}</span>}
      </p>
    </div>
  );
}