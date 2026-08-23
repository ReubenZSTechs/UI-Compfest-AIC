// frontend/src/features/canvas/components/LiveAgentSwitcher.tsx
// Saklar halaman atas-kanan: berpindah antara Live (canvas) dan Agent
// (chatbot) — HANYA dua tab [Live | Agent]. Menjaga projectId yang sama agar
// seluruh alur kerja tetap dalam SATU ProjectDraft.
import { NavLink, useLocation } from "react-router-dom";
import { useDraftStore } from "@/store/draftStore";
import styles from "./LiveAgentSwitcher.module.css";

export function LiveAgentSwitcher() {
  const { search } = useLocation();
  const activeDraftId = useDraftStore((s) => s.activeDraftId);

  // Pastikan projectId selalu terbawa saat switch tab Live ↔ Agent,
  // bahkan jika URL saat ini tidak membawa ?projectId= secara eksplisit.
  const effectiveSearch = search || (activeDraftId ? `?projectId=${activeDraftId}` : "");

  const links = [
    { to: `/live${effectiveSearch}`, label: "Live" },
    { to: `/agent${effectiveSearch}`, label: "Agent" },
  ];

  return (
    <nav className={styles.switcher} aria-label="Beralih antara Live dan Agent">
      {links.map((link) => (
        <NavLink
          key={link.to}
          to={link.to}
          className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ""}`}
        >
          {link.label}
        </NavLink>
      ))}
    </nav>
  );
}

export default LiveAgentSwitcher;