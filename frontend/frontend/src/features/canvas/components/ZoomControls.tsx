// frontend/src/features/canvas/components/ZoomControls.tsx
// Kontrol zoom kustom (horizontal) di bar bawah canvas: perkecil, persentase
// zoom, perbesar, dan tampilkan semua. Menggantikan <Controls> bawaan React Flow.
import { useReactFlow, useStore } from "@xyflow/react";
import styles from "./ZoomControls.module.css";

const ICON_PROPS = {
  width: 16,
  height: 16,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
} as const;

export function ZoomControls() {
  const { zoomIn, zoomOut, fitView } = useReactFlow();
  const zoomLevel = useStore((s) => s.transform[2]);

  return (
    <div className={styles.zoomControls} role="group" aria-label="Kontrol zoom">
      <button
        type="button"
        className={styles.zoomButton}
        onClick={() => zoomOut()}
        aria-label="Perkecil"
        title="Perkecil (−)"
      >
        <svg {...ICON_PROPS}>
          <path strokeLinecap="round" d="M5 12h14" />
        </svg>
      </button>

      <span className={styles.zoomLabel} title="Level zoom">
        {Math.round(zoomLevel * 100)}%
      </span>

      <button
        type="button"
        className={styles.zoomButton}
        onClick={() => zoomIn()}
        aria-label="Perbesar"
        title="Perbesar (+)"
      >
        <svg {...ICON_PROPS}>
          <path strokeLinecap="round" d="M12 5v14M5 12h14" />
        </svg>
      </button>

      <button
        type="button"
        className={styles.zoomButton}
        onClick={() => fitView({ padding: 0.2 })}
        aria-label="Tampilkan semua node"
        title="Tampilkan semua node"
      >
        <svg {...ICON_PROPS}>
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"
          />
        </svg>
      </button>
    </div>
  );
}

export default ZoomControls;
