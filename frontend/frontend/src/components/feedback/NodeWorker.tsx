// frontend/src/components/feedback/NodeWorker.tsx
// Custom Node React Flow: profil pekerja.
// Membungkus komponen lama WorkerCard (REUSE UI) + titik konektor (handles).
import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { WorkerCard } from "@/features/digital-twin/components/WorkerCard";
import type { CanvasFlowNode } from "@/features/canvas/types/canvas.types";
import { useCanvasUIStore } from "@/store/canvasUI";
import styles from "./NodeWorker.module.css";

export const NodeWorker = memo(function NodeWorker({ id, data, selected }: NodeProps<CanvasFlowNode>) {
  const activeTool = useCanvasUIStore((s) => s.activeTool);
  const selectedNodeId = useCanvasUIStore((s) => s.selectedNodeId);
  const setSelectedNode = useCanvasUIStore((s) => s.setSelectedNode);

  // NodeWorker hanya dirender untuk node pekerja — guard untuk narrow type union.
  if (data.kind !== "worker") return null;

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
      className={`${styles.wrapper} ${isSelected ? styles.selected : ""} ${styles[`ai-${data.aiStatus}`]}`}
      onClick={handleClick}
      role="button"
      tabIndex={0}
    >
      <Handle type="source" id="source-right" position={Position.Right} className={styles.handle} />
      <Handle type="source" id="source-left" position={Position.Left} className={styles.handle} />

      <WorkerCard
        worker={data.worker}
        realtimeMetrics={{
          currentFatigueLevel: data.fatigueScore / 100,
          currentStressLevel: Math.min(0.95, data.fatigueScore / 140),
          burnoutHazardRisk:
            data.fatigueScore >= 70 ? "critical" : data.fatigueScore >= 45 ? "high" : data.fatigueScore >= 25 ? "medium" : "low",
        }}
      />

      <div className={styles.footerRow}>
        <span className={styles.roleTag}>PEKERJA</span>
        <span className={styles.roleTag}>→ PROSES</span>
      </div>
    </div>
  );
});

export default NodeWorker;