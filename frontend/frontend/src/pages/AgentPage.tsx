// frontend/src/pages/AgentPage.tsx
// Halaman Agent AI: chatbot vertikal ringkas untuk berkoordinasi dengan AI saat
// mengubah alur produksi di halaman Live. Menjaga elemen melayang yang sama
// dengan Live: tombol kembali + menu akun (kiri-atas) dan saklar Live/Agent
// (kanan-atas). Berbagi SATU ProjectDraft dengan Live & Recommendations.
import { Link } from "react-router-dom";
import { AccountMenu } from "@/components/feedback/AccountMenu";
import { LiveAgentSwitcher } from "@/features/canvas/components/LiveAgentSwitcher";
import { AgentChat } from "@/features/agent/components/AgentChat";
import { useCanvasSessionInit } from "@/features/canvas/hooks/useCanvasSessionInit";
import { useExitConfirm } from "@/features/canvas/hooks/useExitConfirm";
import { useDraftAutoSync } from "@/hooks/useDraftAutoSync";
import styles from "./AgentPage.module.css";

export function AgentPage() {
  // Ikut draft terpadu yang sama dengan Live: restore chat + canvas saat
  // dibuka langsung, tanpa me-reset state saat berpindah tab Live ↔ Agent.
  useCanvasSessionInit("agent");
  useDraftAutoSync();

  // Konfirmasi save/keluar saat tombol kembali ditekan.
  const { handleBackClick, guard } = useExitConfirm();

  return (
    <div className={styles.workspace}>
      <div className={styles.main}>
        <Link
          to="/dashboard"
          className={styles.backLink}
          title="Kembali ke Dashboard"
          aria-label="Kembali ke Dashboard"
          onClick={handleBackClick}
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

        <div className={styles.accountLayer}>
          <AccountMenu />
        </div>

        <div className={styles.switcherLayer}>
          <LiveAgentSwitcher />
        </div>

        <div className={styles.chatLayer}>
          <AgentChat />
        </div>

        {guard}
      </div>
    </div>
  );
}

export default AgentPage;