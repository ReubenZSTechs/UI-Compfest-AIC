// frontend/src/features/canvas/hooks/useCanvasSessionInit.ts
// Inisialisasi sesi DRAFT terpadu (unified ProjectDraft).
//
// Dipanggil oleh halaman Live / Agent / Recommendations saat mount.
// Menjamin SATU projectId mengisi seluruh halaman:
//   - Tab switch sesi yang sama        => hanya menandai currentStep.
//   - ?projectId=... draft tersimpan   => loadDraft (hydrate canvas + chat + cards).
//   - Tanpa ?projectId & tanpa aktif   => muat draft terakhir, atau 
//     buat draft template kosong.
import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useDraftStore } from "@/store/draftStore";
import type { ProjectStep } from "@/features/project/types/project.types";

export function useCanvasSessionInit(step: ProjectStep = "canvas") {
  const [searchParams] = useSearchParams();

  useEffect(() => {
    const draftStore = useDraftStore.getState();
    const urlProjectId = searchParams.get("projectId");

    // 1) URL membawa projectId eksplisit → muat draft itu.
    if (urlProjectId) {
      const target = draftStore.findDraft(urlProjectId);
      if (target) {
        if (draftStore.getActiveDraft()?.projectId !== urlProjectId) {
          draftStore.loadDraft(urlProjectId);
        }
        draftStore.setCurrentStep(step);
        return;
      }
    }

    // 2) Draft yang sama masih aktif (tab switch Live ↔ Agent) → lanjut.
    const active = draftStore.getActiveDraft();
    if (active) {
      draftStore.setCurrentStep(step);
      return;
    }

    // 3) Draft terbaru di registry → buka.
    const drafts = draftStore.drafts;
    if (drafts.length > 0) {
      draftStore.loadDraft(drafts[0].projectId);
      draftStore.setCurrentStep(step);
      return;
    }

    // 4) Fallback ke template kosong bila tidak ada riwayat sama sekali.
    // (Fungsi migrasi legacy dihapus menyesuaikan canvasApi.ts terbaru)
    draftStore.createDraft("blank");
    draftStore.setCurrentStep(step);

  }, [searchParams, step]);
}

export default useCanvasSessionInit;