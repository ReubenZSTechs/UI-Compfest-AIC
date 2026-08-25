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
import { useNavigate, useSearchParams } from "react-router-dom";
import { ROUTES } from "@/app/router/routes";
import { useDraftStore } from "@/store/draftStore";
import type { ProjectStep } from "@/features/project/types/project.types";

export function useCanvasSessionInit(step: ProjectStep = "canvas") {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    const draftStore = useDraftStore.getState();
    const urlProjectId = searchParams.get("projectId");

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

    const active = draftStore.getActiveDraft();
    if (active) {
      draftStore.setCurrentStep(step);
      return;
    }

    const drafts = draftStore.drafts;
    if (drafts.length > 0) {
      draftStore.loadDraft(drafts[0].projectId);
      draftStore.setCurrentStep(step);
      return;
    }

    navigate(ROUTES.INTRO, { replace: true });
  }, [searchParams, step, navigate]);
}

export default useCanvasSessionInit;