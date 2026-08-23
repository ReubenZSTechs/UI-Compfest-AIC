// frontend/src/features/canvas/components/edges.tsx
// Custom edges React Flow: FLOW (flow / flow paralel / join) vs ASSIGNED_TO.
import { memo, useMemo } from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type EdgeProps,
} from "@xyflow/react";
import { useCanvasUIStore } from "@/store/canvasUI";
import type { CanvasFlowEdge } from "../types/canvas.types";
import styles from "./edges.module.css";

export const FlowEdge = memo(function FlowEdge(props: EdgeProps<CanvasFlowEdge>) {
  const edges = useCanvasUIStore((s) => s.edges);
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    targetX: props.targetX,
    targetY: props.targetY,
    sourcePosition: props.sourcePosition,
    targetPosition: props.targetPosition,
  });

  // Label mengikuti struktur graph (relasi FLOW saja):
  // - 1 parent → 1 child                : "flow"
  // - 1 parent → banyak child (fork)    : "flow paralel"
  // - banyak node paralel bersatu (join): "join"
  const outCount = useMemo(
    () =>
      edges.filter((e) => e.data?.relation === "FLOW" && e.source === props.source).length,
    [edges, props.source]
  );
  const inCount = useMemo(
    () =>
      edges.filter((e) => e.data?.relation === "FLOW" && e.target === props.target).length,
    [edges, props.target]
  );

  const label = inCount > 1 ? "join" : outCount > 1 ? "flow paralel" : "flow";

  return (
    <>
      <BaseEdge
        id={props.id}
        path={edgePath}
        className={styles.flowEdge}
        style={{ strokeWidth: 2 }}
        markerEnd={props.markerEnd}
      />
      <EdgeLabelRenderer>
        <div
          className={styles.flowLabel}
          style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
        >
          {label}
        </div>
      </EdgeLabelRenderer>
    </>
  );
});

export const AssignedEdge = memo(function AssignedEdge(props: EdgeProps<CanvasFlowEdge>) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    targetX: props.targetX,
    targetY: props.targetY,
    sourcePosition: props.sourcePosition,
    targetPosition: props.targetPosition,
  });

  return (
    <>
      <BaseEdge
        id={props.id}
        path={edgePath}
        className={styles.assignedEdge}
        style={{ strokeWidth: 2 }}
        markerEnd={props.markerEnd}
      />
      <EdgeLabelRenderer>
        <div
          className={styles.assignedLabel}
          style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
        >
          ASSIGNED_TO
        </div>
      </EdgeLabelRenderer>
    </>
  );
});