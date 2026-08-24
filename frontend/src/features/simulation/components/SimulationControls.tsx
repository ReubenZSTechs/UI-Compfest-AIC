// features/simulation/components/SimulationControls.tsx

import { useSimulationRunner } from "../hooks/useSimulationRunner";
import { useSimulationStore, type SpeedMultiplier } from "../store/simulationStore";
import styles from "./SimulationControls.module.css";

const SPEED_OPTIONS: SpeedMultiplier[] = [1, 2, 5, 10];

// --- PEMBARUAN: Tambahkan parameter isMock ke dalam Props komponen ---
export function SimulationControls({ isMock }: { isMock?: boolean }) {
  const status = useSimulationStore((s) => s.status);
  const tick = useSimulationStore((s) => s.tick);
  const data = useSimulationStore((s) => s.data);
  const speedMultiplier = useSimulationStore((s) => s.speedMultiplier);
  const start = useSimulationStore((s) => s.start);
  const pause = useSimulationStore((s) => s.pause);
  const reset = useSimulationStore((s) => s.reset);
  const setSpeedMultiplier = useSimulationStore((s) => s.setSpeedMultiplier);

  // --- PEMBARUAN: Teruskan nilai isMock ke dalam runner hook ---
  useSimulationRunner(isMock);

  const shiftInfo = data?.live_simulation_state?.shift_info;

  return (
    <div className={styles.controls}>
      {/* Tombol Utama */}
      <div className={styles.buttonGroup}>
        {status !== "running" ? (
          <button
            type="button"
            onClick={start}
            disabled={shiftInfo?.is_shift_ended}
            className={styles.primaryButton}
          >
            {status === "paused" ? "Lanjutkan Simulasi" : "Mulai Simulasi"}
          </button>
        ) : (
          <button type="button" onClick={pause} className={styles.pauseButton}>
            Jeda
          </button>
        )}

        <button
          type="button"
          onClick={reset}
          disabled={status === "idle"}
          className={styles.resetButton}
        >
          Reset
        </button>
      </div>

      {/* Pengatur Kecepatan Simulasi (1x, 2x, 5x, 10x) */}
      <div className={styles.speedGroup}>
        <span className={styles.speedLabel}>Laju:</span>
        <div className={styles.speedButtons}>
          {SPEED_OPTIONS.map((speed) => (
            <button
              key={speed}
              type="button"
              onClick={() => setSpeedMultiplier(speed)}
              className={[
                styles.speedButton,
                speedMultiplier === speed ? styles.speedButtonActive : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              {speed}x
            </button>
          ))}
        </div>
      </div>

      {/* Indikator Waktu Operasional & Shift */}
      <div className={styles.shiftTimeContainer}>
        <div className={styles.clockDisplay}>
          <span className={styles.clockIcon}></span>
          <span className={styles.clockText}>
            {shiftInfo ? shiftInfo.current_time_formatted : "08:00"}
          </span>
        </div>

        {shiftInfo && (
          <div
            className={[
              styles.shiftBadge,
              shiftInfo.operational_status === "working" ? styles.shiftWorking : "",
              shiftInfo.operational_status === "break" ? styles.shiftBreak : "",
              shiftInfo.operational_status === "shift_ended" ? styles.shiftEnded : "",
            ]
              .filter(Boolean)
              .join(" ")}
          >
            {shiftInfo.operational_status === "working" && "JAM KERJA"}
            {shiftInfo.operational_status === "break" && "JAM ISTIRAHAT"}
            {shiftInfo.operational_status === "shift_ended" && "SHIFT SELESAI"}
          </div>
        )}
      </div>

      {/* Status Readout */}
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
        {status === "running" && `Tick #${tick} (${speedMultiplier}x)`}
        {status === "paused" && "Dijeda"}
        {status === "idle" && "Standby"}
      </div>
    </div>
  );
}