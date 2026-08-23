// frontend/src/features/canvas/hooks/useCanvasSessionInit.ts
// Inisialisasi sesi DRAFT terpadu (unified ProjectDraft).
//
// Dipanggil oleh halaman Live / Agent / Recommendations saat mount.
// Menjamin SATU projectId mengisi seluruh halaman:
//   - Tab switch sesi yang sama        => hanya menandai currentStep.
//   - ?projectId=... draft tersimpan   => loadDraft (hydrate canvas + chat + cards).
//   - Tanpa ?projectId & tanpa aktif   => muat draft terakhir, migrasi legacy,
//     atau buat draft template kosong.
import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useDraftStore } from "@/store/draftStore";
import {
  legacyCanvasProjectToDraft,
  loadLegacyCanvasProject,
} from "../api/canvasApi";
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

    // 4) Migrasi proyek legacy (backend latest / localStorage v1), lalu
    //    fallback ke template kosong bila tidak ada.
    let cancelled = false;
    void (async () => {
      const legacy = await loadLegacyCanvasProject();
      if (cancelled) return;
      const draft = legacy ? legacyCanvasProjectToDraft(legacy) : null;
      if (draft) {
        useDraftStore.getState().applyLegacyDraft(draft);
        useDraftStore.getState().loadDraft(draft.projectId);
        useDraftStore.getState().setCurrentStep(step);
        return;
      }
      useDraftStore.getState().createDraft("blank");
      useDraftStore.getState().setCurrentStep(step);
    })();

    return () => {
      cancelled = true;
    };
  }, [searchParams, step]);
}

export default useCanvasSessionInit;
