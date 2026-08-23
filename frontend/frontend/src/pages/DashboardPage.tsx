// frontend/src/pages/DashboardPage.tsx
// Main Dashboard / Saved Drafts: daftar ProjectDraft terpadu yang tersimpan
// (auto-sync, tahan lintas login). Setiap kartu membuka draft dengan
// me-load projectId ke global project context lalu mengarahkan ke tahap
// terakhir user aktif (canvas / agent / recommendations).
import { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useDraftStore } from "@/store/draftStore";
import { useToastStore } from "@/store/toast";
import { TEMPLATE_META } from "@/features/canvas/templates/templates";
import type { ProjectDraft } from "@/features/project/types/project.types";
import styles from "./DashboardPage.module.css";

function formatUpdated(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const minutes = Math.floor((Date.now() - d.getTime()) / 60000);
  if (minutes < 1) return "Baru saja";
  if (minutes < 60) return `${minutes} menit lalu`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} jam lalu`;
  return d.toLocaleDateString("id-ID", { day: "numeric", month: "short", year: "numeric" });
}

const STEP_LABEL: Record<ProjectDraft["currentStep"], string> = {
  canvas: "Design Canvas",
  agent: "Agent & Settings",
  recommendations: "Rekomendasi Optimasi",
};

const STEP_ROUTE: Record<ProjectDraft["currentStep"], string> = {
  canvas: "/live",
  agent: "/agent",
  recommendations: "/project/:id/recommendations",
};

export function DashboardPage() {
  const navigate = useNavigate();
  const drafts = useDraftStore((s) => s.drafts);
  const deleteDraft = useDraftStore((s) => s.deleteDraft);
  const duplicateDraft = useDraftStore((s) => s.duplicateDraft);
  const showToast = useToastStore((s) => s.showToast);

  const stats = useMemo(() => {
    const totalNodes = drafts.reduce(
      (acc, d) => acc + (d.canvasData.nodes?.length ?? 0),
      0
    );
    const totalMessages = drafts.reduce(
      (acc, d) => acc + (d.agentData.chatHistory?.length ?? 0),
      0
    );
    return { count: drafts.length, totalNodes, totalMessages };
  }, [drafts]);

  /** Load projectId ke global context, lalu arahkan ke step terakhir user. */
  function openProject(draft: ProjectDraft) {
    useDraftStore.getState().loadDraft(draft.projectId);
    const base = STEP_ROUTE[draft.currentStep] ?? STEP_ROUTE.canvas;
    const url =
      draft.currentStep === "recommendations"
        ? `/project/${encodeURIComponent(draft.projectId)}/recommendations`
        : `${base}?projectId=${encodeURIComponent(draft.projectId)}`;
    navigate(url);
  }

  function handleDuplicate(id: string) {
    const copy = duplicateDraft(id);
    if (copy) showToast(`Draft "${copy.title}" diduplikasi`);
  }

  function handleDelete(id: string) {
    const target = drafts.find((d) => d.projectId === id);
    deleteDraft(id);
    showToast(`Draft "${target?.title ?? "Tanpa Nama"}" dihapus`, "info");
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>Saved Drafts</h1>
          <p className={styles.subtitle}>
            Satu draft membungkus seluruh alur kerja — canvas Live, chat Agent,
            kebijakan operasional, dan kartu rekomendasi optimasi.
          </p>
        </div>
        <Link to="/intro" className={styles.cta}>
          + Buat Draft Baru
        </Link>
      </div>

      <div className={styles.stats}>
        <div className={styles.statCard}>
          <span className={styles.statValue}>{stats.count}</span>
          <span className={styles.statLabel}>Draft Tersimpan</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statValue}>{stats.totalNodes}</span>
          <span className={styles.statLabel}>Total Node Kanvas</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statValue}>{stats.totalMessages}</span>
          <span className={styles.statLabel}>Pesan Agent</span>
        </div>
      </div>

      {drafts.length === 0 ? (
        <div className={styles.empty}>
          <p className={styles.emptyTitle}>Belum ada draft tersimpan</p>
          <p className={styles.emptyDesc}>
            Mulai dari Intro: pilih template, rancang alur di Live, berkoordinasi
            dengan Agent, lalu generate kartu optimasi — semua tersimpan otomatis
            dalam satu draft yang bisa dibuka lagi kapan saja.
          </p>
          <Link to="/intro" className={styles.emptyCta}>Mulai Desain Canvas →</Link>
        </div>
      ) : (
        <div className={styles.grid}>
          {drafts.map((d) => {
            const nodeCount = d.canvasData.nodes?.length ?? 0;
            const chatCount = d.agentData.chatHistory?.length ?? 0;
            const cardCount = d.optimizationData.generatedCards?.length ?? 0;
            const templateTitle = d.templateId ? TEMPLATE_META[d.templateId]?.title : null;

            return (
              <article key={d.projectId} className={styles.card}>
                <div className={styles.cardHeader}>
                  <h3 className={styles.cardTitle} title={d.title}>{d.title}</h3>
                  {templateTitle && <span className={styles.templateBadge}>{templateTitle}</span>}
                </div>

                <div className={styles.cardMeta}>
                  <span>Last Updated: <strong>{formatUpdated(d.lastUpdated)}</strong></span>
                  <span>
                    {nodeCount} node · {chatCount} pesan · {cardCount} kartu AI
                  </span>
                  <span className={styles.stepBadge}>
                    Terakhir: {STEP_LABEL[d.currentStep] ?? "Design Canvas"}
                  </span>
                </div>

                <div className={styles.actions}>
                  <button
                    type="button"
                    className={`${styles.action} ${styles.open}`}
                    onClick={() => openProject(d)}
                  >
                    Open
                  </button>
                  <button
                    type="button"
                    className={`${styles.action} ${styles.duplicate}`}
                    onClick={() => handleDuplicate(d.projectId)}
                  >
                    Duplicate
                  </button>
                  <button
                    type="button"
                    className={`${styles.action} ${styles.delete}`}
                    onClick={() => handleDelete(d.projectId)}
                  >
                    Delete
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default DashboardPage;