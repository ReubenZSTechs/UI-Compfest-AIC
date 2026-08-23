// frontend/src/hooks/useDraftAutoSync.ts
// Auto-sync global: setiap perubahan working state (nodes/edges canvas,
// judul, operational limits, riwayat chat agent) langsung dimirror ke SATU
// record ProjectDraft aktif dan dipersist (localStorage + backup backend).
// Dipakai oleh halaman Live, Agent, dan Recommendations.
import { useEffect } from "react";
import { useCanvasUIStore } from "@/store/canvasUI";
import { useAgentChatStore } from "@/store/agentChat";
import { useDraftStore } from "@/store/draftStore";

export function useDraftAutoSync() {
  useEffect(() => {
    let dirty = false;
    let scheduled = false;

    const schedule = () => {
      dirty = true;
      if (scheduled) return;
      scheduled = true;
      // Gabungkan burst perubahan dalam satu microtask agar tidak menulis
      // berkali-kali saat drag node / mengetik chat.
      queueMicrotask(() => {
        scheduled = false;
        if (!dirty) return;
        dirty = false;
        useDraftStore.getState().syncActiveDraft();
      });
    };

    const unsubCanvas = useCanvasUIStore.subscribe(schedule);
    const unsubChat = useAgentChatStore.subscribe(schedule);
    return () => {
      unsubCanvas();
      unsubChat();
    };
  }, []);
}

export default useDraftAutoSync;
