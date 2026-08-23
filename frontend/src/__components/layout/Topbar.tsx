import styles from "./Topbar.module.css";

export function Topbar() {
  return (
    <header className={styles.topbar}>
      <div className={styles.leftSection}>
        <h1 className={styles.title}>PABRIKERS Dashboard</h1>
        <span className={styles.badge}>
          <span className={styles.dot} />
          System Active
        </span>
      </div>

      <div className={styles.rightSection}>
        <div className={styles.userProfile}>
          <div className={styles.avatar}>CIT</div>
          <div className={styles.userInfo}>
            <div className={styles.userName}>CIT Admin</div>
            <div className={styles.userEmail}>cit@pabrikers.id</div>
          </div>
        </div>
      </div>
    </header>
  );
}

export default Topbar;