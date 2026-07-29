// features/simulation/components/SimulationControls.tsx
import { useSimulationRunner } from "../hooks/useSimulationRunner";
import { useSimulationStore } from "../store/simulationStore";
import styles from "./SimulationControls.module.css";

export function SimulationControls() {
  const status = useSimulationStore((s) => s.status);
  const tick = useSimulationStore((s) => s.tick);
  const start = useSimulationStore((s) => s.start);
  const pause = useSimulationStore((s) => s.pause);
  const reset = useSimulationStore((s) => s.reset);

  // Owns the polling lifecycle; safe to mount alongside the flowchart in the same page.
  useSimulationRunner();

  return (
    <div className={styles.controls}>
      {status !== "running" ? (
        <button type="button" onClick={start} className={styles.primaryButton}>
          {status === "paused" ? "Lanjutkan Simulasi" : "Mulai Simulasi"}
        </button>
      ) : (
        <button type="button" onClick={pause} className={styles.pauseButton}>
          Jeda
        </button>
      )}

      <button type="button" onClick={reset} disabled={status === "idle"} className={styles.resetButton}>
        Reset
      </button>

      <div className={styles.statusReadout}>
        <span
          className={[
            styles.statusDot,
            status === "running" ? styles.statusDotRunning : "",
            status === "paused" ? styles.statusDotPaused : "",
          ]
            .filter(Boolean)
            .join(" ")}
        />
        {status === "running" && `Tick #${tick}`}
        {status === "paused" && "Dijeda"}
        {status === "idle" && "Standby"}
      </div>
    </div>
  );
}