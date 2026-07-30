// features/simulation/components/SpeedControls.tsx

import React from 'react';
import { useSimulationStore, type SpeedMultiplier } from '../store/simulationStore';
import styles from './SpeedControls.module.css';

const SPEED_OPTIONS: SpeedMultiplier[] = [1, 2, 5, 10];

export function SpeedControls() {
  const currentSpeed = useSimulationStore((s) => s.speedMultiplier);
  const setSpeedMultiplier = useSimulationStore((s) => s.setSpeedMultiplier);

  return (
    <div className={styles.speedGroup}>
      <span className={styles.speedLabel}>Laju:</span>
      <div className={styles.buttonGroup}>
        {SPEED_OPTIONS.map((speed) => (
          <button
            key={speed}
            type="button"
            onClick={() => setSpeedMultiplier(speed)}
            className={[
              styles.speedButton,
              currentSpeed === speed ? styles.active : '',
            ]
              .filter(Boolean)
              .join(' ')}
          >
            {speed}x
          </button>
        ))}
      </div>
    </div>
  );
}