import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ROUTES } from "@/app/router/routes";
import { useCanvasUIStore } from "@/store/canvasUI";
import { useToastStore } from "@/store/toast";
import { useDraftStore } from "@/store/draftStore";
import { runFactoryBuild } from "../utils/runFactoryBuild";
import { SaveProjectModal } from "./SaveProjectModal";
import { WorkerZipButton } from "./WorkerZipButton";
import styles from "./CanvasAnalyzePanel.module.css";

export function CanvasAnalyzePanel() {
  const navigate = useNavigate();
  const nodes = useCanvasUIStore((s) => s.nodes);
  const analysis = useCanvasUIStore((s) => s.analysis);
  const projectTitle = useCanvasUIStore((s) => s.projectTitle);
  const workerPool = useCanvasUIStore((s) => s.workerPool);
  const setProjectTitle = useCanvasUIStore((s) => s.setProjectTitle);
  const showToast = useToastStore((s) => s.showToast);

  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved">("idle");
  const [showSaveModal, setShowSaveModal] = useState(false);

  const isRunning = analysis.status === "running";
  const hasProcessNode = nodes.some((node) => node.data.kind === "process");
  const hasWorkers = workerPool.length > 0;

  async function handleGenerate() {
    if (!hasProcessNode || isRunning) return;

    if (!hasWorkers) {
      showToast("Unggah arsip worker (.zip) sebelum membangun digital twin.", "error");
      return;
    }

    const result = await runFactoryBuild();

    if (result.status === "done" && result.factoryId) {
      const params = new URLSearchParams({ factoryId: result.factoryId });
      if (result.compatibilityJobId) params.set("jobId", result.compatibilityJobId);

      const projectId = useDraftStore.getState().activeDraftId;
      if (projectId) params.set("projectId", projectId);

      useDraftStore.getState().setFactoryId(result.factoryId);
      navigate(`${ROUTES.PARSER}?${params.toString()}`);
      return;
    }

    showToast(result.message, "error");
  }

  function handleSave() {
    if (saveState === "saving") return;
    setShowSaveModal(true);
  }

  async function handleConfirmSave(title: string) {
    if (saveState === "saving") return;
    setSaveState("saving");
    try {
      setProjectTitle(title);
      useDraftStore.getState().setTitle(title);
      await useDraftStore.getState().saveActiveDraft();
      setSaveState("saved");
      setShowSaveModal(false);
      showToast(`Draft "${title}" tersimpan di Dashboard`);
    } catch {
      setSaveState("idle");
      showToast("Gagal menyimpan draft. Coba lagi.", "error");
    }
  }

  return (
    <>
      <div className={styles.panel}>
        <button
          type="button"
          className={styles.saveButton}
          onClick={handleSave}
          disabled={nodes.length === 0 || saveState === "saving"}
        >
          {saveState === "saving" ? "Menyimpan…" : saveState === "saved" ? "Tersimpan ✓" : "Simpan"}
        </button>

        <WorkerZipButton />

        {analysis.status !== "idle" && (
          <span
            className={`${styles.statusPill} ${styles[`status-${analysis.status}`]}`}
            title={analysis.message}
          >
            {analysis.status === "running" && "⏳"}
            {analysis.status === "done" && "✓"}
            {analysis.status === "error" && "✕"}{" "}
            {analysis.status === "running" ? "Memproses..." : analysis.message ?? analysis.status}
          </span>
        )}

        <button
          type="button"
          className={styles.analyzeButton}
          onClick={() => void handleGenerate()}
          disabled={!hasProcessNode || isRunning}
        >
          {isRunning ? "Memproses…" : "Generate Digital Twin"}
        </button>
      </div>

      <SaveProjectModal
        open={showSaveModal}
        initialTitle={projectTitle}
        saving={saveState === "saving"}
        onConfirm={(title) => void handleConfirmSave(title)}
        onCancel={() => {
          if (saveState !== "saving") setShowSaveModal(false);
        }}
      />
    </>
  );
}

export default CanvasAnalyzePanel;