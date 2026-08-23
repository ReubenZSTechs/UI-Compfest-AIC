// features/simulation/hooks/useSimulationRunner.ts

import { useEffect, useRef } from 'react';
import { fetchLiveSimulationState } from '../api/simulationApi';
import { useSimulationStore } from '../store/simulationStore';
import type { SimulationResponse } from '../types/simulation.types';

// Kecepatan normal (1x) = 1 tick per 1000 ms
const BASE_TICK_INTERVAL_MS = 1000;

export function useSimulationRunner() {
  const status = useSimulationStore((s) => s.status);
  const speedMultiplier = useSimulationStore((s) => s.speedMultiplier);
  const pause = useSimulationStore((s) => s.pause);
  const setData = useSimulationStore((s) => s.setData);
  const incrementTick = useSimulationStore((s) => s.incrementTick);

  const latestDataRef = useRef<SimulationResponse | null>(null);
  latestDataRef.current = useSimulationStore.getState().data;

  useEffect(() => {
    if (status !== 'running') return undefined;

    let cancelled = false;

    const runTick = async () => {
      const next = await fetchLiveSimulationState(latestDataRef.current ?? undefined);
      if (cancelled) return;
      
      latestDataRef.current = next;
      setData(next);
      incrementTick();

      // Otomatis pause jika shift operasional selesai (17:00)
      if (next.live_simulation_state.shift_info?.is_shift_ended) {
        pause();
      }
    };

    // Hitung interval berdasarkan multiplier
    // 1x = 1000ms | 2x = 500ms | 5x = 200ms | 10x = 100ms
    const intervalMs = BASE_TICK_INTERVAL_MS / speedMultiplier;

    runTick();
    const intervalId = window.setInterval(runTick, intervalMs);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [status, speedMultiplier, setData, incrementTick, pause]);
}