// frontend/src/pages/AnalyticsPage.tsx
import { useParams, Link } from "react-router-dom";
import { useDraftStore } from "@/store/draftStore";
import styles from "./DashboardPage.module.css";

export function AnalyticsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const drafts = useDraftStore((s) => s.drafts);
  const draft = drafts.find((d) => d.projectId === projectId);

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>Project Analytics</h1>
          <p className={styles.subtitle}>
            Analisis metrik dan performa alur kerja untuk proyek{" "}
            <strong>{draft?.title ?? projectId ?? "Default"}</strong>
          </p>
        </div>
        <Link to="/dashboard" className={styles.cta}>
          ← Kembali ke Dashboard
        </Link>
      </div>

      <div className={styles.stats}>
        <div className={styles.statCard}>
          <span className={styles.statValue}>
            {draft?.canvasData.nodes?.length ?? 0}
          </span>
          <span className={styles.statLabel}>Total Node</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statValue}>
            {draft?.canvasData.edges?.length ?? 0}
          </span>
          <span className={styles.statLabel}>Relasi Alur</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statValue}>
            {draft?.optimizationData.generatedCards?.length ?? 0}
          </span>
          <span className={styles.statLabel}>Skenario Rekomendasi</span>
        </div>
      </div>
    </div>
  );
}

export default AnalyticsPage;
