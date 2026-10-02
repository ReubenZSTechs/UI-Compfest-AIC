import { useEffect } from 'react';
import { fetchLiveSimulationState } from '../api/simulationApi';
import { useSimulationStore } from '../store/simulationStore';

const BASE_TICK_INTERVAL_MS = 1000;

/** Drives the client-side simulation tick loop while the store status is "running". */
export function useSimulationRunner() {
  const status = useSimulationStore((s) => s.status);
  const speedMultiplier = useSimulationStore((s) => s.speedMultiplier);
  const pause = useSimulationStore((s) => s.pause);
  const complete = useSimulationStore((s) => s.complete);
  const setData = useSimulationStore((s) => s.setData);
  const setError = useSimulationStore((s) => s.setError);
  const incrementTick = useSimulationStore((s) => s.incrementTick);

  useEffect(() => {
    if (status !== 'running') return undefined;

    let cancelled = false;

    const runTick = async () => {
      try {
        const previous = useSimulationStore.getState().data;
        const next = await fetchLiveSimulationState(previous ?? undefined);
        if (cancelled) return;

        setData(next);
        incrementTick();

        if (next.live_simulation_state.shift_info?.is_shift_ended) {
          complete();
        }
      } catch (error) {
        if (cancelled) return;

        setError(
          error instanceof Error
            ? error.message
            : 'Simulasi berhenti karena kesalahan tak terduga.'
        );
        pause();
      }
    };

    const intervalMs = BASE_TICK_INTERVAL_MS / speedMultiplier;

    void runTick();
    const intervalId = window.setInterval(() => void runTick(), intervalMs);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [status, speedMultiplier, setData, setError, incrementTick, pause, complete]);
}
