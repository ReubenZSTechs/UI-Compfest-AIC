// frontend/src/features/canvas/components/CanvasHeader.tsx
// Header mengambang transparan di pojok kiri atas: tombol kembali (ke
// Dashboard / Saved Drafts) + judul proyek yang bisa diedit.
import { Link } from "react-router-dom";
import { useCanvasUIStore } from "@/store/canvasUI";
import styles from "./CanvasHeader.module.css";

interface CanvasHeaderProps {
  /** Handler tombol kembali (mendukung konfirmasi save/keluar). */
  onBackClick?: (e: React.MouseEvent) => void;
}

export function CanvasHeader({ onBackClick }: CanvasHeaderProps) {
  const projectTitle = useCanvasUIStore((s) => s.projectTitle);
  const setProjectTitle = useCanvasUIStore((s) => s.setProjectTitle);

  return (
    <div className={styles.header}>
      <Link
        to="/dashboard"
        className={styles.backLink}
        title="Kembali ke Dashboard"
        aria-label="Kembali ke Dashboard"
        onClick={onBackClick}
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
          <path d="M19 12H5" />
          <path d="m12 19-7-7 7-7" />
        </svg>
      </Link>
      <input
        type="text"
        className={styles.titleInput}
        value={projectTitle}
        onChange={(e) => setProjectTitle(e.target.value)}
        aria-label="Judul proyek"
      />
    </div>
  );
}

export default CanvasHeader;
