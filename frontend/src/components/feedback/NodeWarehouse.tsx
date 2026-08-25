import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { CanvasFlowNode } from "@/features/canvas/types/canvas.types";
import { useCanvasUIStore } from "@/store/canvasUI";
import styles from "./NodeWarehouse.module.css";

export const NodeWarehouse = memo(function NodeWarehouse({
  id,
  data,
  selected,
}: NodeProps<CanvasFlowNode>) {
  const activeTool = useCanvasUIStore((s) => s.activeTool);
  const selectedNodeId = useCanvasUIStore((s) => s.selectedNodeId);
  const setSelectedNode = useCanvasUIStore((s) => s.setSelectedNode);

  if (data.kind !== "warehouse") return null;

  const isSelected = selected || selectedNodeId === id;

  function handleClick() {
    if (activeTool === "erase") {
      useCanvasUIStore.getState().removeElement(id);
      return;
    }
    setSelectedNode(id);
  }

  return (
    <div
      className={`${styles.card} ${isSelected ? styles.selected : ""} ${styles[`ai-${data.aiStatus}`]}`}
      onClick={handleClick}
      role="button"
      tabIndex={0}
    >
      <Handle type="source" id="source-bottom" position={Position.Bottom} className={styles.handle} />

      <div className={styles.headerRow}>
        <span className={styles.nodeType}>GUDANG</span>
        {data.aiStatus === "verified" && <span className={styles.verifiedBadge}>AI ✓</span>}
        {data.aiStatus === "analyzing" && <span className={styles.analyzingBadge}>…</span>}
        {data.aiStatus === "error" && <span className={styles.errorBadge}>!</span>}
      </div>
      <h3 className={styles.title}>{data.label || "Gudang Bahan Baku"}</h3>

      <div className={styles.rows}>
        <div className={styles.row}>
          <span className={styles.rowLabel}>Kapasitas</span>
          <span className={styles.rowValue}>
            {data.capacity} {data.materialUnit}
          </span>
        </div>
        <div className={styles.row}>
          <span className={styles.rowLabel}>Laju Suplai</span>
          <span className={styles.rowValue}>
            {data.feedRate} {data.materialUnit}/menit
          </span>
        </div>
        <div className={styles.row}>
          <span className={styles.rowLabel}>Material</span>
          <span className={styles.rowValue}>{data.materialName || "—"}</span>
        </div>
      </div>
    </div>
  );
});

export default NodeWarehouse;