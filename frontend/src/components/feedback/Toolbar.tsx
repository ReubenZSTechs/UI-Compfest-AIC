// frontend/src/components/feedback/Toolbar.tsx
// Toolbar mengambang di sisi kiri canvas — mengatur mode aksi user (activeTool).
// Hanya ikon (tanpa label). Tool yang aktif menampilkan versi ikon yang di-FILL
// dengan warna (logo terisi penuh), tanpa border/stroke pada tombol.
import { useCanvasUIStore } from "@/store/canvasUI";
import type { ActiveTool } from "@/features/canvas/types/canvas.types";
import styles from "./Toolbar.module.css";

const ICON_PROPS = {
  width: 18,
  height: 18,
  viewBox: "0 0 24 24",
} as const;

const TOOLS: Array<{
  tool: ActiveTool;
  label: string;
  hint: string;
  icon: React.ReactNode;
  iconActive: React.ReactNode;
  action?: "undo" | "redo";
}> = [
  {
    tool: "select",
    label: "Pilih",
    hint: "Pilih & geser node",
    icon: (
      <svg {...ICON_PROPS} fill="none" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 3l14 9-6.5 1L9 19l-2-7z" />
      </svg>
    ),
    iconActive: (
      <svg {...ICON_PROPS}>
        <path fill="currentColor" d="M5 3l14 9-6.5 1L9 19l-2-7z" />
      </svg>
    ),
  },
  {
    tool: "add-process",
    label: "Tambah Proses",
    hint: "Klik kanvas untuk menambah node proses",
    icon: (
      <svg {...ICON_PROPS} fill="none" stroke="currentColor" strokeWidth={2}>
        <rect x="4" y="4" width="16" height="16" rx="2" />
        <path strokeLinecap="round" d="M12 8v8M8 12h8" />
      </svg>
    ),
    iconActive: (
      <svg {...ICON_PROPS}>
        <path
          fill="currentColor"
          fillRule="evenodd"
          d="M6 4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zm4.5 3.5v3h-3v3h3v3h3v-3h3v-3h-3v-3z"
        />
      </svg>
    ),
  },
  {
    tool: "add-worker",
    label: "Tambah Pekerja",
    hint: "Klik kanvas untuk menambah node pekerja",
    icon: (
      <svg {...ICON_PROPS} fill="none" stroke="currentColor" strokeWidth={2}>
        <circle cx="12" cy="8" r="4" />
        <path strokeLinecap="round" d="M4 20c1.5-3.5 4.5-5 8-5s6.5 1.5 8 5" />
      </svg>
    ),
    iconActive: (
      <svg {...ICON_PROPS}>
        <path
          fill="currentColor"
          d="M8 8a4 4 0 1 1 8 0 4 4 0 0 1-8 0zm-4 12c1.5-3.5 4.5-5 8-5s6.5 1.5 8 5v1H4z"
        />
      </svg>
    ),
  },
  {
    tool: "add-output",
    label: "Tambah Output",
    hint: "Klik kanvas untuk menambah node output (ujung alur)",
    icon: (
      <svg {...ICON_PROPS} fill="none" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M21 3H3v6h18zM6 9v10M18 9v10M6 19h12" />
        <path strokeLinecap="round" d="M12 13v4M10 15l2 2 2-2" />
      </svg>
    ),
    iconActive: (
      <svg {...ICON_PROPS}>
        <path
          fill="currentColor"
          fillRule="evenodd"
          d="M5 4a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v5h-6v4h6v5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1v-5h6v-4H5zm7 8V9h-2v3H7l5 5 5-5h-3z"
        />
      </svg>
    ),
  },
  {
    tool: "add-warehouse",
    label: "Tambah Gudang",
    hint: "Klik kanvas untuk menambah node gudang (sumber awal alur)",
    icon: (
      <svg {...ICON_PROPS} fill="none" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 10l9-5 9 5v10H3z" />
        <path strokeLinecap="round" d="M8 20v-6h8v6" />
      </svg>
    ),
    iconActive: (
      <svg {...ICON_PROPS}>
        <path fill="currentColor" d="M12 4l10 5.5V21h-6v-6H8v6H2V9.5z" />
      </svg>
    ),
  },
  {
    tool: "erase",
    label: "Hapus",
    hint: "Klik node/garis untuk menghapus",
    icon: (
      <svg {...ICON_PROPS} fill="none" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="m7 21-4.3-4.3c-1-1-1-2.5 0-3.4l9.6-9.6c1-1 2.5-1 3.4 0l5.6 5.6c1 1 1 2.5 0 3.4L13 21" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M22 21H7" />
        <path strokeLinecap="round" strokeLinejoin="round" d="m5 11 9 9" />
      </svg>
    ),
    iconActive: (
      <svg {...ICON_PROPS}>
        <path
          fill="currentColor"
          d="M7 21 2.7 16.7a2 2 0 0 1 0-2.8l9.6-9.6a2 2 0 0 1 2.8 0l5.6 5.6a2 2 0 0 1 0 2.8L13 21Z"
        />
      </svg>
    ),
  },
  {
    tool: "undo",
    label: "Undo",
    hint: "Batalkan perubahan (Ctrl+Z)",
    icon: (
      <svg {...ICON_PROPS} fill="none" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 15L4 10l5-5" />
        <path strokeLinecap="round" d="M4 10h9a7 7 0 0 1 7 7v2" />
      </svg>
    ),
    iconActive: (
      <svg {...ICON_PROPS}>
        <path
          fill="currentColor"
          d="M4 10l5-5v3h4.5a7.5 7.5 0 0 1 7.5 7.5V19h-2.5v-.5a5 5 0 0 0-5-5H9v3z"
        />
      </svg>
    ),
    action: "undo",
  },
];

export function Toolbar() {
  const activeTool = useCanvasUIStore((s) => s.activeTool);
  const setActiveTool = useCanvasUIStore((s) => s.setActiveTool);
  const undo = useCanvasUIStore((s) => s.undo);
  const redo = useCanvasUIStore((s) => s.redo);
  const canUndo = useCanvasUIStore((s) => s.past.length > 0);
  const canRedo = useCanvasUIStore((s) => s.future.length > 0);
  const openSettings = useCanvasUIStore((s) => s.openSettings);

  function handleTool(tool: ActiveTool, action?: "undo" | "redo") {
    if (action === "undo") {
      undo();
      return;
    }
    if (action === "redo") {
      redo();
      return;
    }
    setActiveTool(activeTool === tool ? "select" : tool);
  }

  return (
    <nav className={styles.toolbar} aria-label="Alat canvas">
      {TOOLS.map(({ tool, label, hint, icon, iconActive, action }) => {
        const isActive = activeTool === tool;
        const disabled = action === "undo" ? !canUndo : action === "redo" ? !canRedo : false;
        return (
          <button
            key={tool}
            type="button"
            title={hint}
            aria-label={label}
            className={`${styles.toolButton} ${isActive ? styles.active : ""}`}
            disabled={disabled}
            onClick={() => handleTool(tool, action)}
          >
            {isActive ? iconActive : icon}
          </button>
        );
      })}

      <div className={styles.divider} aria-hidden="true" />

      <button
        type="button"
        title="Operational Settings"
        aria-label="Operational Settings"
        className={styles.toolButton}
        onClick={() => openSettings()}
      >
        <svg
          width={18}
          height={18}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l-.06-.06a1.65 1.65 0 0 0 .33-1.82V11a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 .33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      </button>
    </nav>
  );
}

export default Toolbar;