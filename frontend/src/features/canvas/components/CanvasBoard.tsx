// frontend/src/features/canvas/components/CanvasBoard.tsx
// Papan tulis interaktif (React Flow): drag & drop node, tarik garis relasi,
// klik untuk menambah node sesuai activeTool, undo/redo via keyboard.
import { useCallback, useEffect, useState } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  BackgroundVariant,
  ConnectionMode,
  MarkerType,
  useReactFlow,
  type Connection,
  type Edge,
  type EdgeMouseHandler,
  type NodeMouseHandler,
  type OnEdgesDelete,
  type OnNodeDrag,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useCanvasUIStore } from "@/store/canvasUI";
import { resolveRelation } from "@/store/canvasUI";
import { isValidFlowConnection, toFlowGraph } from "../utils/flowLogic";
import { NodeFabric } from "@/components/feedback/NodeFabric";
import { NodeWorker } from "@/components/feedback/NodeWorker";
import { NodeOutput } from "@/components/feedback/NodeOutput";
import { FlowEdge, AssignedEdge } from "./edges";
import { CanvasAnalyzePanel } from "./CanvasAnalyzePanel";
import { ZoomControls } from "./ZoomControls";
import type { CanvasFlowEdge, CanvasFlowNode } from "../types/canvas.types";
import styles from "./CanvasBoard.module.css";

const nodeTypes = { fabric: NodeFabric, worker: NodeWorker, output: NodeOutput };
const edgeTypes = { flow: FlowEdge, assigned: AssignedEdge };

const defaultEdgeOptions = {
  markerEnd: { type: MarkerType.ArrowClosed, width: 18, height: 18 },
};

export function CanvasBoard() {
  return (
    <ReactFlowProvider>
      <BoardCanvas />
    </ReactFlowProvider>
  );
}

function BoardCanvas() {
  const activeTool = useCanvasUIStore((s) => s.activeTool);
  const nodes = useCanvasUIStore((s) => s.nodes);
  const edges = useCanvasUIStore((s) => s.edges);
  const selectedNodeId = useCanvasUIStore((s) => s.selectedNodeId);
  const setSelectedNode = useCanvasUIStore((s) => s.setSelectedNode);

  const [connectSourceId, setConnectSourceId] = useState<string | null>(null);
  const { screenToFlowPosition } = useReactFlow();

  const onNodesChange = useCanvasUIStore((s) => s.onNodesChange);
  const onEdgesChange = useCanvasUIStore((s) => s.onEdgesChange);
  const onConnect = useCanvasUIStore((s) => s.onConnect);
  const addNodeAt = useCanvasUIStore((s) => s.addNodeAt);
  const removeElement = useCanvasUIStore((s) => s.removeElement);
  const snapshot = useCanvasUIStore((s) => s.snapshot);
  const undo = useCanvasUIStore((s) => s.undo);
  const redo = useCanvasUIStore((s) => s.redo);

  const isValidConnection = useCallback(
    (connection: Connection | Edge) => {
      if (!connection.source || !connection.target || connection.source === connection.target) {
        return false;
      }
      const source = nodes.find((n) => n.id === connection.source);
      const target = nodes.find((n) => n.id === connection.target);
      const relation = resolveRelation(source?.data.kind, target?.data.kind);
      if (relation === null) return false;
      // Aturan alur: level sama / flow ke parent sendiri tidak diizinkan.
      if (relation === "FLOW") {
        if (!isValidFlowConnection(connection.source, connection.target, toFlowGraph(nodes, edges))) {
          return false;
        }
      }
      return !edges.some(
        (e) => e.source === connection.source && e.target === connection.target
      );
    },
    [nodes, edges]
  );

  const handlePaneClick = useCallback(
    (event: React.MouseEvent) => {
      if (
        activeTool === "add-process" ||
        activeTool === "add-worker" ||
        activeTool === "add-output"
      ) {
        // Memetakan koordinat layar ke koordinat flow (sudah memperhitungkan zoom & pan).
        const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
        addNodeAt(activeTool === "add-process" ? "process" : activeTool === "add-worker" ? "worker" : "output", position);
        return;
      }

      setSelectedNode(null);
    },
    [activeTool, addNodeAt, setSelectedNode, screenToFlowPosition]
  );

  const handleNodeClick: NodeMouseHandler<CanvasFlowNode> = useCallback(
    (_, node) => {
      if (activeTool === "erase") {
        removeElement(node.id);
        return;
      }
      if (activeTool === "connect") {
        if (!connectSourceId) {
          setConnectSourceId(node.id);
        } else if (connectSourceId !== node.id) {
          onConnect({ source: connectSourceId, target: node.id, sourceHandle: null, targetHandle: null });
          setConnectSourceId(null);
        }
        return;
      }
      setSelectedNode(node.id);
    },
    [activeTool, connectSourceId, onConnect, removeElement, setSelectedNode]
  );

  const handleEdgeClick: EdgeMouseHandler<CanvasFlowEdge> = useCallback(
    (_, edge) => {
      if (activeTool === "erase") {
        removeElement(edge.id, true);
      }
    },
    [activeTool, removeElement]
  );

  const handleEdgesDelete: OnEdgesDelete<CanvasFlowEdge> = useCallback(
    (deleted) => {
      if (deleted.length > 0) snapshot();
    },
    [snapshot]
  );

  const handleNodeDragStart: OnNodeDrag<CanvasFlowNode> = useCallback(() => {
    snapshot();
  }, [snapshot]);

  // Keyboard shortcuts: Undo (Ctrl+Z), Redo (Ctrl+Y), Hapus (Delete), Batal (Esc)
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setSelectedNode(null);
        setConnectSourceId(null);
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
        e.preventDefault();
        if (e.shiftKey) redo();
        else undo();
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") {
        e.preventDefault();
        redo();
      }
      if (e.key === "Delete" || e.key === "Backspace") {
        if (selectedNodeId) {
          e.preventDefault();
          removeElement(selectedNodeId);
        }
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [selectedNodeId, setSelectedNode, redo, undo, removeElement]);

  return (
    <div className={styles.board}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onPaneClick={handlePaneClick}
        onNodeClick={handleNodeClick}
        onEdgeClick={handleEdgeClick}
        onEdgesDelete={handleEdgesDelete}
        onNodeDragStart={handleNodeDragStart}
        isValidConnection={isValidConnection}
        defaultEdgeOptions={defaultEdgeOptions}
        connectionMode={ConnectionMode.Loose}
        deleteKeyCode={null}
        minZoom={0.2}
        maxZoom={2.5}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={22} size={1.4} color="#c6cdd6" />
        <div className={styles.bottomBar}>
          <ZoomControls />
          <CanvasAnalyzePanel />
        </div>
      </ReactFlow>

      {connectSourceId && (
        <div className={styles.connectHint}>
          Klik node tujuan (proses) untuk menghubungkan dari{" "}
          <strong>{connectSourceId}</strong>
        </div>
      )}
    </div>
  );
}