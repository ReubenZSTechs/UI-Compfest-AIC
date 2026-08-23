// frontend/src/components/feedback/ToastHost.tsx
// Merender toast notification global (pojok kanan-atas) dari useToastStore.
import { useToastStore } from "@/store/toast";
import styles from "./ToastHost.module.css";

const ICONS: Record<string, string> = {
  success: "✓",
  info: "ℹ",
  error: "✕",
};

export function ToastHost() {
  const toasts = useToastStore((s) => s.toasts);
  const dismissToast = useToastStore((s) => s.dismissToast);

  return (
    <div className={styles.host} aria-live="polite" aria-atomic="false">
      {toasts.map((t) => (
        <button
          key={t.id}
          type="button"
          className={`${styles.toast} ${styles[`toast-${t.kind}`]}`}
          onClick={() => dismissToast(t.id)}
          title="Tutup notifikasi"
        >
          <span className={styles.icon}>{ICONS[t.kind] ?? "•"}</span>
          <span className={styles.message}>{t.message}</span>
        </button>
      ))}
    </div>
  );
}

export default ToastHost;