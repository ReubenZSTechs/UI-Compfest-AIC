import { useEffect } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useDraftStore } from "@/store/draftStore";
import { useDraftAutoSync } from "@/hooks/useDraftAutoSync";
import { useRlScenarios } from "@/features/optimization/hooks/useRlScenarios";
import { useRlOptimizationJob } from "@/features/optimization/hooks/useRlOptimizationJob";
import { resolveFactoryContext } from "@/features/optimization/utils/resolveFactory";
import type { RlScenario } from "@/features/optimization/types/rlScenario.types";
import styles from "./RecommendationsPage.module.css";

/** Formats a rupiah amount without decimals. */
function formatIdr(value: number): string {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(value);
}

/** Lists the three RL scenarios of a factory and opens the selected one. */
export function RecommendationsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  useDraftAutoSync();

  const drafts = useDraftStore((s) => s.drafts);
  const routeId = projectId || searchParams.get("projectId");
  const { factoryId, draft } = resolveFactoryContext(
    drafts,
    routeId,
    searchParams.get("factoryId")
  );

  const { scenarios, isLoading } = useRlScenarios(factoryId);
  const { job, isTraining } = useRlOptimizationJob(factoryId);

  useEffect(() => {
    if (!routeId) {
      navigate("/dashboard", { replace: true });
      return;
    }
    if (draft) {
      const ds = useDraftStore.getState();
      if (ds.getActiveDraft()?.projectId !== draft.projectId) {
        ds.loadDraft(draft.projectId);
      }
      ds.setCurrentStep("recommendations");
    }
  }, [routeId, draft, navigate]);

  function openScenario(scenario: RlScenario) {
    navigate(
      `/project/${encodeURIComponent(routeId ?? "")}/recommendation/${scenario.scenario_id}`
    );
  }

  const twinLink = factoryId
    ? `/digital-twin?factoryId=${encodeURIComponent(factoryId)}`
    : "/dashboard";

  return (
    <div className={styles.workspace}>
      <header className={styles.header}>
        <Link
          to={twinLink}
          className={styles.backLink}
          title="Kembali ke Digital Twin"
          aria-label="Kembali ke Digital Twin"
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

        <span className={styles.title}>{draft?.title ?? factoryId ?? "Proyek Tanpa Judul"}</span>

        <button
          type="button"
          className={styles.profileIcon}
          title="Profil"
          aria-label="Profil user"
        >
          <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <circle cx="12" cy="8" r="4" />
            <path strokeLinecap="round" d="M4 20c1.5-3.5 4.5-5 8-5s6.5 1.5 8 5" />
          </svg>
        </button>
      </header>

      <main className={styles.body}>
        <p className={styles.eyebrow}>Pilih skenario optimasi terbaik</p>

        {isTraining || (isLoading && scenarios.length === 0) ? (
          <div className={styles.loading}>
            <span className={styles.spinner} aria-hidden="true" />
            <p>
              {isTraining
                ? `RL sedang mencari aksi optimal… ${Math.round(job?.progress_pct ?? 0)}%`
                : "Memuat skenario hasil RL…"}
            </p>
          </div>
        ) : scenarios.length === 0 ? (
          <div className={styles.loading}>
            <p>
              {job?.status === "failed"
                ? `Training RL gagal: ${job.error_message ?? "kesalahan tidak diketahui"}`
                : "Belum ada hasil optimasi RL untuk pabrik ini. Jalankan simulasi di halaman Digital Twin terlebih dahulu."}
            </p>
            <Link to={twinLink} className={styles.cardAction}>
              Buka Digital Twin →
            </Link>
          </div>
        ) : (
          <div className={styles.cardsRow}>
            {scenarios.map((scenario, i) => (
              <button
                key={scenario.scenario_id}
                type="button"
                className={styles.card}
                style={{ animationDelay: `${i * 0.12}s` }}
                onClick={() => openScenario(scenario)}
              >
                <span className={styles.cardBadge}>
                  {scenario.recommended ? "DIREKOMENDASIKAN" : `SKENARIO ${i + 1}`}
                </span>
                <h3 className={styles.cardTitle}>{scenario.title}</h3>
                <p className={styles.cardBudget}>{formatIdr(scenario.constraints.capex_used_rp)}</p>
                <p className={styles.cardDesc}>{scenario.insight || scenario.description}</p>
                <span className={styles.cardAction}>Lihat Detail →</span>
              </button>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

export default RecommendationsPage;
