// frontend/src/store/toast.ts
// Toast notification global (ditampilkan oleh ToastHost di root aplikasi).
import { create } from "zustand";

export interface ToastItem {
  id: string;
  message: string;
  kind: "success" | "info" | "error";
}

interface ToastState {
  toasts: ToastItem[];
  showToast: (message: string, kind?: ToastItem["kind"]) => void;
  dismissToast: (id: string) => void;
}

let toastCounter = 0;
const nextId = () => `toast-${Date.now().toString(36)}-${++toastCounter}`;

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  showToast: (message, kind = "success") => {
    const id = nextId();
    set((s) => ({ toasts: [...s.toasts, { id, message, kind }] }));
    setTimeout(() => get().dismissToast(id), 3200);
  },
  dismissToast: (id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));