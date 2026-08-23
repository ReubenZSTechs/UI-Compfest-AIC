// frontend/src/pages/Canvaspage.tsx
// Halaman 2: Full Canvas Workspace (full-screen, tanpa AppShell).
// Komposisi: CanvasBoard tengah | Toolbar kiri | SidebarDetail kanan |
// Header mengambang kiri-atas | Bar aksi bawah-tengah (analisis + kontrol zoom).
// Sesi terpadu (projectId → ProjectDraft) dipakai bersama halaman Agent &
// Recommendations: inisialisasi via useCanvasSessionInit + auto-sync otomatis
// ke SATU record draft agar semua tab berbagi state yang sama.
import { CanvasBoard } from "@/features/canvas/components/CanvasBoard";
import { CanvasHeader } from "@/features/canvas/components/CanvasHeader";
import { SidebarDetail } from "@/features/canvas/components/SidebarDetail";
import { Toolbar } from "@/components/feedback/Toolbar";
import { AccountMenu } from "@/components/feedback/AccountMenu";
import { LiveAgentSwitcher } from "@/features/canvas/components/LiveAgentSwitcher";
import { OperationalSettingsModal } from "@/features/canvas/components/OperationalSettingsModal";
import { useCanvasSessionInit } from "@/features/canvas/hooks/useCanvasSessionInit";
import { useExitConfirm } from "@/features/canvas/hooks/useExitConfirm";
import { useDraftAutoSync } from "@/hooks/useDraftAutoSync";
import styles from "./Canvaspage.module.css";

export function CanvasPage() {
  // Inisialisasi/muat draft terpadu (idempotent terhadap tab switch).
  useCanvasSessionInit("canvas");

  // Setiap perubahan working state otomatis disinkronkan ke ProjectDraft aktif.
  useDraftAutoSync();

  // Konfirmasi save/keluar saat tombol kembali ditekan.
  const { handleBackClick, guard } = useExitConfirm();

  return (
    <div className={styles.workspace}>
      <div className={styles.main}>
        <CanvasBoard />

        <CanvasHeader onBackClick={handleBackClick} />

        <AccountMenu />

        <div className={styles.switcherLayer}>
          <LiveAgentSwitcher />
        </div>

        <div className={styles.toolbarLayer}>
          <Toolbar />
        </div>

        <SidebarDetail />

        <OperationalSettingsModal />

        {guard}
      </div>
    </div>
  );
}

export default CanvasPage;