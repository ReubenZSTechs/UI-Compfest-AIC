import { useState, useMemo, useEffect } from "react";
import { Link, useParams, useNavigate, useLocation, useSearchParams } from "react-router-dom";
import {
  getResolvedScenarios,
  type ScenarioData,
} from "@/features/optimization/data/analyticsScenariosData";
import { ThroughputShiftChart } from "@/features/optimization/components/ThroughputShiftChart";
import { CostBreakdownChart } from "@/features/optimization/components/CostBreakdownChart";
import { ProductionFlowGraphPreview } from "@/features/optimization/components/ProductionFlowGraphPreview";
import { WhatIfPlayground } from "@/features/optimization/components/WhatIfPlayground";
import { RlFlowSimulation } from "@/features/optimization/components/RlFlowSimulation";
import { useRlScenarios } from "@/features/optimization/hooks/useRlScenarios";
import { mapRlScenarioToScenarioData, formatStationLabel } from "@/features/optimization/utils/mapRlScenario";
import { useDraftStore } from "@/store/draftStore";
import { useToastStore } from "@/store/toast";
import { useDraftAutoSync } from "@/hooks/useDraftAutoSync";
import styles from "./ExecutionPage.module.css";

function formatRupiah(value: number): string {
  if (value <= 0) return "Rp 0";
  if (value >= 1_000_000_000) return `Rp ${(value / 1_000_000_000).toFixed(2)} Miliar`;
  if (value >= 1_000_000) return `Rp ${(value / 1_000_000).toFixed(1)} Juta`;
  return `Rp ${Math.round(value).toLocaleString("id-ID")}`;
}

