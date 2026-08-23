// frontend/src/features/canvas/utils/session.ts
// Utilitas identitas sesi canvas: 1 templateId = 1 group (canvasId) yang
// menghubungkan halaman Live & Agent dalam satu konteks tersimpan.

/** Membuat ID sesi unik untuk satu grup Live+Agent. */
export function createCanvasId(): string {
  return `canvas-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}