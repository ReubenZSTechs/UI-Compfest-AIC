// frontend/src/pages/RecommendationsPage.tsx
// Halaman rekomendasi DEDICATED (standalone) di /project/:projectId/recommendations.
// - Header minimal: Project Title + ikon profil user.
// - Auto-generate 3 AI Recommendation Cards (mock) begitu halaman terbuka.
// - Kartu ditampilkan di tengah dengan animasi masuk bertahap.
// - Klik kartu => lanjut ke halaman eksekusi/detail /project/:id/recommendation/:cardId.
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useDraftStore } from "@/store/draftStore";
import { useDraftAutoSync } from "@/hooks/useDraftAutoSync";
import { generateOptimizationCards } from "@/features/optimization/utils/generateCards";
import type { OptimizationCard } from "@/features/project/types/project.types";
import styles from "./RecommendationsPage.module.css";

function formatIdr(value: number): string {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(value);
}

export function RecommendationsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  useDraftAutoSync();

  const drafts = useDraftStore((s) => s.drafts);
  const activeDraftId = useDraftStore((s) => s.activeDraftId);
  const [generating, setGenerating] = useState(false);

  // Resolve projectId: URL param > query param > active draft
  const queryProjectId = searchParams.get("projectId");
  const effectiveProjectId = projectId || queryProjectId || activeDraftId;

  // Muat draft dari URL + pastikan kartu rekomendasi sudah digenerate.
  useEffect(() => {
    if (!effectiveProjectId) {
      // Tidak ada draft yang bisa dimuat → redirect ke dashboard.
      navigate("/dashboard", { replace: true });
      return;
    }
    const ds = useDraftStore.getState();
    if (ds.getActiveDraft()?.projectId !== effectiveProjectId) {
      ds.loadDraft(effectiveProjectId);
    }
    ds.setCurrentStep("recommendations");

    const draft = ds.findDraft(effectiveProjectId);
    if (draft && draft.optimizationData.generatedCards.length === 0) {
      setGenerating(true);
      void (async () => {
        const cards = await generateOptimizationCards(draft);
        useDraftStore.getState().setOptimizationCards(cards);
        setGenerating(false);
      })();
    }
  }, [effectiveProjectId, navigate]);

  const draft = drafts.find((d) => d.projectId === effectiveProjectId) ?? null;
  const cards = draft?.optimizationData.generatedCards ?? [];

  function openCard(card: OptimizationCard) {
    navigate(`/project/${encodeURIComponent(effectiveProjectId ?? "")}/recommendation/${card.id}`);
  }

  return (
    <div className={styles.workspace}>
      {/* Header minimal: Project Title + ikon profil user */}
      <header className={styles.header}>
        <Link
          to="/dashboard"
          className={styles.backLink}
          title="Kembali ke Dashboard"
          aria-label="Kembali ke Dashboard"
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

        <span className={styles.title}>{draft?.title ?? "Proyek Tanpa Judul"}</span>

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

        {generating || cards.length === 0 ? (
          <div className={styles.loading}>
            <span className={styles.spinner} aria-hidden="true" />
            <p>AI sedang menganalisis & menyusun skenario…</p>
          </div>
        ) : (
          <div className={styles.cardsRow}>
            {cards.map((card, i) => (
              <button
                key={card.id}
                type="button"
                className={styles.card}
                style={{ animationDelay: `${i * 0.12}s` }}
                onClick={() => openCard(card)}
              >
                <span className={styles.cardBadge}>{card.id.toUpperCase()}</span>
                <h3 className={styles.cardTitle}>{card.title}</h3>
                <p className={styles.cardBudget}>{formatIdr(card.budget)}</p>
                <p className={styles.cardDesc}>{card.description}</p>
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