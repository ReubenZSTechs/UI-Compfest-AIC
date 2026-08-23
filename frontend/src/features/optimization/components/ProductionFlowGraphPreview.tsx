// frontend/src/features/optimization/components/ProductionFlowGraphPreview.tsx
import type { FlowNode, FlowEdge } from "../data/analyticsScenariosData";
import styles from "./ProductionFlowGraphPreview.module.css";

interface Props {
  nodes: FlowNode[];
  edges: FlowEdge[];
}

export function ProductionFlowGraphPreview({ nodes, edges }: Props) {
  return (
    <div className={styles.graphWrapper}>
      <div className={styles.nodesRow}>
        {nodes.map((node, i) => {
          const hasEdge = edges.some((e) => e.from === node.id);

          return (
            <div key={node.id} className={styles.nodeGroup}>
              <div
                className={`${styles.nodeCard} ${styles[`node_${node.status}`]}`}
              >
                <div className={styles.nodeHeader}>
                  <span className={styles.nodeType}>{node.type}</span>
                  <span
                    className={`${styles.statusBadge} ${
                      styles[`badge_${node.status}`]
                    }`}
                  >
                    {node.status.toUpperCase()}
                  </span>
                </div>
                <div className={styles.nodeLabel}>{node.label}</div>
                <div className={styles.workersList}>
                  {node.assignedWorkers.map((w) => {
                    const isAuto = /auto|robot|sensor|vision|system/i.test(w);
                    return (
                      <span key={w} className={styles.workerTag}>
                        {isAuto ? "🤖" : "👤"} {w}
                      </span>
                    );
                  })}
                </div>
              </div>

              {hasEdge && i < nodes.length - 1 && (
                <div className={styles.edgeArrow} aria-hidden="true">
                  <div className={styles.arrowLine} />
                  <span className={styles.arrowHead}>▶</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default ProductionFlowGraphPreview;
