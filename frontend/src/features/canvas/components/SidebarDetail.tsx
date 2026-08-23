// frontend/src/features/canvas/components/SidebarDetail.tsx
// Property box melayang di sisi kanan: melihat/mengedit detail node terpilih.
// Menggunakan komponen lama (REUSE UI): WorkerCard & JobDeskTable.
import { useCanvasUIStore } from "@/store/canvasUI";
import { WorkerCard } from "@/features/digital-twin/components/WorkerCard";
import type { CanvasFlowNode } from "../types/canvas.types";
import styles from "./SidebarDetail.module.css";

export function SidebarDetail() {
  const selectedNodeId = useCanvasUIStore((s) => s.selectedNodeId);
  const nodes = useCanvasUIStore((s) => s.nodes);
  const updateNodeData = useCanvasUIStore((s) => s.updateNodeData);
  const removeElement = useCanvasUIStore((s) => s.removeElement);
  const setSelectedNode = useCanvasUIStore((s) => s.setSelectedNode);
  const snapshot = useCanvasUIStore((s) => s.snapshot);

  const node = nodes.find((n) => n.id === selectedNodeId) ?? null;

  // Tanpa node terpilih: tidak ada panel sama sekali (empty state dihapus).
  if (!node) return null;

  const d = node.data;

  return (
    <aside className={styles.propertyBox}>
      <header className={styles.header}>
        <div>
          <span className={styles.eyebrow}>
            {d.kind === "process" ? "NODE PROSES" : d.kind === "output" ? "NODE OUTPUT" : "NODE PEKERJA"}
          </span>
          <h2 className={styles.title}>{d.label}</h2>
        </div>
        <button
          type="button"
          className={styles.closeButton}
          onClick={() => setSelectedNode(null)}
          aria-label="Tutup panel detail"
        >
          ✕
        </button>
      </header>

      <div className={styles.body}>
        {d.kind === "process" ? (
          <ProcessDetail
            node={node}
            updateNodeData={updateNodeData}
            snapshot={snapshot}
          />
        ) : d.kind === "output" ? (
          <OutputDetail node={node} updateNodeData={updateNodeData} snapshot={snapshot} />
        ) : (
          <WorkerDetail node={node} updateNodeData={updateNodeData} snapshot={snapshot} />
        )}
      </div>

      <footer className={styles.footer}>
        <button
          type="button"
          className={styles.deleteButton}
          onClick={() => removeElement(node.id)}
        >
          Hapus Node
        </button>
      </footer>
    </aside>
  );
}

interface DetailProps {
  node: CanvasFlowNode;
  updateNodeData: (
    id: string,
    patch: Partial<CanvasFlowNode["data"]> & Record<string, unknown>
  ) => void;
  snapshot: () => void;
}

function ProcessDetail({ node, updateNodeData, snapshot }: DetailProps) {
  const d = node.data;
  const isProcess = d.kind === "process";
  if (!isProcess) return null;

  const skillsText = d.requiredSkills.join(", ");

  function applySkills(text: string) {
    const skills = text
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    updateNodeData(node.id, { requiredSkills: skills });
  }

  return (
    <div className={styles.form}>
      <label className={styles.field}>
        <span className={styles.fieldLabel}>Nama Proses</span>
        <input
          type="text"
          className={styles.input}
          value={d.label}
          onFocus={snapshot}
          onChange={(e) => updateNodeData(node.id, { label: e.target.value })}
        />
      </label>

      <label className={styles.field}>
        <span className={styles.fieldLabel}>
          Skill yang Dibutuhkan <em>(pisahkan dengan koma)</em>
        </span>
        <input
          type="text"
          className={styles.input}
          value={skillsText}
          onFocus={snapshot}
          placeholder="Contoh: Sewing, Cutting"
          onChange={(e) => applySkills(e.target.value)}
        />
      </label>

      <label className={styles.field}>
        <span className={styles.fieldLabel}>Target Output (unit/jam)</span>
        <input
          type="number"
          min={0}
          className={styles.input}
          value={d.targetOutput || ""}
          onFocus={snapshot}
          onChange={(e) =>
            updateNodeData(node.id, { targetOutput: Number(e.target.value) || 0 })
          }
        />
      </label>
    </div>
  );
}