export function ExecutionPage() {
  const { projectId, cardId } = useParams<{ projectId?: string; cardId?: string }>();
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const showToast = useToastStore((s) => s.showToast);

  useDraftAutoSync();

  const queryProjectId = searchParams.get("projectId");
  const queryFactoryId = searchParams.get("factoryId") || searchParams.get("factory_id");
  const effectiveProjectId = projectId || queryProjectId;

  const drafts = useDraftStore((s) => s.drafts);
  const matchedDraft = drafts.find((d) => d.projectId === effectiveProjectId);
  const draft = matchedDraft || drafts[0]; // display-only fallback (title, cards)
  const generatedCards = draft?.optimizationData?.generatedCards;

  const factoryId =
    queryFactoryId ||
    matchedDraft?.factoryId ||
    effectiveProjectId ||
    undefined;

  const { scenarios: rlScenarios, meta, isLoading, isError, error } = useRlScenarios(factoryId);

  const fallbackScenarios = useMemo(
    () => getResolvedScenarios(generatedCards),
    [generatedCards]
  );

  const usingRlData = rlScenarios.length > 0;

  const resolvedScenarios = useMemo<ScenarioData[]>(() => {
    if (!usingRlData) return fallbackScenarios;
    return rlScenarios.map(mapRlScenarioToScenarioData);
  }, [usingRlData, rlScenarios, fallbackScenarios]);

  const activeScenarioId = useMemo(() => {
    if (cardId) {
      const match = resolvedScenarios.find(
        (s) =>
          s.id.toLowerCase() === cardId.toLowerCase() ||
          s.shortTitle.toLowerCase().includes(cardId.toLowerCase()) ||
          s.title.toLowerCase().includes(cardId.toLowerCase())
      );
      if (match) return match.id;
    }

    const path = location.pathname.toLowerCase();
    if (path.includes("3") || path.includes("skenario-c")) {
      return resolvedScenarios[2]?.id ?? resolvedScenarios[0]?.id ?? "";
    }
    if (path.includes("2") || path.includes("skenario-b")) {
      return resolvedScenarios[1]?.id ?? resolvedScenarios[0]?.id ?? "";
    }
    return resolvedScenarios[0]?.id ?? "";
  }, [cardId, location.pathname, resolvedScenarios]);

  const [activeTab, setActiveTab] = useState<string>(activeScenarioId);
  const [showGraph, setShowGraph] = useState<boolean>(false);
  const [generatedDate] = useState<string>(() => {
    const now = new Date();
    const date = `${now.getDate()}/${now.getMonth() + 1}/${now.getFullYear()}`;
    const clock = [now.getHours(), now.getMinutes(), now.getSeconds()]
      .map((part) => String(part).padStart(2, "0"))
      .join(".");
    return `${date}, ${clock}`;
  });

  useEffect(() => {
    setActiveTab(activeScenarioId);
  }, [activeScenarioId]);

  const activeIndex = useMemo(() => {
    const index = resolvedScenarios.findIndex((s) => s.id === activeTab);
    return index >= 0 ? index : 0;
  }, [resolvedScenarios, activeTab]);

  const currentScenario: ScenarioData | undefined = resolvedScenarios[activeIndex];
  const currentRlScenario = usingRlData ? rlScenarios[activeIndex] : null;

  function handleTabClick(tabId: string) {
    setActiveTab(tabId);
    if (projectId) {
      navigate(`/project/${encodeURIComponent(projectId)}/recommendation/${tabId}`);
    }
  }

  function handleBackToDashboard() {
    showToast("Kembali ke Dashboard Utama", "info");
    navigate("/dashboard");
  }

  function handleGoToDigitalTwin() {
    if (!factoryId) {
      showToast("Factory ID belum tersedia.", "error");
      return;
    }
    showToast("Membuka Digital Twin...", "info");
    navigate(`/digital-twin?factoryId=${encodeURIComponent(factoryId)}`);
  }

  if (isLoading) {
    return (
      <div className={styles.pageContainer}>
        <div className={styles.cardContainer}>
          <p className={styles.cardDescription}>
            Memuat hasil optimasi reinforcement learning...
          </p>
        </div>
      </div>
    );
  }

  if (!currentScenario) {
    return (
      <div className={styles.pageContainer}>
        <div className={styles.cardContainer}>
          <p className={styles.cardDescription}>
            Belum ada skenario yang tersedia untuk factory ini.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.pageContainer}>
      {/* 1. TOP APP BAR */}
      <header className={styles.topBar}>
        <div className={styles.barLeft}>
          <Link
            to={
              projectId
                ? `/project/${encodeURIComponent(projectId)}/recommendations`
                : "/dashboard"
            }
            className={styles.backButton}
            title="Kembali ke Dashboard / Rekomendasi"
            aria-label="Kembali"
          >
            <svg
              width="15"
              height="15"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M19 12H5" />
              <path d="m12 19-7-7 7-7" />
            </svg>
          </Link>

          <div className={styles.brandTitleWrap}>
            <div className={styles.brandIcon}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2.2">
                <path d="M3 3v18h18" />
                <path d="m19 9-5 5-4-4-3 3" />
              </svg>
            </div>
            <div className={styles.brandTexts}>
              <h1 className={styles.appTitle}>ANALYTICS REPORT</h1>
              <span className={styles.appSubTitle}>
                AI Reinforcement Learning Synthesis
              </span>
            </div>
          </div>

                    <div className={styles.modelStatusBadge}>
            <span className={styles.pulseDot} aria-hidden="true" />
            <span>
              {meta
                ? `${meta.status} · ${meta.total_timesteps.toLocaleString("id-ID")} TIMESTEPS`
                : "MENGGUNAKAN DATA CONTOH"}
            </span>
          </div>
        </div>{/* ← close barLeft here */}

        <div className={styles.barRight}>
          {draft && (
            <div className={styles.draftPill}>
              <span className={styles.draftPillDot}>●</span>
              <span>{draft.title}</span>
            </div>
          )}
          <span className={styles.timestampBadge}>Generated: {generatedDate}</span>

          <button
            type="button"
            className={styles.primaryActionButton}
            onClick={handleBackToDashboard}
          >
            <span>Kembali ke Dashboard</span>
            <span className={styles.actionArrow}>→</span>
          </button>
        </div>
      </header>

      {isError && (
        <div className={styles.cardContainer}>
          <p className={styles.cardDescription}>
            Gagal memuat hasil RL{error?.message ? ` — ${error.message}` : ""}.
            Menampilkan data contoh sementara.
          </p>
        </div>
      )}

      {/* 2. DYNAMIC SCENARIO DECK (TAB TITLE MENGIKUTI SCENARIO YANG TERSEDIA) */}
      <section className={styles.scenarioDeckWrapper}>
        <div className={styles.scenarioDeck}>
          {resolvedScenarios.map((sc, idx) => {
            const isActive = sc.id === activeTab;
            const numberFormatted = String(idx + 1).padStart(2, "0");

            return (
              <button
                key={sc.id}
                type="button"
                className={`${styles.scenarioCard} ${
                  isActive ? styles.scenarioCardActive : ""
                }`}
                onClick={() => handleTabClick(sc.id)}
                aria-pressed={isActive}
              >
                <div className={styles.cardTopRow}>
                  <div className={styles.cardRankGroup}>
                    <span
                      className={`${styles.cardNumberBadge} ${
                        isActive ? styles.cardNumberActive : ""
                      }`}
                    >
                      {numberFormatted}
                    </span>
                    <h2 className={styles.cardScenarioTitle} title={sc.title}>
                      {sc.title}
                    </h2>
                  </div>
                    {rlScenarios[idx]?.recommended && (
                      <span className={styles.activePill}>REKOMENDASI</span>
                    )}
                    {isActive && <span className={styles.activePill}>ACTIVE</span>}
                </div>

                <p className={styles.cardDescription}>{sc.subtitle}</p>

                <div className={styles.cardConstraintsRow}>
                  <span
                    className={`${styles.constraintTag} ${
                      sc.constraints.hiring ? styles.tagPositive : styles.tagNeutral
                    }`}
                  >
                    {sc.constraints.hiring ? "✓" : "✕"} Hiring
                  </span>
                  <span
                    className={`${styles.constraintTag} ${
                      sc.constraints.fireMut ? styles.tagPositive : styles.tagNeutral
                    }`}
                  >
                    {sc.constraints.fireMut ? "✓" : "✕"} Fire/Mut
                  </span>
                  <span
                    className={`${styles.constraintTag} ${
                      sc.constraints.automation ? styles.tagPositive : styles.tagNeutral
                    }`}
                  >
                    {sc.constraints.automation ? "✓" : "✕"} Automasi
                  </span>
                  <span className={styles.budgetChip}>
                    {rlScenarios[idx]
                      ? `${formatRupiah(rlScenarios[idx].constraints.capex_used_rp)} / ${sc.constraints.budgetLabel}`
                      : sc.constraints.budgetLabel}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {/* 3. MAIN DASHBOARD CONTENT */}
      <main className={styles.contentGrid}>
        {/* LEFT COLUMN: HERO KPIS + CHARTS + STATIONS + GRAPH + AI IMPACT RECS */}
        <section className={styles.analyticsMain}>
          {/* A. 3 KPI CARDS */}
          <div className={styles.kpiTilesRow}>
            {/* KPI 1: Throughput */}
            <div className={styles.kpiTile}>
              <div className={styles.kpiTop}>
                <div className={styles.kpiNameGroup}>
                  <div className={styles.kpiIconBox}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#801426" strokeWidth="2.4">
                      <path d="M18 15l-6-6-6 6" />
                    </svg>
                  </div>
                  <span className={styles.kpiName}>THROUGHPUT</span>
                </div>
                <span
                  className={
                    currentScenario.metrics.throughput.diffType === "positive"
                      ? styles.deltaBadgePositive
                      : styles.deltaBadgeNegative
                  }
                >
                  {currentScenario.metrics.throughput.diff}
                </span>
              </div>

              <div className={styles.kpiNumbers}>
                <div className={styles.valBlock}>
                  <span className={styles.valTag}>SEBELUM</span>
                  <span className={styles.valTextMuted}>
                    {currentScenario.metrics.throughput.before}
                  </span>
                </div>
                <div className={styles.valSeparator}>→</div>
                <div className={styles.valBlock}>
                  <span className={styles.valTag}>SESUDAH</span>
                  <span className={styles.valTextHighlight}>
                    {currentScenario.metrics.throughput.after}
                  </span>
                </div>
              </div>

              <div className={styles.kpiProgressBar}>
                <div
                  className={styles.kpiProgressFill}
                  style={{
                    width:
                      currentScenario.tabNumber === 3
                        ? "96%"
                        : currentScenario.tabNumber === 2
                        ? "78%"
                        : "60%",
                  }}
                />
              </div>
            </div>

            {/* KPI 2: Human Error Rate */}
            <div className={styles.kpiTile}>
              <div className={styles.kpiTop}>
                <div className={styles.kpiNameGroup}>
                  <div className={`${styles.kpiIconBox} ${styles.kpiIconAmber}`}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#b8740c" strokeWidth="2.4">
                      <path d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                    </svg>
                  </div>
                  <span className={styles.kpiName}>HUMAN ERROR RATE</span>
                </div>
                <span
                  className={
                    currentScenario.metrics.errorRate.diffType === "positive"
                      ? styles.deltaBadgePositive
                      : styles.deltaBadgeNegative
                  }
                >
                  {currentScenario.metrics.errorRate.diff}
                </span>
              </div>

              <div className={styles.kpiNumbers}>
                <div className={styles.valBlock}>
                  <span className={styles.valTag}>SEBELUM</span>
                  <span className={styles.valTextMuted}>
                    {currentScenario.metrics.errorRate.before}
                  </span>
                </div>
                <div className={styles.valSeparator}>→</div>
                <div className={styles.valBlock}>
                  <span className={styles.valTag}>SESUDAH</span>
                  <span className={styles.valTextHighlight}>
                    {currentScenario.metrics.errorRate.after}
                  </span>
                </div>
              </div>

              <div className={styles.kpiProgressBar}>
                <div
                  className={`${styles.kpiProgressFill} ${styles.progressAmber}`}
                  style={{
                    width:
                      currentScenario.tabNumber === 3
                        ? "15%"
                        : currentScenario.tabNumber === 2
                        ? "38%"
                        : "65%",
                  }}
                />
              </div>
            </div>

            {/* KPI 3: Total Op. Cost */}
            <div className={styles.kpiTile}>
              <div className={styles.kpiTop}>
                <div className={styles.kpiNameGroup}>
                  <div className={styles.kpiIconBox}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#801426" strokeWidth="2.4">
                      <line x1="12" y1="1" x2="12" y2="23" />
                      <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
                    </svg>
                  </div>
                  <span className={styles.kpiName}>TOTAL OP. COST</span>
                </div>
                <span
                  className={
                    currentScenario.metrics.opCost.diffType === "positive"
                      ? styles.deltaBadgePositive
                      : styles.deltaBadgeNegative
                  }
                >
                  {currentScenario.metrics.opCost.diff}
                </span>
              </div>

              <div className={styles.kpiNumbers}>
                <div className={styles.valBlock}>
                  <span className={styles.valTag}>SEBELUM</span>
                  <span className={styles.valTextMuted}>
                    {currentScenario.metrics.opCost.before}
                  </span>
                </div>
                <div className={styles.valSeparator}>→</div>
                <div className={styles.valBlock}>
                  <span className={styles.valTag}>SESUDAH</span>
                  <span className={styles.valTextHighlight}>
                    {currentScenario.metrics.opCost.after}
                  </span>
                </div>
              </div>

              <div className={styles.kpiProgressBar}>
                <div
                  className={styles.kpiProgressFill}
                  style={{
                    width:
                      currentScenario.tabNumber === 3
                        ? "88%"
                        : currentScenario.tabNumber === 2
                        ? "70%"
                        : "45%",
                  }}
                />
              </div>
            </div>
          </div>

                    {currentRlScenario && (
            <div className={styles.cardContainer}>
              <div className={styles.cardHeader}>
                <div className={styles.cardHeaderTitle}>
                  <span className={styles.sectionIcon}>🧠</span>
                  <span>HUMAN FACTORS &amp; REWARD WEIGHTS</span>
                </div>
                <span className={styles.cardMetaCount}>
                  Episode reward {currentRlScenario.episode_reward}
                </span>
              </div>

              <div className={styles.kpiTilesRow}>
                <div className={styles.kpiTile}>
                  <div className={styles.kpiTop}>
                    <span className={styles.kpiName}>MEAN FATIGUE</span>
                  </div>
                  <div className={styles.kpiNumbers}>
                    <span className={styles.valTextHighlight}>
                      {(currentRlScenario.metrics.mean_fatigue.after * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className={styles.kpiProgressBar}>
                    <div
                      className={styles.kpiProgressFill}
                      style={{
                        width: `${currentRlScenario.metrics.mean_fatigue.after * 100}%`,
                      }}
                    />
                  </div>
                </div>

                <div className={styles.kpiTile}>
                  <div className={styles.kpiTop}>
                    <span className={styles.kpiName}>MAX FATIGUE</span>
                  </div>
                  <div className={styles.kpiNumbers}>
                    <span className={styles.valTextHighlight}>
                      {(currentRlScenario.metrics.max_fatigue.after * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className={styles.kpiProgressBar}>
                    <div
                      className={`${styles.kpiProgressFill} ${styles.progressAmber}`}
                      style={{
                        width: `${currentRlScenario.metrics.max_fatigue.after * 100}%`,
                      }}
                    />
                  </div>
                </div>

                <div className={styles.kpiTile}>
                  <div className={styles.kpiTop}>
                    <span className={styles.kpiName}>COST / ITEM</span>
                    <span
                      className={
                        currentRlScenario.metrics.cost_per_item_rp.is_improvement
                          ? styles.deltaBadgePositive
                          : styles.deltaBadgeNegative
                      }
                    >
                      {currentRlScenario.metrics.cost_per_item_rp.delta_pct?.toFixed(1)}%
                    </span>
                  </div>
                  <div className={styles.kpiNumbers}>
                    <div className={styles.valBlock}>
                      <span className={styles.valTag}>SEBELUM</span>
                      <span className={styles.valTextMuted}>
                        {formatRupiah(currentRlScenario.metrics.cost_per_item_rp.before ?? 0)}
                      </span>
                    </div>
                    <div className={styles.valSeparator}>→</div>
                    <div className={styles.valBlock}>
                      <span className={styles.valTag}>SESUDAH</span>
                      <span className={styles.valTextHighlight}>
                        {formatRupiah(currentRlScenario.metrics.cost_per_item_rp.after)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <div className={styles.cardConstraintsRow}>
                {Object.entries(currentRlScenario.reward_weights).map(([key, value]) => (
                  <span key={key} className={styles.constraintTag}>
                    w·{key} {value.toFixed(2)}
                  </span>
                ))}
                <span className={styles.budgetChip}>
                  {currentRlScenario.metrics.bottleneck_count.after} bottleneck
                </span>
                {currentRlScenario.factory_flow_optimal.residual_bottleneck && (
                  <span className={styles.budgetChip}>
                    Residual:{" "}
                    {formatStationLabel(
                      currentRlScenario.factory_flow_optimal.residual_bottleneck
                    )}
                  </span>
                )}
              </div>
            </div>
          )}

          {currentRlScenario && (
            <div className={styles.cardContainer}>
              <div className={styles.cardHeader}>
                <div className={styles.cardHeaderTitle}>
                  <span className={styles.sectionIcon}>🔄</span>
                  <span>SIMULASI REALOKASI — RL POLICY</span>
                </div>
                <span className={styles.cardMetaCount}>
                  {currentRlScenario.factory_flow_optimal.reallocation_moves.length} rotasi ·{" "}
                  {currentRlScenario.factory_flow_optimal.asset_upgrades.length} otomasi ·{" "}
                  {currentRlScenario.factory_flow_optimal.new_hires.length} rekrut
                </span>
              </div>

              <RlFlowSimulation scenario={currentRlScenario} />
            </div>
          )}

          {/* B. CHARTS ROW */}
          <div className={styles.chartsGrid}>
            <ThroughputShiftChart
              labels={currentScenario.shiftChart.labels}
              before={currentScenario.shiftChart.before}
              after={currentScenario.shiftChart.after}
            />
            <CostBreakdownChart
              categories={currentScenario.costChart.categories}
              before={currentScenario.costChart.before}
              after={currentScenario.costChart.after}
            />
          </div>

          {/* C. STATION STATUS - POST OPTIMIZATION */}
          <div className={styles.cardContainer}>
            <div className={styles.cardHeader}>
              <div className={styles.cardHeaderTitle}>
                <span className={styles.sectionIcon}>⚙️</span>
                <span>STATION STATUS — POST OPTIMIZATION</span>
              </div>
              <span className={styles.cardMetaCount}>
                {currentScenario.stations.length} Stasiun Terpantau
              </span>
            </div>

            <div className={styles.stationsRow}>
              {currentScenario.stations.map((st) => (
                <div key={st.id} className={styles.stationCard} title={st.details || st.name}>
                  <div className={styles.stationIcon}>
                    {st.badgeColor === "amber" && "⚡"}
                    {st.badgeColor === "green" && "✓"}
                    {st.badgeColor === "red" && "⚠️"}
                    {st.badgeColor === "blue" && "🤖"}
                  </div>
                  <div className={styles.stationName}>{st.name}</div>
                  <span
                    className={`${styles.statusBadge} ${
                      styles[`badge_${st.badgeColor}`]
                    }`}
                  >
                    {st.status}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* D. GRAF ALUR PRODUKSI — TEROPTIMASI */}
          <div className={styles.cardContainer}>
            <div className={styles.accordionHeader}>
              <div className={styles.accordionLeft}>
                <span className={styles.targetIcon}>🎯</span>
                <div>
                  <div className={styles.accordionTitle}>
                    GRAF ALUR PRODUKSI — TEROPTIMASI
                  </div>
                  <div className={styles.accordionSub}>
                    {currentScenario.graphSubtitle}
                  </div>
                </div>
              </div>

              <div className={styles.graphButtonsGroup}>
                <button
                  type="button"
                  className={styles.toggleBtn}
                  onClick={() => setShowGraph((prev) => !prev)}
                  title="Preview mini diagram"
                >
                  {showGraph ? "Tutup ⌃" : "Preview ⌄"}
                </button>
                
                {/* --- PEMBARUAN 2: TOMBOL MENUJU DIGITAL TWIN --- */}
                <button
                  type="button"
                  className={styles.openCanvasBtn}
                  onClick={handleGoToDigitalTwin}
                  title="Buka Digital Twin berdasarkan skenario ini"
                >
                  <span>Tampilkan graf</span>
                  <span className={styles.arrowIcon}>↗</span>
                </button>
              </div>
            </div>

            {showGraph && (
              <ProductionFlowGraphPreview
                nodes={currentScenario.flowGraph.nodes}
                edges={currentScenario.flowGraph.edges}
              />
            )}
          </div>

          {/* E. AI RECOMMENDATIONS — RANKED BY IMPACT */}
          <div className={styles.cardContainer}>
            <div className={styles.cardHeader}>
              <div className={styles.cardHeaderTitle}>
                <span className={styles.sectionIcon}>💡</span>
                <span>AI RECOMMENDATIONS — RANKED BY IMPACT</span>
              </div>
              <span className={styles.cardMetaCount}>Prioritas Utama</span>
            </div>

            <div className={styles.recsList}>
              {currentScenario.recommendations.map((rec) => (
                <div key={rec.id} className={styles.recItem}>
                  <div className={styles.recRankGroup}>
                    <span className={styles.recNumber}>{rec.rank}</span>
                    <span className={styles.priorityPill}>{rec.priority}</span>
                  </div>
                  <p className={styles.recDetailText}>{rec.text}</p>
                  <span className={styles.gainPill}>{rec.impactBadge}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* RIGHT COLUMN: AI CHATBOT / WHAT-IF SIMULATOR */}
        <section className={styles.analyticsSidebar}>
          <WhatIfPlayground
            scenarioNumber={currentScenario.tabNumber}
            scenarioTitle={currentScenario.title}
            scenarioData={currentScenario}
            quickScenarios={currentScenario.quickScenarios}
          />
        </section>
      </main>
    </div>
  );
}

export default ExecutionPage;