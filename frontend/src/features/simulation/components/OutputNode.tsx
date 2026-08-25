// features/simulation/components/OutputNode.tsx
import type { OutputSinkState } from "../types/simulation.types";
import styles from "./WarehouseNode.module.css";

interface OutputNodeProps {
  output: OutputSinkState;
}

export function OutputNode({ output }: OutputNodeProps) {
  const fillPct = Math.max(
    0,
    Math.min(100, (output.total_output_units / output.target_output_units) * 100)
  );
  
  return (
    <div className={styles.node}>
      <div className={styles.top}>
        <div className={styles.titleGroup}>
          <span className={styles.icon}>▤</span>
          <span className={styles.title}>{output.output_name}</span>
        </div>
        <span className={styles.stockReadout}>
          {Math.round(output.total_output_units).toLocaleString("id-ID")} / {output.target_output_units.toLocaleString("id-ID")} {output.material_unit}
        </span>
      </div>
      <div className={styles.stockTrack}>
        <div className={styles.stockFill} style={{ width: `${fillPct}%` }} />
      </div>
      {output.defective_units > 0 && (
        <p className={styles.defectiveNote}>{output.defective_units} unit cacat</p>
      )}
    </div>
  );
}