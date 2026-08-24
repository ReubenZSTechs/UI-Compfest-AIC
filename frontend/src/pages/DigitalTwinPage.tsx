// frontend/src/pages/DigitalTwinPage.tsx

import { useState, useMemo, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useDigitalTwin } from "@/features/digital-twin/hooks/useDigitalTwin";
import { useDigitalTwinStore } from "@/features/digital-twin/store/digitalTwinStore";
import { AssetCard } from "@/features/digital-twin/components/AssetCard";
import { WorkerCard } from "@/features/digital-twin/components/WorkerCard";
import { JobDeskTable } from "@/features/digital-twin/components/JobDeskTable";
import { CompatibilityMatrix } from "@/features/digital-twin/components/CompatibilityMatrix";
import { FilterBar } from "@/features/digital-twin/components/FilterBar";
import type { AssetCategory } from "@/features/digital-twin/types/digitalTwin.types";
import { SimulationControls } from "@/features/simulation/components/SimulationControls";
import { SimulationFlowchart } from "@/features/simulation/components/SimulationFlowchart";
import { SimulationSummaryPanel } from "@/features/simulation/components/SimulationSummaryPanel";
import simulationSectionStyles from "@/features/simulation/components/SimulationSection.module.css";
import "@/features/simulation/styles/tokens.css";
import styles from "./DigitalTwinPage.module.css";

