// frontend/src/features/canvas/components/SaveProjectModal.tsx
// Popup singkat sebelum menyimpan: meminta user memasukkan judul projek.
// Judul default mengikuti nilai awal (bisa langsung disetujui atau diedit).
// Dialog dirender dengan key saat terbuka agar state judul selalu segar
// (di-remount tiap kali modal dibuka).
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import styles from "./SaveProjectModal.module.css";

interface SaveProjectModalProps {
  open: boolean;
  initialTitle: string;
  saving: boolean;
  onConfirm: (title: string) => void;
  onCancel: () => void;
}

interface DialogProps {
  initialTitle: string;
  saving: boolean;
  onConfirm: (title: string) => void;
  onCancel: () => void;
}

function SaveProjectDialog({ initialTitle, saving, onConfirm, onCancel }: DialogProps) {
  const [title, setTitle] = useState(initialTitle);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.select();
  }, []);

  return (
    <div
      className={styles.overlay}
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !saving) onCancel();
      }}
    >
      <div className={styles.dialog} role="dialog" aria-modal="true" aria-labelledby="save-modal-title">
        <h3 id="save-modal-title" className={styles.title}>Simpan Projek ke Dashboard</h3>
        <p className={styles.subtitle}>
          Beri nama projek sebelum disimpan. Judul ini akan tampil di Main Dashboard.
        </p>

        <label className={styles.fieldLabel} htmlFor="save-project-title">
          Judul Projek
        </label>
        <input
          ref={inputRef}
          id="save-project-title"
          type="text"
          className={styles.input}
          value={title}
          maxLength={80}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="cth: Alur Produksi Batch A"
          disabled={saving}
        />

        <div className={styles.actions}>
          <button type="button" className={styles.cancelButton} onClick={onCancel} disabled={saving}>
            Batal
          </button>
          <button
            type="button"
            className={styles.confirmButton}
            onClick={() => onConfirm(title.trim() || initialTitle)}
            disabled={saving}
          >
            {saving ? "Menyimpan…" : "Simpan Projek"}
          </button>
        </div>
      </div>
    </div>
  );
}

export function SaveProjectModal({ open, initialTitle, saving, onConfirm, onCancel }: SaveProjectModalProps) {
  if (!open) return null;
  return createPortal(
    <SaveProjectDialog
      key={initialTitle}
      initialTitle={initialTitle}
      saving={saving}
      onConfirm={onConfirm}
      onCancel={onCancel}
    />,
    document.body
  );
}

export default SaveProjectModal;