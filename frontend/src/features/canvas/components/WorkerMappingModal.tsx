import { useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useCanvasUIStore } from "@/store/canvasUI";
import type { CanvasProcessData } from "../types/canvas.types";
import styles from "./WorkerMappingModal.module.css";

export function WorkerMappingModal() {
  const mappingOpen = useCanvasUIStore((s) => s.mappingOpen);
  if (!mappingOpen) return null;
  return createPortal(<WorkerMappingDialog />, document.body);
}

function WorkerMappingDialog() {
  const nodes = useCanvasUIStore((s) => s.nodes);
  const workerPool = useCanvasUIStore((s) => s.workerPool);
  const workerAssignments = useCanvasUIStore((s) => s.workerAssignments);
  const assignWorker = useCanvasUIStore((s) => s.assignWorker);
  const unassignWorker = useCanvasUIStore((s) => s.unassignWorker);
  const clearWorkerAssignments = useCanvasUIStore((s) => s.clearWorkerAssignments);
  const autoDistributeWorkers = useCanvasUIStore((s) => s.autoDistributeWorkers);
  const closeMapping = useCanvasUIStore((s) => s.closeMapping);

  const [query, setQuery] = useState("");

  const processNodes = useMemo(
    () => nodes.filter((node) => node.data.kind === "process"),
    [nodes]
  );

  const assignedWorkerIds = useMemo(
    () => new Set(Object.values(workerAssignments).flat()),
    [workerAssignments]
  );

  const unassignedWorkers = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return workerPool
      .filter((worker) => !assignedWorkerIds.has(worker.workerId))
      .filter(
        (worker) =>
          keyword.length === 0 ||
          worker.name.toLowerCase().includes(keyword) ||
          worker.skills.some((skill) => skill.toLowerCase().includes(keyword))
      );
  }, [workerPool, assignedWorkerIds, query]);

  const workerById = useMemo(
    () => new Map(workerPool.map((worker) => [worker.workerId, worker])),
    [workerPool]
  );

  return (
    <div
      className={styles.overlay}
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) closeMapping();
      }}
    >
      <div className={styles.dialog} role="dialog" aria-modal="true" aria-labelledby="worker-mapping-title">
        <header className={styles.header}>
          <div>
            <h3 id="worker-mapping-title" className={styles.title}>
              Pemetaan Worker ke Node
            </h3>
            <p className={styles.subtitle}>
              Tetapkan setiap pekerja hasil ekstraksi arsip ke node proses tujuannya.
            </p>
          </div>
          <button type="button" className={styles.closeButton} onClick={closeMapping} aria-label="Tutup">
            ✕
          </button>
        </header>

        <div className={styles.toolbar}>
          <input
            type="search"
            className={styles.search}
            placeholder="Cari nama atau skill pekerja"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <button type="button" className={styles.ghostButton} onClick={autoDistributeWorkers}>
            Distribusi Otomatis
          </button>
          <button type="button" className={styles.ghostButton} onClick={clearWorkerAssignments}>
            Kosongkan
          </button>
        </div>

        <div className={styles.body}>
          <section className={styles.column}>
            <h4 className={styles.columnTitle}>
              Belum Ditugaskan ({unassignedWorkers.length})
            </h4>
            <div className={styles.list}>
              {unassignedWorkers.length === 0 ? (
                <p className={styles.empty}>Seluruh pekerja sudah dipetakan.</p>
              ) : (
                unassignedWorkers.map((worker) => (
                  <article key={worker.workerId} className={styles.workerCard}>
                    <div>
                      <span className={styles.workerName}>{worker.name}</span>
                      <span className={styles.workerMeta}>
                        {worker.skills.length > 0 ? worker.skills.join(", ") : "Tanpa skill tercatat"}
                      </span>
                    </div>
                    <select
                      className={styles.select}
                      value=""
                      onChange={(event) => {
                        if (event.target.value) assignWorker(event.target.value, worker.workerId);
                      }}
                    >
                      <option value="">Pilih node…</option>
                      {processNodes.map((node) => (
                        <option key={node.id} value={node.id}>
                          {(node.data as CanvasProcessData).label}
                        </option>
                      ))}
                    </select>
                  </article>
                ))
              )}
            </div>
          </section>

          <section className={styles.column}>
            <h4 className={styles.columnTitle}>Node Proses ({processNodes.length})</h4>
            <div className={styles.list}>
              {processNodes.length === 0 ? (
                <p className={styles.empty}>Belum ada node proses pada kanvas.</p>
              ) : (
                processNodes.map((node) => {
                  const assigned = workerAssignments[node.id] ?? [];
                  return (
                    <article key={node.id} className={styles.nodeCard}>
                      <header className={styles.nodeHeader}>
                        <span className={styles.nodeTitle}>
                          {(node.data as CanvasProcessData).label}
                        </span>
                        <span className={styles.nodeCount}>{assigned.length} pekerja</span>
                      </header>

                      {assigned.length === 0 ? (
                        <p className={styles.empty}>Belum ada pekerja.</p>
                      ) : (
                        <ul className={styles.chipList}>
                          {assigned.map((workerId) => (
                            <li key={workerId} className={styles.chip}>
                              {workerById.get(workerId)?.name ?? workerId}
                              <button
                                type="button"
                                className={styles.chipRemove}
                                onClick={() => unassignWorker(node.id, workerId)}
                                aria-label="Lepas penugasan"
                              >
                                ✕
                              </button>
                            </li>
                          ))}
                        </ul>
                      )}
                    </article>
                  );
                })
              )}
            </div>
          </section>
        </div>

        <footer className={styles.footer}>
          <span className={styles.summary}>
            {assignedWorkerIds.size} dari {workerPool.length} pekerja telah dipetakan.
          </span>
          <button type="button" className={styles.confirmButton} onClick={closeMapping}>
            Selesai
          </button>
        </footer>
      </div>
    </div>
  );
}

export default WorkerMappingModal;