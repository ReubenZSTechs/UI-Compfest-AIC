// frontend/src/components/feedback/LeaveConfirmModal.tsx
// Konfirmasi saat user menekan tombol kembali / keluar dari workspace (Live/Agent):
// pilih menyimpan projek ke Dashboard, keluar tanpa menyimpan, atau batal.
import { createPortal } from "react-dom";
import styles from "./LeaveConfirmModal.module.css";

interface LeaveConfirmModalProps {
  open: boolean;
  onSave: () => void;
  onDiscard: () => void;
  onCancel: () => void;
}

export function LeaveConfirmModal({ open, onSave, onDiscard, onCancel }: LeaveConfirmModalProps) {
  if (!open) return null;

  return createPortal(
    <div
      className={styles.overlay}
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <div className={styles.dialog} role="alertdialog" aria-modal="true" aria-labelledby="leave-modal-title">
        <h3 id="leave-modal-title" className={styles.title}>Keluar dari Workspace?</h3>
        <p className={styles.body}>
          Kamu memiliki perubahan yang belum disimpan. Simpan projek ke Dashboard dulu,
          atau tinggalkan tanpa menyimpan.
        </p>

        <div className={styles.actions}>
          <button type="button" className={styles.cancelButton} onClick={onCancel} autoFocus>
            Batal
          </button>
          <button type="button" className={styles.discardButton} onClick={onDiscard}>
            Jangan Simpan
          </button>
          <button type="button" className={styles.saveButton} onClick={onSave}>
            Simpan & Keluar
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}

export default LeaveConfirmModal;