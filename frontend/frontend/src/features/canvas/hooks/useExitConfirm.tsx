// frontend/src/features/canvas/hooks/useExitConfirm.ts
// Penjaga keluar untuk workspace Live/Agent/Recommendations: karena user sering
// salah tekan tombol kembali, setiap kali keluar (tombol back → Dashboard)
// ditawarkan pilihan "Simpan & Keluar", "Jangan Simpan", atau "Batal".
// Perubahan sebenarnya sudah tersinkron otomatis ke ProjectDraft (draftStore),
// sehingga "Simpan & Keluar" cukup mem-finalisasi + backup ke backend.
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCanvasUIStore } from "@/store/canvasUI";
import { useAgentChatStore } from "@/store/agentChat";
import { useToastStore } from "@/store/toast";
import { useDraftStore } from "@/store/draftStore";
import { LeaveConfirmModal } from "@/components/feedback/LeaveConfirmModal";
import { SaveProjectModal } from "@/features/canvas/components/SaveProjectModal";

export function useExitConfirm() {
  const navigate = useNavigate();
  const nodes = useCanvasUIStore((s) => s.nodes);
  const messages = useAgentChatStore((s) => s.messages);
  const projectTitle = useCanvasUIStore((s) => s.projectTitle);
  const setProjectTitle = useCanvasUIStore((s) => s.setProjectTitle);
  const showToast = useToastStore((s) => s.showToast);

  const [leaveOpen, setLeaveOpen] = useState(false);
  const [saveTitleOpen, setSaveTitleOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  // Tidak perlu konfirmasi bila tidak ada yang bisa disimpan.
  const hasContent = nodes.length > 0 || messages.length > 0;

  // Peringatan saat refresh/menutup tab dengan perubahan yang belum disimpan.
  useEffect(() => {
    if (!hasContent) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [hasContent]);

  function goDashboard() {
    navigate("/dashboard");
  }

  /** Dipasang pada tombol kembali: konfirmasi bila ada perubahan, else langsung. */
  function handleBackClick(e: React.MouseEvent) {
    e.preventDefault();
    if (!hasContent) {
      goDashboard();
      return;
    }
    setLeaveOpen(true);
  }

  function handleDiscard() {
    setLeaveOpen(false);
    goDashboard();
  }

  function handleSaveIntent() {
    setLeaveOpen(false);
    setSaveTitleOpen(true);
  }

  async function handleConfirmSave(title: string) {
    if (saving) return;
    setSaving(true);
    try {
      setProjectTitle(title);
      useDraftStore.getState().setTitle(title);
      useDraftStore.getState().saveActiveDraft();
      showToast(`Draft "${title}" tersimpan di Dashboard`);
      setSaveTitleOpen(false);
      goDashboard();
    } catch {
      setSaving(false);
      showToast("Gagal menyimpan draft. Coba lagi.", "error");
    }
  }

  return {
    hasContent,
    handleBackClick,
    guard: (
      <>
        <LeaveConfirmModal
          open={leaveOpen}
          onSave={handleSaveIntent}
          onDiscard={handleDiscard}
          onCancel={() => setLeaveOpen(false)}
        />
        <SaveProjectModal
          open={saveTitleOpen}
          initialTitle={projectTitle}
          saving={saving}
          onConfirm={(title) => void handleConfirmSave(title)}
          onCancel={() => setSaveTitleOpen(false)}
        />
      </>
    ),
  };
}

export default useExitConfirm;