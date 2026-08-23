// frontend/src/components/feedback/NodeOutput.tsx
// Custom Node React Flow: Node Output (Finished Goods Storage) — ujung alur
// produksi. Menerima aliran dari proses (target-top) dan menampilkan target
// output vs total output sesuai simulation_summary di project.md.
import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { CanvasFlowNode } from "@/features/canvas/types/canvas.types";
import { useCanvasUIStore } from "@/store/canvasUI";
import styles from "./NodeOutput.module.css";

export const NodeOutput = memo(function NodeOutput({ id, data, selected }: NodeProps<CanvasFlowNode>) {
  const activeTool = useCanvasUIStore((s) => s.activeTool);
  const selectedNodeId = useCanvasUIStore((s) => s.selectedNodeId);
  const setSelectedNode = useCanvasUIStore((s) => s.setSelectedNode);

  // NodeOutput hanya dirender untuk node output — guard untuk narrow type union.
  if (data.kind !== "output") return null;

  const isSelected = selected || selectedNodeId === id;
  const achievement =
    data.targetOutput > 0 ? Math.round((data.totalOutput / data.targetOutput) * 100) : 0;

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
      <Handle type="target" id="target-top" position={Position.Top} className={styles.handle} />

      <div className={styles.headerRow}>
        <span className={styles.nodeType}>OUTPUT</span>
        {data.aiStatus === "verified" && <span className={styles.verifiedBadge}>AI ✓</span>}
        {data.aiStatus === "analyzing" && <span className={styles.analyzingBadge}>…</span>}
        {data.aiStatus === "error" && <span className={styles.errorBadge}>!</span>}
      </div>
      <h3 className={styles.title}>{data.label || "Output / Finished Goods"}</h3>

      <div className={styles.rows}>
        <div className={styles.row}>
          <span className={styles.rowLabel}>Target Output</span>
          <span className={styles.rowValue}>
            {data.targetOutput > 0 ? `${data.targetOutput} unit/jam` : "—"}
          </span>
        </div>
        <div className={styles.row}>
          <span className={styles.rowLabel}>Total Output</span>
          <span className={styles.rowValue}>
            {data.totalOutput > 0 ? `${data.totalOutput} unit` : "—"}
          </span>
        </div>
      </div>

      <div className={styles.achievementBlock}>
        <div className={styles.achievementHeader}>
          <span className={styles.achievementLabel}>Pencapaian</span>
          <span className={styles.achievementValue}>
            {data.targetOutput > 0 ? `${achievement}%` : "—"}
          </span>
        </div>
        {data.targetOutput > 0 && (
          <div className={styles.progressTrack} aria-hidden="true">
            <div
              className={styles.progressFill}
              style={{ width: `${Math.min(100, achievement)}%` }}
            />
          </div>
        )}
      </div>
    </div>
  );
});

export default NodeOutput;