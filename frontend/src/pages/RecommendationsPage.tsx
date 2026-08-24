import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useDraftStore } from "@/store/draftStore";
import { useDraftAutoSync } from "@/hooks/useDraftAutoSync";
import { generateOptimizationCards } from "@/features/optimization/utils/generateCards";
import type { OptimizationCard } from "@/features/project/types/project.types";
import styles from "./RecommendationsPage.module.css";

// ==========================================
// 1. TAMBAHKAN FLAG & MOCK DATA UNTUK UI TESTING
// ==========================================
const USE_MOCK_DATA = true; // Set ke 'false' jika ingin menggunakan data asli kembali

const MOCK_CARDS: Partial<OptimizationCard>[] = [
  {
    id: "rec_1",
    title: "Otomasi Lini Perakitan",
    budget: 150000000,
    description: "Mengganti 2 stasiun manual dengan lengan robotik untuk meningkatkan throughput sebesar 15%.",
  },
  {
    id: "rec_2",
    title: "Penambahan Shift Kerja",
    budget: 45000000,
    description: "Menambah shift malam dengan 5 pekerja ekstra untuk mengejar target produksi harian tanpa beli mesin.",
  },
  {
    id: "rec_3",
    title: "Optimasi Layout Pabrik",
    budget: 12000000,
    description: "Menyusun ulang letak stasiun kerja untuk mengurangi bottleneck dan waktu tempuh material antar stasiun.",
  }
];
// ==========================================

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

  const queryProjectId = searchParams.get("projectId");
  const effectiveProjectId = projectId || queryProjectId || activeDraftId;

  useEffect(() => {
    // 2. BYPASS REDIRECT JIKA SEDANG MENGGUNAKAN MOCK DATA
    if (USE_MOCK_DATA) return; 

    if (!effectiveProjectId) {
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
  
  // 3. TENTUKAN DATA YANG AKAN DI-RENDER
  const actualCards = draft?.optimizationData.generatedCards ?? [];
  const displayCards = (USE_MOCK_DATA ? MOCK_CARDS : actualCards) as OptimizationCard[];
  const isGenerating = USE_MOCK_DATA ? false : (generating || actualCards.length === 0);

  function openCard(card: OptimizationCard) {
    navigate(`/project/${encodeURIComponent(effectiveProjectId ?? "mock-project")}/recommendation/${card.id}`);
  }

  return (
    <div className={styles.workspace}>
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

        {/* Pakai judul mock jika tidak ada draft */}
        <span className={styles.title}>
          {USE_MOCK_DATA ? "Proyek Testing UI" : (draft?.title ?? "Proyek Tanpa Judul")}
        </span>

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

        {/* 4. RENDER BERDASARKAN STATUS GENERATING (MOCK SELALU FALSE) */}
        {isGenerating ? (
          <div className={styles.loading}>
            <span className={styles.spinner} aria-hidden="true" />
            <p>AI sedang menganalisis & menyusun skenario…</p>
          </div>
        ) : (
          <div className={styles.cardsRow}>
            {displayCards.map((card, i) => (
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