export function DigitalTwinPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const factoryId =
    searchParams.get("factory_id") ||
    searchParams.get("factoryId") ||
    searchParams.get("simulation_id") ||
    searchParams.get("job_id") ||
    undefined;

  // --- PEMBARUAN 1: Deteksi parameter mock=success atau mock=true di URL ---
  const isMockMode = 
    searchParams.get("mock") === "success" || 
    searchParams.get("mock") === "true";
  // -------------------------------------------------------------------------

  const { data, isLoading, isFetched, error } = useDigitalTwin(factoryId);

  // Validasi keberadaan data hasil parsing
  const hasParsedData = useMemo(() => {
    if (!data) return false;
    const hasFactory = Boolean(
      data.factoryInfo?.factoryId || data.factoryInfo?.factoryName
    );
    const hasDesks = Array.isArray(data.jobDesks) && data.jobDesks.length > 0;
    const hasWorkers = Array.isArray(data.workers) && data.workers.length > 0;
    const hasAssets = Array.isArray(data.assets) && data.assets.length > 0;
    return hasFactory || hasDesks || hasWorkers || hasAssets;
  }, [data]);

  // Route Guard: Alihkan ke halaman document parser hanya jika proses fetch selesai & data memang kosong/error
  useEffect(() => {
    // 1. Jika URL tidak memiliki factoryId, langsung redirect
    if (!factoryId) {
      alert("Hasil parsing belum tersedia. Silakan unggah dan proses dokumen terlebih dahulu.");
      navigate("/document-parser", { replace: true });
      return;
    }

    // 2. Tunggu hingga pemanggilan API selesai (isFetched === true dan !isLoading)
    if (isFetched && !isLoading) {
      if (error || !hasParsedData) {
        alert("Hasil parsing belum tersedia. Silakan unggah dan proses dokumen terlebih dahulu.");
        navigate("/document-parser", { replace: true });
      }
    }
  }, [isFetched, isLoading, error, hasParsedData, factoryId, navigate]);

  // Fungsi navigasi ke halaman rekomendasi
  const handleGoToRecommendations = () => {
    if (factoryId) {
      navigate(`/project/${encodeURIComponent(factoryId)}/recommendations`);
    } else {
      alert("ID Factory tidak ditemukan untuk melihat rekomendasi.");
    }
  };

  // State pencarian terpisah untuk masing-masing seksi
  const [assetSearchQuery, setAssetSearchQuery] = useState("");
  const [workerSearchQuery, setWorkerSearchQuery] = useState("");
  const [jobDeskSearchQuery, setJobDeskSearchQuery] = useState("");

  const selectedWorkflowStep = useDigitalTwinStore((s) => s.selectedWorkflowStep);
  const selectedCategory = useDigitalTwinStore((s) => s.selectedCategory);
  const automationFilter = useDigitalTwinStore((s) => s.automationFilter);

  // Peta workerId -> currentStation (null-safe)
  const workerStationMap = useMemo(() => {
    const map = new Map<string, string>();
    data?.factoryFlowRightnow?.staffCurrentPositions?.forEach((pos) => {
      if (pos?.workerId) {
        map.set(pos.workerId, pos.currentStation ?? "");
      }
    });
    return map;
  }, [data]);

  // Filter Aset & Mesin
  const filteredAssets = useMemo(() => {
    if (!data?.assets) return [];
    return data.assets.filter((asset) => {
      if (!asset) return false;
      const matchesStep = selectedWorkflowStep
        ? asset.workflowStep === selectedWorkflowStep
        : true;
      const matchesCategory = selectedCategory
        ? asset.category === selectedCategory
        : true;
      const matchesAutomation =
        automationFilter === "all"
          ? true
          : automationFilter === "automated"
            ? asset.isAutomated
            : !asset.isAutomated;

      const query = assetSearchQuery.toLowerCase();
      const matchesSearch = assetSearchQuery
        ? (asset.assetName?.toLowerCase().includes(query) ?? false) ||
          (asset.assetId?.toLowerCase().includes(query) ?? false)
        : true;

      return matchesStep && matchesCategory && matchesAutomation && matchesSearch;
    });
  }, [data, selectedWorkflowStep, selectedCategory, automationFilter, assetSearchQuery]);

  // Filter Pekerja
  const filteredWorkers = useMemo(() => {
    if (!data?.workers) return [];
    return data.workers.filter((worker) => {
      if (!worker) return false;
      const matchesStep = selectedWorkflowStep
        ? workerStationMap.get(worker.workerId) === selectedWorkflowStep
        : true;

      const query = workerSearchQuery.toLowerCase();
      const matchesSearch = workerSearchQuery
        ? (worker.name?.toLowerCase().includes(query) ?? false) ||
          (worker.workerId?.toLowerCase().includes(query) ?? false)
        : true;

      return matchesStep && matchesSearch;
    });
  }, [data, selectedWorkflowStep, workerSearchQuery, workerStationMap]);

  // Filter Job Desk
  const filteredJobDesks = useMemo(() => {
    if (!data?.jobDesks) return [];
    return data.jobDesks.filter((job) => {
      if (!job) return false;
      const matchesStep = selectedWorkflowStep
        ? job.workflowStep === selectedWorkflowStep
        : true;

      const query = jobDeskSearchQuery.toLowerCase();
      const matchesSearch = jobDeskSearchQuery
        ? (job.jobTitle?.toLowerCase().includes(query) ?? false) ||
          (job.jobId?.toLowerCase().includes(query) ?? false)
        : true;

      return matchesStep && matchesSearch;
    });
  }, [data, selectedWorkflowStep, jobDeskSearchQuery]);

  const categories = useMemo<AssetCategory[]>(() => {
    if (!data?.assets) return [];
    return Array.from(new Set(data.assets.map((a) => a?.category).filter(Boolean)));
  }, [data]);

  const workerNames = useMemo(() => {
    if (!data?.workers) return {};
    return Object.fromEntries(
      data.workers
        .filter((w) => w?.workerId)
        .map((w) => [w.workerId, w.name ?? w.workerId])
    );
  }, [data]);

  const jobTitles = useMemo(() => {
    if (!data?.jobDesks) return {};
    return Object.fromEntries(
      data.jobDesks
        .filter((j) => j?.jobId)
        .map((j) => [j.jobId, j.jobTitle ?? j.jobId])
    );
  }, [data]);

  // Tampilkan loading screen selama request API masih berlangsung
  if (isLoading || !isFetched) {
    return <div className={styles.stateMessage}>Memeriksa ketersediaan data digital twin...</div>;
  }

  // Guard bertahap: tunggu redirect dari useEffect jika data error atau kosong
  if (error || !hasParsedData || !data) {
    return null;
  }

  return (
    <div className={styles.page}>
      {/* Header */}
      <header className={styles.header}>
        <div>
          <span className={styles.eyebrow}>
            Digital Twin {factoryId ? `(ID: ${factoryId})` : ""}
            {/* Indikator UI untuk Mock Mode */}
            {isMockMode && <span style={{ color: "var(--twin-accent-warning)", marginLeft: "8px" }}>[MOCK MODE]</span>}
          </span>
          <h1 className={styles.factoryName}>
            {data.factoryInfo?.factoryName ?? "Digital Twin Pabrik"}
          </h1>
          <span className={styles.factoryId}>
            {data.factoryInfo?.factoryId ?? "-"}
          </span>
        </div>
        
        {/* Kontrol Aksi & Info di sisi Kanan Header */}
        <div className={styles.headerActions}>
          <div className={styles.snapshotInfo}>
            <span className={styles.readoutLabel}>Snapshot Terakhir</span>
            <time className={styles.snapshotTime}>
              {data.factoryFlowRightnow?.snapshotTimestamp
                ? new Date(data.factoryFlowRightnow.snapshotTimestamp).toLocaleString(
                    "id-ID",
                    { dateStyle: "medium", timeStyle: "short" }
                  )
                : "-"}
            </time>
          </div>
          
          <button 
            onClick={handleGoToRecommendations}
            className={styles.recommendationBtn}
          >
            Optimisasi Reinfocement Learning
          </button>
        </div>
      </header>

      {/* Live Simulation */}
      <section className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle}>Live Simulation</h2>
          {/* --- PEMBARUAN 2: Melempar prop isMockMode ke SimulationControls --- */}
          <SimulationControls isMock={isMockMode} />
        </div>
        <div className={simulationSectionStyles.simulationGrid}>
          {/* --- PEMBARUAN 3: Melempar prop isMockMode ke Flowchart dan Summary Panel --- */}
          <SimulationFlowchart 
            workerNames={workerNames} 
            jobTitles={jobTitles} 
            isMock={isMockMode} 
          />
          <SimulationSummaryPanel isMock={isMockMode} />
        </div>
      </section>

      {/* Filter Bar untuk Tahap Workflow & Otomasi */}
      <FilterBar
        workflowSteps={data.factoryInfo?.workflowSequence ?? []}
        categories={categories}
      />

      {/* Assets & Mesin */}
      <section className={styles.section}>
        <div className={styles.sectionHeader}>
          <div className={styles.sectionTitleGroup}>
            <h2 className={styles.sectionTitle}>Aset & Mesin</h2>
            <span className={styles.sectionCount}>{filteredAssets.length}</span>
          </div>
          <input
            type="text"
            placeholder="Cari aset atau ID..."
            value={assetSearchQuery}
            onChange={(e) => setAssetSearchQuery(e.target.value)}
            className={styles.sectionSearchInput}
          />
        </div>
        {filteredAssets.length === 0 ? (
          <p className={styles.emptyState}>
            Tidak ada aset yang cocok dengan pencarian/filter.
          </p>
        ) : (
          <div className={styles.assetGrid}>
            {filteredAssets.map((asset) => (
              <AssetCard key={asset.assetId} asset={asset} />
            ))}
          </div>
        )}
      </section>

      {/* Workers */}
      <section className={styles.section}>
        <div className={styles.sectionHeader}>
          <div className={styles.sectionTitleGroup}>
            <h2 className={styles.sectionTitle}>Pekerja</h2>
            <span className={styles.sectionCount}>{filteredWorkers.length}</span>
          </div>
          <input
            type="text"
            placeholder="Cari nama atau ID pekerja..."
            value={workerSearchQuery}
            onChange={(e) => setWorkerSearchQuery(e.target.value)}
            className={styles.sectionSearchInput}
          />
        </div>
        {filteredWorkers.length === 0 ? (
          <p className={styles.emptyState}>
            Tidak ada pekerja yang cocok dengan pencarian/filter.
          </p>
        ) : (
          <div className={styles.workerGrid}>
            {filteredWorkers.map((worker) => (
              <WorkerCard key={worker.workerId} worker={worker} />
            ))}
          </div>
        )}
      </section>

      {/* Job Desks */}
      <section className={styles.section}>
        <div className={styles.sectionHeader}>
          <div className={styles.sectionTitleGroup}>
            <h2 className={styles.sectionTitle}>Job Desk</h2>
            <span className={styles.sectionCount}>{filteredJobDesks.length}</span>
          </div>
          <input
            type="text"
            placeholder="Cari judul atau ID job desk..."
            value={jobDeskSearchQuery}
            onChange={(e) => setJobDeskSearchQuery(e.target.value)}
            className={styles.sectionSearchInput}
          />
        </div>
        <JobDeskTable jobDesks={filteredJobDesks} />
      </section>

      {/* Compatibility Matrix */}
      <section className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle}>Matriks Kompatibilitas</h2>
        </div>
        <CompatibilityMatrix
          workers={filteredWorkers}
          jobDesks={filteredJobDesks}
          evaluations={data.llmCompatibilityAndEvaluations ?? []}
        />
      </section>
    </div>
  );
}