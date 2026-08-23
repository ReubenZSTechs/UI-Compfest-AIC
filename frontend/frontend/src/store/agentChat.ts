// frontend/src/store/agentChat.ts
// State percakapan Agent Chat ditingkatkan ke store global (Zustand) agar
// riwayat chat TIDAK hilang saat komponen AgentChat di-unmount ketika user
// berpindah antar halaman Live ↔ Agent.
// Chat juga terikat ke sesi (canvasId) yang sama dengan halaman Live, sehingga
// saat canvas disimpan/dimuat ulang, riwayat percakapan ikut tersimpan.
import { create } from "zustand";

export interface AgentChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
}

let msgCounter = 0;
const nextId = () => `msg-${Date.now().toString(36)}-${++msgCounter}`;

interface AgentChatState {
  messages: AgentChatMessage[];
  busy: boolean;
  canvasId: string | null;
  pushMessage: (role: AgentChatMessage["role"], text: string) => void;
  setBusy: (busy: boolean) => void;
  /** Mengisi ulang riwayat percakapan dari sesi yang dimuat (save/load). */
  hydrate: (canvasId: string | null, messages: AgentChatMessage[]) => void;
  /** Sesi baru (template baru) => mulai chat kosong untuk canvasId tersebut. */
  startNewSession: (canvasId: string) => void;
  resetChat: () => void;
}

export const useAgentChatStore = create<AgentChatState>((set) => ({
  messages: [],
  busy: false,
  canvasId: null,
  pushMessage: (role, text) =>
    set((s) => ({ messages: [...s.messages, { id: nextId(), role, text }] })),
  setBusy: (busy) => set({ busy }),
  hydrate: (canvasId, messages) => set({ canvasId, messages, busy: false }),
  startNewSession: (canvasId) => set({ canvasId, messages: [], busy: false }),
  resetChat: () => set({ messages: [], busy: false }),
}));