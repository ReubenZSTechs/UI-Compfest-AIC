// frontend/src/features/canvas/components/SidebarDetail.tsx
// Property box melayang di sisi kanan: melihat/mengedit detail node terpilih.
// Menggunakan komponen lama (REUSE UI): WorkerCard & JobDeskTable.
import { useCanvasUIStore } from "@/store/canvasUI";
import { WorkerCard } from "@/features/digital-twin/components/WorkerCard";
import { resolveProcessSpecs } from "../utils/processSpecs";
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
  const shifts = useCanvasUIStore((s) => s.shifts);
  const d = node.data;
  if (d.kind !== "process") return null;

  const index = useCanvasUIStore
    .getState()
    .nodes.filter((n) => n.data.kind === "process")
    .findIndex((n) => n.id === node.id);

  const { stage, asset, job } = resolveProcessSpecs(node, Math.max(0, index));

  function patchStage(patch: Partial<typeof stage>) {
    updateNodeData(node.id, { stage: { ...stage, ...patch } });
  }

  function patchAsset(patch: Partial<typeof asset>) {
    updateNodeData(node.id, { asset: { ...asset, ...patch } });
  }

  function patchJob(patch: Partial<typeof job>) {
    updateNodeData(node.id, { job: { ...job, ...patch } });
  }

  function applySkills(text: string) {
    const skills = text
      .split(",")
      .map((item) => item.trim())
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
          onChange={(event) => updateNodeData(node.id, { label: event.target.value })}
        />
      </label>

      <label className={styles.field}>
        <span className={styles.fieldLabel}>
          Skill yang Dibutuhkan <em>(pisahkan dengan koma)</em>
        </span>
        <input
          type="text"
          className={styles.input}
          value={d.requiredSkills.join(", ")}
          onFocus={snapshot}
          placeholder="Contoh: Sewing, Cutting"
          onChange={(event) => applySkills(event.target.value)}
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
          onChange={(event) =>
            updateNodeData(node.id, { targetOutput: Number(event.target.value) || 0 })
          }
        />
      </label>

      <fieldset className={styles.group}>
        <legend className={styles.groupLegend}>Process Stage</legend>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Lane</span>
          <input
            type="text"
            className={styles.input}
            value={stage.lane}
            onFocus={snapshot}
            onChange={(event) => patchStage({ lane: event.target.value })}
          />
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Cycle Time (detik)</span>
          <input
            type="number"
            min={1}
            className={styles.input}
            value={stage.cycleTimeSeconds}
            onFocus={snapshot}
            onChange={(event) =>
              patchStage({ cycleTimeSeconds: Number(event.target.value) || 1 })
            }
          />
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Flow Type</span>
          <select
            className={styles.input}
            value={stage.flowType}
            onChange={(event) =>
              patchStage({ flowType: event.target.value as typeof stage.flowType })
            }
          >
            <option value="batch">Batch</option>
            <option value="continuous">Continuous</option>
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Material Input (koma)</span>
          <input
            type="text"
            className={styles.input}
            value={stage.materialInput.join(", ")}
            onFocus={snapshot}
            onChange={(event) =>
              patchStage({
                materialInput: event.target.value
                  .split(",")
                  .map((item) => item.trim())
                  .filter(Boolean),
              })
            }
          />
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Material Output (koma)</span>
          <input
            type="text"
            className={styles.input}
            value={stage.materialOutput.join(", ")}
            onFocus={snapshot}
            onChange={(event) =>
              patchStage({
                materialOutput: event.target.value
                  .split(",")
                  .map((item) => item.trim())
                  .filter(Boolean),
              })
            }
          />
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>QC Requirement</span>
          <input
            type="text"
            className={styles.input}
            value={stage.qcRequirement}
            onFocus={snapshot}
            onChange={(event) => patchStage({ qcRequirement: event.target.value })}
          />
        </label>
      </fieldset>

      <fieldset className={styles.group}>
        <legend className={styles.groupLegend}>Asset</legend>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Nama Asset</span>
          <input
            type="text"
            className={styles.input}
            value={asset.assetName}
            onFocus={snapshot}
            onChange={(event) => patchAsset({ assetName: event.target.value })}
          />
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Kategori</span>
          <select
            className={styles.input}
            value={asset.category}
            onChange={(event) =>
              patchAsset({ category: event.target.value as typeof asset.category })
            }
          >
            <option value="manual_station">Manual Station</option>
            <option value="machine">Machine</option>
            <option value="measuring_equipment">Measuring Equipment</option>
            <option value="conveyor_automation">Conveyor / Automation</option>
            <option value="environmental_chamber">Environmental Chamber</option>
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Unit Tersedia</span>
          <input
            type="number"
            min={0}
            className={styles.input}
            value={asset.unitsAvailable}
            onFocus={snapshot}
            onChange={(event) =>
              patchAsset({ unitsAvailable: Number(event.target.value) || 0 })
            }
          />
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Level Otomasi</span>
          <select
            className={styles.input}
            value={asset.automationLevel}
            onChange={(event) => {
              const level = event.target.value as typeof asset.automationLevel;
              patchAsset({ automationLevel: level, isAutomated: level === "automated" });
            }}
          >
            <option value="manual">Manual</option>
            <option value="semi_automated">Semi Automated</option>
            <option value="automated">Automated</option>
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Biaya Operasional / Jam</span>
          <input
            type="number"
            min={0}
            className={styles.input}
            value={asset.operationalCostPerHour}
            onFocus={snapshot}
            onChange={(event) =>
              patchAsset({ operationalCostPerHour: Number(event.target.value) || 0 })
            }
          />
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Tingkat Kebisingan (dB)</span>
          <input
            type="number"
            min={0}
            className={styles.input}
            value={asset.environmentalFactors.noiseLevelDb ?? ""}
            onFocus={snapshot}
            onChange={(event) =>
              patchAsset({
                environmentalFactors: {
                  ...asset.environmentalFactors,
                  noiseLevelDb: event.target.value === "" ? null : Number(event.target.value),
                },
              })
            }
          />
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Physical Strain Index (0-1)</span>
          <input
            type="number"
            min={0}
            max={1}
            step={0.05}
            className={styles.input}
            value={asset.environmentalFactors.physicalStrainIndex}
            onFocus={snapshot}
            onChange={(event) =>
              patchAsset({
                environmentalFactors: {
                  ...asset.environmentalFactors,
                  physicalStrainIndex: Number(event.target.value) || 0,
                },
              })
            }
          />
        </label>
      </fieldset>

      <fieldset className={styles.group}>
        <legend className={styles.groupLegend}>Job Desk</legend>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Judul Pekerjaan</span>
          <input
            type="text"
            className={styles.input}
            value={job.jobTitle}
            onFocus={snapshot}
            onChange={(event) => patchJob({ jobTitle: event.target.value })}
          />
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Shift</span>
          <select
            className={styles.input}
            value={job.shiftId}
            onChange={(event) => patchJob({ shiftId: event.target.value })}
          >
            {shifts.map((shift) => (
              <option key={shift.shiftId} value={shift.shiftId}>
                {shift.shiftId} ({shift.startTime}-{shift.endTime})
              </option>
            ))}
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Headcount</span>
          <input
            type="number"
            min={1}
            className={styles.input}
            value={job.headcount}
            onFocus={snapshot}
            onChange={(event) => patchJob({ headcount: Number(event.target.value) || 1 })}
          />
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Beban Fisik</span>
          <select
            className={styles.input}
            value={job.demands.physicalDemandLevel}
            onChange={(event) =>
              patchJob({
                demands: {
                  ...job.demands,
                  physicalDemandLevel: event.target.value as "low" | "medium" | "high",
                },
              })
            }
          >
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Kompleksitas Tugas (0-1)</span>
          <input
            type="number"
            min={0}
            max={1}
            step={0.05}
            className={styles.input}
            value={job.demands.taskComplexity}
            onFocus={snapshot}
            onChange={(event) =>
              patchJob({
                demands: { ...job.demands, taskComplexity: Number(event.target.value) || 0 },
              })
            }
          />
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Fokus Kognitif (0-1)</span>
          <input
            type="number"
            min={0}
            max={1}
            step={0.05}
            className={styles.input}
            value={job.demands.requiredCognitiveFocus}
            onFocus={snapshot}
            onChange={(event) =>
              patchJob({
                demands: {
                  ...job.demands,
                  requiredCognitiveFocus: Number(event.target.value) || 0,
                },
              })
            }
          />
        </label>

        <label className={styles.field}>
          <span className={styles.fieldLabel}>Severity Kesalahan</span>
          <select
            className={styles.input}
            value={job.demands.errorSeverity}
            onChange={(event) =>
              patchJob({
                demands: {
                  ...job.demands,
                  errorSeverity: event.target.value as typeof job.demands.errorSeverity,
                },
              })
            }
          >
            <option value="low">Low</option>
            <option value="moderate">Moderate</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
        </label>
      </fieldset>
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