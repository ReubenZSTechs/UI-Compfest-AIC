// features/simulation/components/SimulationSummaryPanel.tsx
import { useSimulationStore } from "../store/simulationStore";
import styles from "./SimulationSummaryPanel.module.css";

// function formatIdr(value: number) {
//   return `Rp${Math.round(value || 0).toLocaleString("id-ID")}`;
// }

export function SimulationSummaryPanel({ isMock }: { isMock?: boolean }) {
  const data = useSimulationStore((s) => s.data);
  const summary = data?.live_simulation_state?.simulation_summary;
  const insight = data?.live_simulation_state?.analytical_insight_summary;
  const bottlenecks = data?.live_simulation_state?.system_bottlenecks ?? [];

  if (!summary) {
    return <div className={styles.waiting}>Menunggu data simulasi{isMock ? " (MOCK)" : ""}…</div>;
  }

  const achievement = summary.production_achievement_percentage ?? 0;
  const achievementTone =
    achievement >= 95
      ? styles.toneSafe
      : achievement >= 80
        ? styles.toneWarning
        : styles.toneDanger;

  // Baca variabel baru yang dikirim dari store
  const humanErrors = summary.total_human_errors ?? 0;
  const workersRisk = summary.workers_at_risk ?? 0;

  return (
    <div className={styles.panel}>
      <div className={styles.metricGrid}>
        <Metric
          label="Output / Target"
          value={(summary.total_output_units ?? 0).toFixed(0)}
          unit={`/ ${(summary.target_output_units ?? 0).toFixed(0)} unit`}
        />
        <Metric
          label="Pencapaian"
          value={`${achievement.toFixed(1)}%`}
          toneClassName={achievementTone}
        />
        <Metric
          label="Efisiensi"
          value={(summary.efficiency_score ?? 0).toFixed(1)}
          unit="/ 100"
        />
        
        {/* --- METRIK BARU: HUMAN ERROR & BURN OUT --- */}
        <Metric
          label="Human Error"
          value={String(humanErrors)}
          unit="Insiden"
          toneClassName={humanErrors > 0 ? styles.toneDanger : styles.toneSafe}
        />
        <Metric
          label="Pekerja Kritis"
          value={String(workersRisk)}
          unit="Orang"
          toneClassName={workersRisk > 0 ? styles.toneDanger : styles.toneSafe}
        />
        
        <Metric
          label="Bottleneck Aktif"
          value={String(bottlenecks.length)}
          unit="Stasiun"
          toneClassName={bottlenecks.length > 0 ? styles.toneDanger : styles.toneSafe}
        />
      </div>

      <div className={styles.progressTrack}>
        <div
          className={styles.progressFill}
          style={{ width: `${Math.min(100, Math.max(0, achievement))}%` }}
        />
      </div>

      {insight && (
        <div className={styles.insight}>
          <p className={styles.insightLabel}>Analytical Insight {isMock && "[MOCK]"}</p>
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