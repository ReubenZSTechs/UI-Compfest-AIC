// frontend/src/features/canvas/components/CanvasAnalyzePanel.tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ROUTES } from "@/app/router/routes";
import { useCanvasUIStore } from "@/store/canvasUI";
import { useToastStore } from "@/store/toast";
import { useDraftStore } from "@/store/draftStore";
import { runCanvasAnalysis } from "../utils/runCanvasAnalysis";
import { SaveProjectModal } from "./SaveProjectModal";
import styles from "./CanvasAnalyzePanel.module.css";

export function CanvasAnalyzePanel() {
  const navigate = useNavigate();
  const nodes = useCanvasUIStore((s) => s.nodes);
  const analysis = useCanvasUIStore((s) => s.analysis);
  const projectTitle = useCanvasUIStore((s) => s.projectTitle);
  const setProjectTitle = useCanvasUIStore((s) => s.setProjectTitle);
  const showToast = useToastStore((s) => s.showToast);

  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved">("idle");
  const [showSaveModal, setShowSaveModal] = useState(false);

  const isRunning = analysis.status === "running";
  const isEmpty = nodes.length === 0;

  async function runAnalysis() {
    if (isEmpty || isRunning) return;
    // Jalankan proses analisis lalu arahkan ke DocumentParserPage (/parser)
    const result = await runCanvasAnalysis();
    const projectId = useDraftStore.getState().activeDraftId;
    
    if (result.status === "done") {
      // --- PEMBARUAN: Tambahkan parameter &mock=success atau ?mock=success ---
      const url = projectId 
        ? `${ROUTES.PARSER}?projectId=${encodeURIComponent(projectId)}&mock=success` 
        : `${ROUTES.PARSER}?mock=success`;
      // ---------------------------------------------------------------------
      
      navigate(url);
    } else {
      showToast(result.message || "Analisis gagal, coba lagi.", "error");
    }
  }

  // Langkah 1: buka modal judul projek sebelum penyimpanan dilanjutkan.
  function handleSave() {
    if (saveState === "saving") return;
    setShowSaveModal(true);
  }

  // Langkah 2: judul di-set, finalisasi draft terpadu (sudah auto-sync).
  async function handleConfirmSave(title: string) {
    if (saveState === "saving") return;
    setSaveState("saving");
    try {
      setProjectTitle(title);
      useDraftStore.getState().setTitle(title);
      useDraftStore.getState().saveActiveDraft();
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
          disabled={isEmpty || saveState === "saving"}
        >
          {saveState === "saving" ? "Menyimpan…" : saveState === "saved" ? "Tersimpan ✓" : "Simpan"}
        </button>

        {analysis.status !== "idle" && (
          <span
            className={`${styles.statusPill} ${styles[`status-${analysis.status}`]}`}
            title={analysis.message}
          >
            {analysis.status === "running" && "⏳"}
            {analysis.status === "done" && "✓"}
            {analysis.status === "error" && "✕"}{" "}
            {analysis.status === "running" ? "Menganalisis..." : analysis.message ?? analysis.status}
          </span>
        )}

        <button
          type="button"
          className={styles.analyzeButton}
          onClick={runAnalysis}
          disabled={isEmpty || isRunning}
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