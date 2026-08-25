import { useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useCanvasUIStore } from "@/store/canvasUI";
import type { CanvasProcessData, CanvasShift } from "../types/canvas.types";
import styles from "./ShiftPlannerModal.module.css";

const DEFAULT_BREAK_DURATION = 60;

function minutesBetween(startTime: string, endTime: string): number {
  const [startHour, startMinute] = startTime.split(":").map(Number);
  const [endHour, endMinute] = endTime.split(":").map(Number);
  const start = startHour * 60 + startMinute;
  const end = endHour * 60 + endMinute;
  return end > start ? end - start : end + 24 * 60 - start;
}

export function ShiftPlannerModal() {
  const shiftPlannerOpen = useCanvasUIStore((s) => s.shiftPlannerOpen);
  if (!shiftPlannerOpen) return null;
  return createPortal(<ShiftPlannerDialog />, document.body);
}

function ShiftPlannerDialog() {
  const nodes = useCanvasUIStore((s) => s.nodes);
  const shifts = useCanvasUIStore((s) => s.shifts);
  const workerPool = useCanvasUIStore((s) => s.workerPool);
  const shiftAssignments = useCanvasUIStore((s) => s.shiftAssignments);
  const activeShiftId = useCanvasUIStore((s) => s.activeShiftId);
  const setShifts = useCanvasUIStore((s) => s.setShifts);
  const upsertShift = useCanvasUIStore((s) => s.upsertShift);
  const removeShift = useCanvasUIStore((s) => s.removeShift);
  const setActiveShiftId = useCanvasUIStore((s) => s.setActiveShiftId);
  const assignWorkerToShift = useCanvasUIStore((s) => s.assignWorkerToShift);
  const unassignWorkerFromShift = useCanvasUIStore((s) => s.unassignWorkerFromShift);
  const autoDistributeShiftWorkers = useCanvasUIStore((s) => s.autoDistributeShiftWorkers);
  const clearShiftAssignments = useCanvasUIStore((s) => s.clearShiftAssignments);
  const closeShiftPlanner = useCanvasUIStore((s) => s.closeShiftPlanner);

  const [query, setQuery] = useState("");

  const processNodes = useMemo(
    () => nodes.filter((node) => node.data.kind === "process"),
    [nodes]
  );

  const activeShift = shifts.find((shift) => shift.shiftId === activeShiftId) ?? shifts[0];
  const currentMap = shiftAssignments[activeShift?.shiftId ?? ""] ?? {};

  const assignedIds = useMemo(
    () => new Set(Object.values(currentMap).flat()),
    [currentMap]
  );

  const availableWorkers = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return workerPool
      .filter((worker) => !assignedIds.has(worker.workerId))
      .filter(
        (worker) =>
          keyword.length === 0 ||
          worker.name.toLowerCase().includes(keyword) ||
          worker.skills.some((skill) => skill.toLowerCase().includes(keyword))
      );
  }, [workerPool, assignedIds, query]);

  const workerById = useMemo(
    () => new Map(workerPool.map((worker) => [worker.workerId, worker])),
    [workerPool]
  );

  function addShift() {
    const nextIndex = shifts.length + 1;
    const shift: CanvasShift = {
      shiftId: `shift-${String(nextIndex).padStart(2, "0")}`,
      shiftName: `Shift ${nextIndex}`,
      startTime: "16:00",
      endTime: "00:00",
      handoverMinutes: 15,
      breaks: [
        {
          breakId: "break-01",
          label: "Istirahat",
          startOffsetMinutes: 240,
          durationMinutes: DEFAULT_BREAK_DURATION,
        },
      ],
    };
    upsertShift(shift);
    setActiveShiftId(shift.shiftId);
  }

  function patchShift(shiftId: string, patch: Partial<CanvasShift>) {
    setShifts(
      shifts.map((shift) => (shift.shiftId === shiftId ? { ...shift, ...patch } : shift))
    );
  }

  function patchBreak(shiftId: string, breakId: string, patch: Partial<CanvasShift["breaks"][number]>) {
    const shift = shifts.find((item) => item.shiftId === shiftId);
    if (!shift) return;

    patchShift(shiftId, {
      breaks: shift.breaks.map((item) =>
        item.breakId === breakId ? { ...item, ...patch } : item
      ),
    });
  }

  function addBreak(shiftId: string) {
    const shift = shifts.find((item) => item.shiftId === shiftId);
    if (!shift) return;

    patchShift(shiftId, {
      breaks: [
        ...shift.breaks,
        {
          breakId: `break-${String(shift.breaks.length + 1).padStart(2, "0")}`,
          label: "Istirahat Tambahan",
          startOffsetMinutes: 120,
          durationMinutes: 15,
        },
      ],
    });
  }

  if (!activeShift) return null;

  const shiftLength = minutesBetween(activeShift.startTime, activeShift.endTime);

  return (
    <div
      className={styles.overlay}
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) closeShiftPlanner();
      }}
    >
      <div className={styles.dialog} role="dialog" aria-modal="true">
        <header className={styles.header}>
          <div>
            <h3 className={styles.title}>Penjadwalan Shift & Penugasan Pekerja</h3>
            <p className={styles.subtitle}>
              Atur jumlah shift, jam istirahat, dan pekerja yang bertugas di tiap node per shift.
            </p>
          </div>
          <button type="button" className={styles.closeButton} onClick={closeShiftPlanner}>
            ✕
          </button>
        </header>

        <nav className={styles.tabBar}>
          {shifts.map((shift) => (
            <button
              key={shift.shiftId}
              type="button"
              className={`${styles.tab} ${shift.shiftId === activeShift.shiftId ? styles.tabActive : ""}`}
              onClick={() => setActiveShiftId(shift.shiftId)}
            >
              {shift.shiftName}
              <span className={styles.tabMeta}>
                {shift.startTime}–{shift.endTime}
              </span>
            </button>
          ))}
          <button type="button" className={styles.tabAdd} onClick={addShift}>
            + Shift
          </button>
        </nav>

        <section className={styles.configRow}>
          <label className={styles.configField}>
            <span className={styles.configLabel}>Nama Shift</span>
            <input
              type="text"
              className={styles.input}
              value={activeShift.shiftName}
              onChange={(event) =>
                patchShift(activeShift.shiftId, { shiftName: event.target.value })
              }
            />
          </label>

          <label className={styles.configField}>
            <span className={styles.configLabel}>Mulai</span>
            <input
              type="time"
              className={styles.input}
              value={activeShift.startTime}
              onChange={(event) =>
                patchShift(activeShift.shiftId, { startTime: event.target.value })
              }
            />
          </label>

          <label className={styles.configField}>
            <span className={styles.configLabel}>Selesai</span>
            <input
              type="time"
              className={styles.input}
              value={activeShift.endTime}
              onChange={(event) =>
                patchShift(activeShift.shiftId, { endTime: event.target.value })
              }
            />
          </label>

          <label className={styles.configField}>
            <span className={styles.configLabel}>Handover (menit)</span>
            <input
              type="number"
              min={0}
              max={120}
              className={styles.input}
              value={activeShift.handoverMinutes}
              onChange={(event) =>
                patchShift(activeShift.shiftId, {
                  handoverMinutes: Number(event.target.value) || 0,
                })
              }
            />
          </label>

          {shifts.length > 1 && (
            <button
              type="button"
              className={styles.dangerButton}
              onClick={() => {
                removeShift(activeShift.shiftId);
                setActiveShiftId(shifts[0].shiftId);
              }}
            >
              Hapus Shift
            </button>
          )}
        </section>

        <section className={styles.breakSection}>
          <h4 className={styles.sectionTitle}>Jam Istirahat ({shiftLength} menit shift)</h4>

          {activeShift.breaks.map((window) => (
            <div key={window.breakId} className={styles.breakRow}>
              <input
                type="text"
                className={styles.input}
                value={window.label}
                onChange={(event) =>
                  patchBreak(activeShift.shiftId, window.breakId, { label: event.target.value })
                }
              />
              <label className={styles.inlineField}>
                <span>Mulai +</span>
                <input
                  type="number"
                  min={0}
                  max={shiftLength}
                  className={styles.inputNarrow}
                  value={window.startOffsetMinutes}
                  onChange={(event) =>
                    patchBreak(activeShift.shiftId, window.breakId, {
                      startOffsetMinutes: Number(event.target.value) || 0,
                    })
                  }
                />
                <span>menit</span>
              </label>
              <label className={styles.inlineField}>
                <span>Durasi</span>
                <input
                  type="number"
                  min={0}
                  max={240}
                  className={styles.inputNarrow}
                  value={window.durationMinutes}
                  onChange={(event) =>
                    patchBreak(activeShift.shiftId, window.breakId, {
                      durationMinutes: Number(event.target.value) || 0,
                    })
                  }
                />
                <span>menit</span>
              </label>
            </div>
          ))}

          <button
            type="button"
            className={styles.ghostButton}
            onClick={() => addBreak(activeShift.shiftId)}
          >
            + Tambah Istirahat
          </button>
        </section>

        <div className={styles.toolbar}>
          <input
            type="search"
            className={styles.search}
            placeholder="Cari nama atau skill pekerja"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <button
            type="button"
            className={styles.ghostButton}
            onClick={() => autoDistributeShiftWorkers(activeShift.shiftId)}
          >
            Distribusi Otomatis
          </button>
          <button
            type="button"
            className={styles.ghostButton}
            onClick={() => clearShiftAssignments(activeShift.shiftId)}
          >
            Kosongkan Shift Ini
          </button>
        </div>

        <div className={styles.body}>
          <section className={styles.column}>
            <h4 className={styles.columnTitle}>Tersedia ({availableWorkers.length})</h4>
            <div className={styles.list}>
              {availableWorkers.length === 0 ? (
                <p className={styles.empty}>Seluruh pekerja sudah bertugas pada shift ini.</p>
              ) : (
                availableWorkers.map((worker) => (
                  <article key={worker.workerId} className={styles.workerCard}>
                    <div>
                      <span className={styles.workerName}>{worker.name}</span>
                      <span className={styles.workerMeta}>
                        {worker.skills.length > 0
                          ? worker.skills.slice(0, 3).join(", ")
                          : "Tanpa skill tercatat"}
                      </span>
                    </div>
                    <select
                      className={styles.select}
                      value=""
                      onChange={(event) => {
                        if (event.target.value) {
                          assignWorkerToShift(
                            activeShift.shiftId,
                            event.target.value,
                            worker.workerId
                          );
                        }
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
              {processNodes.map((node) => {
                const assigned = currentMap[node.id] ?? [];
                return (
                  <article key={node.id} className={styles.nodeCard}>
                    <header className={styles.nodeHeader}>
                      <span className={styles.nodeTitle}>
                        {(node.data as CanvasProcessData).label}
                      </span>
                      <span className={styles.nodeCount}>{assigned.length} pekerja</span>
                    </header>

                    {assigned.length === 0 ? (
                      <p className={styles.empty}>Belum ada pekerja pada shift ini.</p>
                    ) : (
                      <ul className={styles.chipList}>
                        {assigned.map((workerId) => (
                          <li key={workerId} className={styles.chip}>
                            {workerById.get(workerId)?.name ?? workerId}
                            <button
                              type="button"
                              className={styles.chipRemove}
                              onClick={() =>
                                unassignWorkerFromShift(activeShift.shiftId, node.id, workerId)
                              }
                            >
                              ✕
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </article>
                );
              })}
            </div>
          </section>
        </div>

        <footer className={styles.footer}>
          <span className={styles.summary}>
            {assignedIds.size} dari {workerPool.length} pekerja bertugas di {activeShift.shiftName}.
          </span>
          <button type="button" className={styles.confirmButton} onClick={closeShiftPlanner}>
            Selesai
          </button>
        </footer>
      </div>
    </div>
  );
}

export default ShiftPlannerModal;