function WorkerDetail({ node, updateNodeData, snapshot }: DetailProps) {
  const data = node.data;
  if (data.kind !== "worker") return null;
  // Narrow type ke WorkerDetailData agar closures di bawah tetap type-safe.
  const d: Extract<CanvasFlowNode["data"], { kind: "worker" }> = data;

  const skillsText = (d.worker.skills ?? []).join(", ");

  function applySkills(text: string) {
    const skills = text
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    updateNodeData(node.id, { skills, worker: { ...d.worker, skills } });
  }

  function applyName(name: string) {
    updateNodeData(node.id, { label: name, worker: { ...d.worker, name } });
  }

  return (
    <div className={styles.form}>
      <div className={styles.previewBlock}>
        <span className={styles.fieldLabel}>Preview (WorkerCard)</span>
        <WorkerCard worker={d.worker} />
      </div>

      <label className={styles.field}>
        <span className={styles.fieldLabel}>Nama Pekerja</span>
        <input
          type="text"
          className={styles.input}
          value={d.label}
          onFocus={snapshot}
          onChange={(e) => applyName(e.target.value)}
        />
      </label>

      <label className={styles.field}>
        <span className={styles.fieldLabel}>
          Skill Pekerja <em>(pisahkan dengan koma)</em>
        </span>
        <input
          type="text"
          className={styles.input}
          value={skillsText}
          onFocus={snapshot}
          placeholder="Contoh: Sewing, Cutting"
          onChange={(e) => applySkills(e.target.value)}
        />
      </label>

      <div className={styles.field}>
        <span className={styles.fieldLabel}>Fatigue Score</span>
        <div className={styles.sliderRow}>
          <input
            type="range"
            min={0}
            max={100}
            value={d.fatigueScore}
            onPointerDown={snapshot}
            onChange={(e) => updateNodeData(node.id, { fatigueScore: Number(e.target.value) })}
            className={styles.slider}
          />
          <span className={styles.sliderValue}>{d.fatigueScore}</span>
        </div>
      </div>
    </div>
  );
}

function OutputDetail({ node, updateNodeData, snapshot }: DetailProps) {
  const data = node.data;
  if (data.kind !== "output") return null;
  const d: Extract<CanvasFlowNode["data"], { kind: "output" }> = data;

  const achievement =
    d.targetOutput > 0 ? Math.round((d.totalOutput / d.targetOutput) * 100) : 0;

  return (
    <div className={styles.form}>
      <label className={styles.field}>
        <span className={styles.fieldLabel}>Nama Output</span>
        <input
          type="text"
          className={styles.input}
          value={d.label}
          onFocus={snapshot}
          placeholder="Contoh: Finished Goods Storage"
          onChange={(e) => updateNodeData(node.id, { label: e.target.value })}
        />
      </label>

      <label className={styles.field}>
        <span className={styles.fieldLabel}>Target Output (unit/jam)</span>
        <input
          type="number"
          min={0}
          className={styles.input}
          value={d.targetOutput || ""}
          onFocus={snapshot}
          onChange={(e) =>
            updateNodeData(node.id, { targetOutput: Number(e.target.value) || 0 })
          }
        />
      </label>

      <label className={styles.field}>
        <span className={styles.fieldLabel}>Total Output (unit)</span>
        <input
          type="number"
          min={0}
          className={styles.input}
          value={d.totalOutput || ""}
          onFocus={snapshot}
          onChange={(e) =>
            updateNodeData(node.id, { totalOutput: Number(e.target.value) || 0 })
          }
        />
      </label>

      <div className={styles.previewBlock}>
        <span className={styles.fieldLabel}>Pencapaian</span>
        <p className={styles.hint}>
          {d.targetOutput > 0
            ? `${achievement}% dari target (simulation_summary.project.md).`
            : "Isi Target Output untuk menghitung pencapaian."}
        </p>
      </div>
    </div>
  );
}