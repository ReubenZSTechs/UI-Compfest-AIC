// frontend/src/components/feedback/AccountMenu.tsx
// Menu akun mengambang di sisi kiri atas canvas.
// Pengaturan operasional dipindah ke ikon Settings (⚙️) di Toolbar kiri.
// Gaya mengikuti Toolbar kiri (surface, border, shadow, tombol ikon-only).
import styles from "./AccountMenu.module.css";

const ICON_PROPS = {
  width: 18,
  height: 18,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
} as const;

export function AccountMenu() {
  return (
    <div className={styles.menu} role="group" aria-label="Menu akun">
      <button type="button" className={styles.menuButton} title="Akun" aria-label="Akun">
        <svg {...ICON_PROPS}>
          <circle cx="12" cy="8" r="4" />
          <path strokeLinecap="round" d="M4 20c1.5-3.5 4.5-5 8-5s6.5 1.5 8 5" />
        </svg>
      </button>
    </div>
  );
}

export default AccountMenu;
