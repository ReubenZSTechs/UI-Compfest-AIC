import { useSimulationRunner } from "../hooks/useSimulationRunner";
import { useSimulationStore, type SpeedMultiplier } from "../store/simulationStore";
import styles from "./SimulationControls.module.css";

const SPEED_OPTIONS: SpeedMultiplier[] = [1, 2, 5, 10];

/** Start, pause, reset and speed controls for the client-side shift simulation. */
export function SimulationControls() {
  const status = useSimulationStore((s) => s.status);
  const tick = useSimulationStore((s) => s.tick);
  const data = useSimulationStore((s) => s.data);
  const speedMultiplier = useSimulationStore((s) => s.speedMultiplier);
  const start = useSimulationStore((s) => s.start);
  const pause = useSimulationStore((s) => s.pause);
  const reset = useSimulationStore((s) => s.reset);
  const setSpeedMultiplier = useSimulationStore((s) => s.setSpeedMultiplier);

  useSimulationRunner();

  const error = useSimulationStore((s) => s.error);
  const shiftInfo = data?.live_simulation_state?.shift_info;

  return (
    <div className={styles.controlsWrap}>
      {error && (
        <div className={styles.errorBanner} role="alert">
          <span className={styles.errorIcon}>⚠</span>
          <span className={styles.errorText}>{error}</span>
          <button type="button" onClick={reset} className={styles.errorRetry}>
            Coba lagi
          </button>
        </div>
      )}
      <div className={styles.controls}>
        <div className={styles.buttonGroup}>
          {status !== "running" ? (
              <button
                type="button"
                onClick={start}
                disabled={shiftInfo?.is_shift_ended || Boolean(error)}
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

        <div className={styles.statusReadout}>
          <span
            className={[
              styles.statusDot,
              status === "running" ? styles.statusDotRunning : "",
              status === "paused" || status === "completed" ? styles.statusDotPaused : "",
            ]
              .filter(Boolean)
              .join(" ")}
          />
          {status === "running" && `Tick #${tick} (${speedMultiplier}x)`}
          {status === "paused" && "Dijeda"}
          {status === "idle" && "Standby"}
          {status === "completed" && `Selesai (${tick} tick)`}
        </div>
      </div>
    </div>
  );
}