import { useState } from "react";
import { createPortal } from "react-dom";
import type { CanvasFactoryMeta } from "../types/canvas.types";
import styles from "./FactoryDetailsModal.module.css";

interface FactoryDetailsModalProps {
  open: boolean;
  onConfirm: (meta: CanvasFactoryMeta) => void;
  onCancel: () => void;
}

const MIN_NAME_LENGTH = 3;
const MIN_DESCRIPTION_LENGTH = 20;

function FactoryDetailsDialog({ onConfirm, onCancel }: Omit<FactoryDetailsModalProps, "open">) {
  const [factoryName, setFactoryName] = useState("");
  const [description, setDescription] = useState("");
  const [touched, setTouched] = useState(false);

  const trimmedName = factoryName.trim();
  const trimmedDescription = description.trim();

  const nameError =
    trimmedName.length === 0
      ? "Nama pabrik wajib diisi."
      : trimmedName.length < MIN_NAME_LENGTH
        ? `Nama pabrik minimal ${MIN_NAME_LENGTH} karakter.`
        : null;

  const descriptionError =
    trimmedDescription.length === 0
      ? "Deskripsi pabrik wajib diisi."
      : trimmedDescription.length < MIN_DESCRIPTION_LENGTH
        ? `Deskripsi minimal ${MIN_DESCRIPTION_LENGTH} karakter agar bisa diolah AI.`
        : null;

  const isValid = nameError === null && descriptionError === null;

  function handleSubmit() {
    setTouched(true);
    if (!isValid) return;
    onConfirm({
      factoryName: trimmedName,
      processType: "serial",
      layoutDescription: trimmedDescription,
      declaredWorkerCount: 0,
    });
  }

  return (
    <div
      className={styles.overlay}
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <div
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby="factory-details-title"
      >
        <h3 id="factory-details-title" className={styles.title}>
          Detail Pabrik
        </h3>
        <p className={styles.subtitle}>
          Kanvas baru membutuhkan identitas pabrik. Kedua data ini disimpan ke database dan
          dipakai sepanjang siklus hidup pabrik, termasuk oleh agen AI.
        </p>

        <label className={styles.fieldLabel} htmlFor="factory-name">
          Nama Pabrik
        </label>
        <input
          id="factory-name"
          type="text"
          className={styles.input}
          value={factoryName}
          maxLength={255}
          autoFocus
          onChange={(event) => setFactoryName(event.target.value)}
          onBlur={() => setTouched(true)}
          placeholder="cth: PT Garmen Nusantara, Bandung"
        />
        {touched && nameError && <span className={styles.error}>{nameError}</span>}

        <label className={styles.fieldLabel} htmlFor="factory-description">
          Deskripsi Pabrik
        </label>
        <textarea
          id="factory-description"
          className={styles.textarea}
          value={description}
          rows={5}
          maxLength={2000}
          onChange={(event) => setDescription(event.target.value)}
          onBlur={() => setTouched(true)}
          placeholder="Jelaskan tata letak lantai produksi, mesin utama, dan alur perpindahan barang."
        />
        {touched && descriptionError && <span className={styles.error}>{descriptionError}</span>}

        <div className={styles.actions}>
          <button type="button" className={styles.cancelButton} onClick={onCancel}>
            Batal
          </button>
          <button
            type="button"
            className={styles.confirmButton}
            onClick={handleSubmit}
            disabled={touched && !isValid}
          >
            Buat Kanvas →
          </button>
        </div>
      </div>
    </div>
  );
}

export function FactoryDetailsModal({ open, onConfirm, onCancel }: FactoryDetailsModalProps) {
  if (!open) return null;
  return createPortal(
    <FactoryDetailsDialog onConfirm={onConfirm} onCancel={onCancel} />,
    document.body
  );
}

export default FactoryDetailsModal;