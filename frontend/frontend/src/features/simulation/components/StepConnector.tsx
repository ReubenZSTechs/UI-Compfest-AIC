// features/simulation/components/StepConnector.tsx
import type { ActiveTransfer } from "../types/simulation.types";
import styles from "./StepConnector.module.css";

interface StepConnectorProps {
  /** Present only on the tick this handoff actually happens; undefined = connector is dark. */
  transfer?: ActiveTransfer;
  isBottleneckAdjacent: boolean;
}

export function StepConnector({ transfer, isBottleneckAdjacent }: StepConnectorProps) {
  const isActive = Boolean(transfer);

  return (
    <div className={styles.connector}>
      <div className={styles.line}>
        <span
          key={transfer?.batch_code ?? "idle"} // re-mount on new batch so the blink animation replays each handoff
          className={[styles.light, isActive ? (isBottleneckAdjacent ? styles.lightActiveBottleneck : styles.lightActive) : ""]
            .filter(Boolean)
            .join(" ")}
        />
      </div>
      {transfer && (
        <span
          className={[styles.transferLabel, isBottleneckAdjacent ? styles.transferLabelBottleneck : ""]
            .filter(Boolean)
            .join(" ")}
        >
          {transfer.batch_code} · {transfer.unit === "kg" ? transfer.quantity.toFixed(1) : Math.round(transfer.quantity)}{" "}
          {transfer.unit}
        </span>
      )}
    </div>
  );
}