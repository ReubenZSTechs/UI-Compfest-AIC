// frontend/src/components/layout/AppShell.tsx
import { Outlet } from "react-router-dom";
import Topbar from "./Topbar";
import styles from "./AppShell.module.css";

export function AppShell() {
  return (
    <div className={styles.layout}>
      <div className={styles.mainWrapper}>
        <Topbar />
        <main className={styles.content}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default AppShell;