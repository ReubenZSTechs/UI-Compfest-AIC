// features/simulation/hooks/useSimulationRunner.ts
import { useEffect, useRef } from 'react';
import { fetchLiveSimulationState } from '../api/simulationApi';
import { useSimulationStore } from '../store/simulationStore';
import type { SimulationResponse } from '../types/simulation.types';

const TICK_INTERVAL_MS = 2500;

/** Mount once near the flowchart. While status === 'running' it polls for a new
 * snapshot every TICK_INTERVAL_MS and writes it into the store. Pausing freezes
 * on the last snapshot; resuming continues from it rather than resetting. */
export function useSimulationRunner() {
  const status = useSimulationStore((s) => s.status);
  const setData = useSimulationStore((s) => s.setData);
  const incrementTick = useSimulationStore((s) => s.incrementTick);

  // REVISI (bug fix -- lihat penjelasan sama di features/simulation/hooks/useSimulationRunner.ts):
  // ref disinkronkan lewat store.subscribe() dalam efek, bukan dimutasi
  // langsung di badan render.
  const latestDataRef = useRef<SimulationResponse | null>(useSimulationStore.getState().data);

  useEffect(() => {
    return useSimulationStore.subscribe((state) => {
      latestDataRef.current = state.data;
    });
  }, []);

  useEffect(() => {
    if (status !== 'running') return undefined;

    let cancelled = false;

    const runTick = async () => {
      const next = await fetchLiveSimulationState(latestDataRef.current ?? undefined);
      if (cancelled) return;
      latestDataRef.current = next;
      setData(next);
      incrementTick();
    };

    // fire immediately so the flowchart populates as soon as "Mulai Simulasi" is pressed
    runTick();
    const intervalId = window.setInterval(runTick, TICK_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [status, setData, incrementTick]);
}