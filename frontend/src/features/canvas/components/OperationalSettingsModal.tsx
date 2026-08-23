// frontend/src/features/canvas/components/OperationalSettingsModal.tsx
// Pop-up "Operational Limitations" yang dibuka dari ikon Settings (⚙️) di
// toolbar kiri. Berisi 3 toggle kebijakan (Allow Recruit New Employees, Allow
// Overtime, Allow Outsourcing) + kolom input Budget Limit. Draft dikelola lokal
// lalu disimpan terpusat ke store canvasUI saat "Save settings" — sehingga
// termasuk payload analisis AI berikutnya — dan popup ditutup otomatis.
// Ditutup juga via tombol (X) atau klik di luar area backdrop, dengan transisi
// masuk/keluar yang mulus.
import { useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useCanvasUIStore } from "@/store/canvasUI";
import { useToastStore } from "@/store/toast";
import type { OperationalLimits } from "@/features/canvas/types/canvas.types";
import styles from "./OperationalSettingsModal.module.css";

const EXIT_MS = 180;

type PolicyKey = "allowRecruitNewEmployees" | "allowOvertime" | "allowOutsourcing";

interface PolicyRow {
  key: PolicyKey;
  id: string;
  label: string;
  hint: string;
}

const POLICY_ROWS: PolicyRow[] = [
  {
    key: "allowRecruitNewEmployees",
    id: "op-policy-recruit",
    label: "Allow Recruit New Employees",
    hint: "Mengizinkan flow AI merekrut pekerja baru bila kebutuhan melebihi staf yang ada.",
  },
  {
    key: "allowOvertime",
    id: "op-policy-overtime",
    label: "Allow Overtime",
    hint: "Mengizinkan jam lembur di luar jam kerja normal untuk mengejar target output.",
  },
  {
    key: "allowOutsourcing",
    id: "op-policy-outsourcing",
    label: "Allow Outsourcing",
    hint: "Mengizinkan penyerahan sebagian pekerjaan ke pihak eksternal bila kapasitas internal menipis.",
  },
];

export function OperationalSettingsModal() {
  const open = useCanvasUIStore((s) => s.settingsOpen);
  const limits = useCanvasUIStore((s) => s.operationalLimits);
  const apply = useCanvasUIStore((s) => s.applyOperationalLimits);
  const close = useCanvasUIStore((s) => s.closeSettings);
  const showToast = useToastStore((s) => s.showToast);

  // Draft state — perubahan lokal tidak memengaruhi store sampai Save.
  const [draft, setDraft] = useState<OperationalLimits>({ ...limits });
  const [budgetText, setBudgetText] = useState(
    limits.budgetLimit > 0 ? String(limits.budgetLimit) : ""
  );
  const [closing, setClosing] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const numeric = Number(budgetText);
  const invalidBudget = budgetText.trim() !== "" && (Number.isNaN(numeric) || numeric < 0);

  function setPolicy(key: PolicyKey, value: boolean) {
    setDraft((d) => ({ ...d, [key]: value }));
  }

  function resetDraft() {
    setDraft({ ...limits });
    setBudgetText(limits.budgetLimit > 0 ? String(limits.budgetLimit) : "");
  }

  // Tutup dengan animasi keluar, lalu baru benar-benar di-unmount.
  function beginClose() {
    if (closing) return;
    setClosing(true);
    window.setTimeout(() => {
      close();
      setClosing(false);
    }, EXIT_MS);
  }

  function handleSave() {
    if (invalidBudget) {
      inputRef.current?.focus();
      return;
    }
    const next: OperationalLimits = {
      ...draft,
      budgetLimit: budgetText.trim() === "" ? 0 : numeric,
    };
    apply(next); // simpan terpusat ke alur canvas/AI + tutup otomatis
    showToast("Kebijakan operasional diterapkan ke alur optimasi", "info");
    resetDraft();
    beginClose();
  }

  function handleCancel() {
    resetDraft();
    beginClose();
  }

  if (!open) return null;

  return createPortal(
    <div
      className={`${styles.backdrop} ${closing ? styles.backdropClosing : ""}`}
      role="presentation"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) handleCancel();
      }}
    >
      <div
        className={`${styles.dialog} ${closing ? styles.dialogClosing : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="op-settings-title"
      >
        <button
          type="button"
          className={styles.closeButton}
          aria-label="Tutup"
          onClick={handleCancel}
          title="Tutup"
        >
          ✕
        </button>

        <h3 id="op-settings-title" className={styles.title}>OPERATIONAL LIMITATIONS</h3>
        <p className={styles.subtitle}>
          Set policies and limits before optimization is implemented
        </p>

        <section className={styles.policySection} aria-label="Kebijakan operasional">
          {POLICY_ROWS.map((row) => (
            <div className={styles.field} key={row.key}>
              <div className={styles.fieldHead}>
                <label htmlFor={row.id} className={styles.fieldLabel}>
                  {row.label}
                </label>
                <Toggle
                  id={row.id}
                  checked={draft[row.key]}
                  onChange={(next) => setPolicy(row.key, next)}
                  label={row.label}
                />
              </div>
              <p className={styles.hint}>{row.hint}</p>
            </div>
          ))}
        </section>

        <div className={styles.field}>
          <div className={styles.budgetColumn}>
            <label htmlFor="op-budget" className={styles.fieldLabel}>
              Budget Limit
            </label>
            <div className={styles.budgetRow}>
              <span className={styles.currency}>IDR</span>
              <input
                ref={inputRef}
                id="op-budget"
                type="number"
                min={0}
                step={1000}
                placeholder="cth: 50000000"
                className={`${styles.budgetInput} ${invalidBudget ? styles.invalid : ""}`}
                value={budgetText}
                onChange={(e) => setBudgetText(e.target.value)}
                aria-label="Budget limit"
              />
            </div>
          </div>
          <p className={styles.hint}>Batas atas biaya (currency unit) yang boleh dikeluarkan selama optimasi. Kosongkan untuk tanpa batas.</p>
        </div>

        <div className={styles.actions}>
          <button type="button" className={styles.cancelButton} onClick={handleCancel}>
            Cancel
          </button>
          <button type="button" className={styles.saveButton} onClick={handleSave} disabled={invalidBudget}>
            Save settings
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}

interface ToggleProps {
  id: string;
  checked: boolean;
  label: string;
  onChange: (next: boolean) => void;
}

function Toggle({ id, checked, label, onChange }: ToggleProps) {
  return (
    <label className={`${styles.toggle} ${checked ? styles.toggleChecked : ""}`} htmlFor={id}>
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        aria-label={label}
      />
      <span className={styles.toggleThumb} />
    </label>
  );
}

export default OperationalSettingsModal;
