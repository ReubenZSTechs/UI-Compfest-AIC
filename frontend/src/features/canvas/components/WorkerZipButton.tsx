import { useRef } from "react";
import { useCanvasUIStore } from "@/store/canvasUI";
import { useToastStore } from "@/store/toast";
import { createFactory, uploadWorkerArchive } from "../api/canvasApi";
import styles from "./WorkerZipButton.module.css";

const MAX_ZIP_BYTES = 20 * 1024 * 1024;

export function WorkerZipButton() {
  const inputRef = useRef<HTMLInputElement>(null);

  const factoryId = useCanvasUIStore((s) => s.factoryId);
  const factoryMeta = useCanvasUIStore((s) => s.factoryMeta);
  const projectTitle = useCanvasUIStore((s) => s.projectTitle);
  const workerUpload = useCanvasUIStore((s) => s.workerUpload);
  const workerPool = useCanvasUIStore((s) => s.workerPool);
  const setFactoryId = useCanvasUIStore((s) => s.setFactoryId);
  const setWorkerPool = useCanvasUIStore((s) => s.setWorkerPool);
  const setWorkerUpload = useCanvasUIStore((s) => s.setWorkerUpload);
  const autoDistributeWorkers = useCanvasUIStore((s) => s.autoDistributeWorkers);
  const openMapping = useCanvasUIStore((s) => s.openMapping);
  const showToast = useToastStore((s) => s.showToast);

  const isUploading = workerUpload.status === "uploading";

  async function ensureFactoryId(): Promise<string> {
    if (factoryId) return factoryId;

    const summary = await createFactory({
      factoryName: factoryMeta.factoryName || projectTitle,
      processType: factoryMeta.processType,
      declaredWorkerCount: factoryMeta.declaredWorkerCount,
      layoutDescription: factoryMeta.layoutDescription,
    });
    setFactoryId(summary.factoryId);
    return summary.factoryId;
  }

  async function handleFileSelected(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".zip")) {
      showToast("Berkas harus berformat .zip", "error");
      return;
    }
    if (file.size > MAX_ZIP_BYTES) {
      showToast("Ukuran arsip melebihi 20 MB.", "error");
      return;
    }

    setWorkerUpload({
      status: "uploading",
      fileName: file.name,
      message: "Mengekstraksi profil pekerja...",
    });

    try {
      const targetFactoryId = await ensureFactoryId();
      const result = await uploadWorkerArchive(targetFactoryId, file);

      setWorkerPool(result.workers);
      autoDistributeWorkers();
      setWorkerUpload({
        status: "success",
        message: `${result.workersPersisted} pekerja tersimpan dari ${result.candidatesFound} kandidat.`,
        acceptedCount: result.workersPersisted,
        rejectedCount: result.rejectedBlocksCount,
      });

      if (result.warnings.length > 0) {
        showToast(`${result.warnings.length} peringatan saat ekstraksi arsip.`, "error");
      }
      openMapping();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Gagal memproses arsip pekerja.";
      setWorkerUpload({ status: "error", message });
      showToast(message, "error");
    }
  }

  return (
    <div className={styles.wrapper}>
      <input
        ref={inputRef}
        type="file"
        accept=".zip,application/zip,application/x-zip-compressed"
        className={styles.hiddenInput}
        onChange={(event) => void handleFileSelected(event)}
      />

      <button
        type="button"
        className={styles.uploadButton}
        onClick={() => inputRef.current?.click()}
        disabled={isUploading}
      >
        {isUploading ? "Mengunggah…" : "Unggah Worker (.zip)"}
      </button>

      {workerPool.length > 0 && (
        <button type="button" className={styles.mapButton} onClick={openMapping}>
          Petakan Worker ({workerPool.length})
        </button>
      )}

      {workerUpload.message && (
        <span className={`${styles.status} ${styles[`status-${workerUpload.status}`]}`}>
          {workerUpload.message}
        </span>
      )}
    </div>
  );
}

export default WorkerZipButton;