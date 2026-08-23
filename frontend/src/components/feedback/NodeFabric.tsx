// frontend/src/components/feedback/NodeFabric.tsx
// Custom Node React Flow: stasiun kerja / proses pabrik.
// Elemen: header card, badge skill, target output, titik konektor (handles).
import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { CanvasFlowNode } from "@/features/canvas/types/canvas.types";
import { useCanvasUIStore } from "@/store/canvasUI";
import styles from "./NodeFabric.module.css";

export const NodeFabric = memo(function NodeFabric({ id, data, selected }: NodeProps<CanvasFlowNode>) {
  const activeTool = useCanvasUIStore((s) => s.activeTool);
  const selectedNodeId = useCanvasUIStore((s) => s.selectedNodeId);
  const setSelectedNode = useCanvasUIStore((s) => s.setSelectedNode);

  // NodeFabric hanya dirender untuk node proses — guard untuk narrow type union.
  if (data.kind !== "process") return null;

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
      <Handle type="target" id="target-top" position={Position.Top} className={styles.handle} />
      <Handle type="source" id="source-bottom" position={Position.Bottom} className={styles.handle} />

      <div className={styles.headerRow}>
        <span className={styles.nodeType}>PROSES</span>
        {data.aiStatus === "verified" && <span className={styles.verifiedBadge}>AI ✓</span>}
        {data.aiStatus === "analyzing" && <span className={styles.analyzingBadge}>…</span>}
        {data.aiStatus === "error" && <span className={styles.errorBadge}>!</span>}
      </div>
      <h3 className={styles.title}>{data.label}</h3>

      <div className={styles.skillList}>
        {data.requiredSkills.length === 0 ? (
          <span className={styles.noSkill}>Belum ada skill yang dibutuhkan</span>
        ) : (
          data.requiredSkills.map((skill) => (
            <span key={skill} className={styles.skillTag}>
              {skill}
            </span>
          ))
        )}
      </div>

      <div className={styles.footerRow}>
        <span className={styles.capacityLabel}>Target Output</span>
        <span className={styles.capacityValue}>
          {data.targetOutput > 0 ? `${data.targetOutput} unit/jam` : "—"}
        </span>
      </div>
    </div>
  );
});

export default NodeFabric;