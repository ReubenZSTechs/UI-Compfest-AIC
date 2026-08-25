import { Link } from "react-router-dom";
import styles from "./Topbar.module.css";

export function Topbar() {
  return (
    <header className={styles.navbar}>
      <div className={styles.navInner}>
        <div className={styles.navLeftGroup}>
          <Link to="/" className={styles.navBrand}>
            <div className={styles.brandLogoBox}>
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#ffffff"
                strokeWidth="2.4"
              >
                <path d="M3 3v18h18" />
                <path d="m19 9-5 5-4-4-3 3" />
              </svg>
            </div>
            <div className={styles.brandTitleCol}>
              <span className={styles.brandName}>Pabrikers</span>
              <span className={styles.brandTagline}>Smart Factory Platform</span>
            </div>
          </Link>
        </div>

        <div className={styles.navActions}>
          <Link
            to="/dashboard"
            className={styles.profileBtn}
            aria-label="CIT Admin Profile"
          >
            <div className={styles.profileAvatar}>CIT</div>
            <span className={styles.profileTooltip}>CIT Admin</span>
          </Link>
        </div>
      </div>
    </header>
  );
}

export default Topbar;
