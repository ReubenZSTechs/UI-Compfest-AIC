// features/simulation/components/WarehouseNode.tsx
import type { WarehouseState } from "../types/simulation.types";
import styles from "./WarehouseNode.module.css";

interface WarehouseNodeProps {
  warehouse: WarehouseState;
}

export function WarehouseNode({ warehouse }: WarehouseNodeProps) {
  const fillPct = Math.max(0, Math.min(100, (warehouse.current_stock / warehouse.capacity) * 100));

  return (
    <div className={styles.node}>
      <div className={styles.top}>
        <div className={styles.titleGroup}>
          <span className={styles.icon}></span>
          <span className={styles.title}>Gudang Bahan Baku</span>
        </div>
        <span className={styles.stockReadout}>
          {Math.round(warehouse.current_stock).toLocaleString("id-ID")} / {warehouse.capacity.toLocaleString("id-ID")} kg
        </span>
      </div>
      <div className={styles.stockTrack}>
        <div className={styles.stockFill} style={{ width: `${fillPct}%` }} />
      </div>
    </div>
  );
}