import { useEffect, useMemo, useRef, useState } from "react";
import { formatStationLabel } from "../utils/mapRlScenario";
import type { RlScenario, RlStaffPosition } from "../types/rlScenario.types";
import styles from "./RlFlowSimulation.module.css";

const STEP_INTERVAL_MS = 1400;

interface StationLane {
  stationId: string;
  label: string;
  isAutomated: boolean;
  isBottleneck: boolean;
  occupants: RlStaffPosition[];
}

interface Props {
  scenario: RlScenario;
}

function fatigueTone(value: number): string {
  if (value >= 0.65) return styles.toneDanger;
  if (value >= 0.45) return styles.toneWarning;
  return styles.toneSafe;
}

export function RlFlowSimulation({ scenario }: Props) {
  const flow = scenario.factory_flow_optimal;
  const moves = flow.reallocation_moves;

  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    setStep(0);
    setPlaying(false);
  }, [scenario.scenario_id]);

  useEffect(() => {
    if (!playing) return undefined;

    timerRef.current = window.setInterval(() => {
      setStep((current) => {
        if (current >= moves.length) {
          setPlaying(false);
          return current;
        }
        return current + 1;
      });
    }, STEP_INTERVAL_MS);

    return () => {
      if (timerRef.current !== null) {
        window.clearInterval(timerRef.current);
      }
    };
  }, [playing, moves.length]);

  const appliedMoveIds = useMemo(
    () => new Set(moves.slice(0, step).map((move) => move.move_id)),
    [moves, step]
  );

  const lanes = useMemo<StationLane[]>(() => {
    const automated = new Set(
      flow.asset_upgrades.map((upgrade) => upgrade.workflow_step ?? "")
    );

    const order: string[] = [];
    flow.optimal_staff_positions.forEach((position) => {
      [position.current_station_rightnow, position.optimal_station].forEach(
        (station) => {
          if (station && !order.includes(station)) {
            order.push(station);
          }
        }
      );
    });

    return order.map((stationId) => ({
      stationId,
      label: formatStationLabel(stationId),
      isAutomated: automated.has(stationId),
      isBottleneck: flow.residual_bottleneck === stationId,
      occupants: flow.optimal_staff_positions.filter((position) => {
        const settled =
          position.action === "stay" ||
          (position.move_id ? appliedMoveIds.has(position.move_id) : false);
        const station = settled
          ? position.optimal_station
          : position.current_station_rightnow;
        return station === stationId;
      }),
    }));
  }, [flow, appliedMoveIds]);

  const activeMove = step > 0 ? moves[step - 1] : null;
  const progress = moves.length === 0 ? 100 : (step / moves.length) * 100;

  return (
    <div className={styles.wrapper}>
      <div className={styles.toolbar}>
        <div className={styles.toolbarLeft}>
          <button
            type="button"
            className={styles.playButton}
            onClick={() => setPlaying((value) => !value)}
            disabled={moves.length === 0 || step >= moves.length}
          >
            {playing ? "Jeda" : "Putar Rotasi"}
          </button>
          <button
            type="button"
            className={styles.stepButton}
            onClick={() => setStep((value) => Math.min(value + 1, moves.length))}
            disabled={step >= moves.length}
          >
            Langkah →
          </button>
          <button
            type="button"
            className={styles.stepButton}
            onClick={() => {
              setPlaying(false);
              setStep(0);
            }}
            disabled={step === 0}
          >
            Ulangi
          </button>
        </div>

        <div className={styles.toolbarRight}>
          <span className={styles.stepCounter}>
            {step} / {moves.length} rotasi
          </span>
          <span className={styles.rewardChip}>
            Reward {scenario.episode_reward.toFixed(3)}
          </span>
        </div>
      </div>

      <div className={styles.progressTrack}>
        <div className={styles.progressFill} style={{ width: `${progress}%` }} />
      </div>

      {activeMove && (
        <div className={styles.moveBanner}>
          <span className={styles.moveTag}>{activeMove.move_id}</span>
          <span className={styles.moveText}>
            {activeMove.name} · {formatStationLabel(activeMove.from_station)} →{" "}
            {formatStationLabel(activeMove.to_station)}
          </span>
          <span className={styles.moveMetric}>
            Fatigue {(activeMove.final_fatigue * 100).toFixed(0)}% · Stress{" "}
            {(activeMove.final_stress * 100).toFixed(0)}%
          </span>
        </div>
      )}

      <div className={styles.lanes}>
        {lanes.map((lane, index) => (
          <div
            key={lane.stationId}
            className={[
              styles.lane,
              lane.isBottleneck ? styles.laneBottleneck : "",
              lane.isAutomated ? styles.laneAutomated : "",
            ]
              .filter(Boolean)
              .join(" ")}
          >
            <div className={styles.laneHeader}>
              <span className={styles.laneIndex}>
                {String(index + 1).padStart(2, "0")}
              </span>
              <span className={styles.laneLabel}>{lane.label}</span>
              {lane.isAutomated && (
                <span className={styles.laneBadgeAuto}>AUTO</span>
              )}
              {lane.isBottleneck && (
                <span className={styles.laneBadgeBottleneck}>BOTTLENECK</span>
              )}
            </div>

            <div className={styles.laneBody}>
              {lane.occupants.length === 0 ? (
                <span className={styles.laneEmpty}>
                  {lane.isAutomated ? "Dijalankan mesin" : "Kosong"}
                </span>
              ) : (
                lane.occupants.map((occupant) => (
                  <div key={occupant.worker_id} className={styles.workerChip}>
                    <div className={styles.workerTop}>
                      <span className={styles.workerName}>{occupant.name}</span>
                      {occupant.action === "moved" && (
                        <span className={styles.workerMoved}>rotasi</span>
                      )}
                    </div>

                    <div className={styles.gaugeRow}>
                      <span className={styles.gaugeLabel}>F</span>
                      <div className={styles.gaugeTrack}>
                        <div
                          className={`${styles.gaugeFill} ${fatigueTone(
                            occupant.projected_fatigue
                          )}`}
                          style={{
                            width: `${occupant.projected_fatigue * 100}%`,
                          }}
                        />
                      </div>
                      <span className={styles.gaugeValue}>
                        {(occupant.projected_fatigue * 100).toFixed(0)}%
                      </span>
                    </div>

                    <div className={styles.gaugeRow}>
                      <span className={styles.gaugeLabel}>S</span>
                      <div className={styles.gaugeTrack}>
                        <div
                          className={`${styles.gaugeFill} ${fatigueTone(
                            occupant.projected_stress
                          )}`}
                          style={{
                            width: `${occupant.projected_stress * 100}%`,
                          }}
                        />
                      </div>
                      <span className={styles.gaugeValue}>
                        {(occupant.projected_stress * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default RlFlowSimulation;