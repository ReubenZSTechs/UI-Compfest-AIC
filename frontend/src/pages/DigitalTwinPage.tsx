import { useState, useMemo } from "react";
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
  const { data, isLoading, error } = useDigitalTwin();

  // State pencarian terpisah untuk masing-masing seksi
  const [assetSearchQuery, setAssetSearchQuery] = useState("");
  const [workerSearchQuery, setWorkerSearchQuery] = useState("");
  const [jobDeskSearchQuery, setJobDeskSearchQuery] = useState("");

  const selectedWorkflowStep = useDigitalTwinStore((s) => s.selectedWorkflowStep);
  const selectedCategory = useDigitalTwinStore((s) => s.selectedCategory);
  const automationFilter = useDigitalTwinStore((s) => s.automationFilter);

  // Peta worker_id -> current_station
  const workerStationMap = useMemo(() => {
    const map = new Map<string, string>();
    data?.factory_flow_rightnow.staff_current_positions.forEach((pos) => {
      map.set(pos.worker_id, pos.current_station);
    });
    return map;
  }, [data]);

  // Filter Aset & Mesin (menggunakan assetSearchQuery)
  const filteredAssets = useMemo(() => {
    if (!data) return [];
    return data.assets.filter((asset) => {
      const matchesStep = selectedWorkflowStep
        ? asset.workflow_step === selectedWorkflowStep
        : true;
      const matchesCategory = selectedCategory
        ? asset.category === selectedCategory
        : true;
      const matchesAutomation =
        automationFilter === "all"
          ? true
          : automationFilter === "automated"
            ? asset.is_automated
            : !asset.is_automated;
      const matchesSearch = assetSearchQuery
        ? asset.asset_name.toLowerCase().includes(assetSearchQuery.toLowerCase()) ||
          asset.asset_id.toLowerCase().includes(assetSearchQuery.toLowerCase())
        : true;
      return matchesStep && matchesCategory && matchesAutomation && matchesSearch;
    });
  }, [data, selectedWorkflowStep, selectedCategory, automationFilter, assetSearchQuery]);

  // Filter Pekerja (menggunakan workerSearchQuery)
  const filteredWorkers = useMemo(() => {
    if (!data) return [];
    return data.workers.filter((worker) => {
      const matchesStep = selectedWorkflowStep
        ? workerStationMap.get(worker.worker_id) === selectedWorkflowStep
        : true;
      const matchesSearch = workerSearchQuery
        ? worker.name.toLowerCase().includes(workerSearchQuery.toLowerCase()) ||
          worker.worker_id.toLowerCase().includes(workerSearchQuery.toLowerCase())
        : true;
      return matchesStep && matchesSearch;
    });
  }, [data, selectedWorkflowStep, workerSearchQuery, workerStationMap]);

  // Filter Job Desk (menggunakan jobDeskSearchQuery)
  const filteredJobDesks = useMemo(() => {
    if (!data) return [];
    return data.job_desks.filter((job) => {
      const matchesStep = selectedWorkflowStep
        ? job.workflow_step === selectedWorkflowStep
        : true;
      const matchesSearch = jobDeskSearchQuery
        ? job.job_title.toLowerCase().includes(jobDeskSearchQuery.toLowerCase()) ||
          job.job_id.toLowerCase().includes(jobDeskSearchQuery.toLowerCase())
        : true;
      return matchesStep && matchesSearch;
    });
  }, [data, selectedWorkflowStep, jobDeskSearchQuery]);

  const categories = useMemo<AssetCategory[]>(() => {
    if (!data) return [];
    return Array.from(new Set(data.assets.map((a) => a.category)));
  }, [data]);

  const workerNames = useMemo(() => {
    if (!data) return {};
    return Object.fromEntries(data.workers.map((w) => [w.worker_id, w.name]));
  }, [data]);

  const jobTitles = useMemo(() => {
    if (!data) return {};
    return Object.fromEntries(data.job_desks.map((j) => [j.job_id, j.job_title]));
  }, [data]);

  if (isLoading) {
    return <div className={styles.stateMessage}>Memuat digital twin...</div>;
  }

  if (error) {
    return (
      <div className={`${styles.stateMessage} ${styles.stateError}`}>
        Gagal memuat data: {error.message}
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className={styles.page}>
      {/* Header */}
      <header className={styles.header}>
        <div>
          <span className={styles.eyebrow}>Digital Twin</span>
          <h1 className={styles.factoryName}>{data.factory_info.factory_name}</h1>
          <span className={styles.factoryId}>{data.factory_info.factory_id}</span>
        </div>
        <div className={styles.snapshotInfo}>
          <span className={styles.readoutLabel}>Snapshot Terakhir</span>
          <time className={styles.snapshotTime}>
            {new Date(data.factory_flow_rightnow.snapshot_timestamp).toLocaleString(
              "id-ID",
              { dateStyle: "medium", timeStyle: "short" }
            )}
          </time>
        </div>
      </header>

      {/* Live Simulation */}
      <section className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle}>Live Simulation</h2>
          <SimulationControls />
        </div>
        <div className={simulationSectionStyles.simulationGrid}>
          <SimulationFlowchart workerNames={workerNames} jobTitles={jobTitles} />
          <SimulationSummaryPanel />
        </div>
      </section>

      {/* Filter Bar untuk Tahap Workflow & Otomasi */}
      <FilterBar
        workflowSteps={data.factory_info.workflow_sequence}
        categories={categories}
      />

      {/* Assets & Mesin */}
      <section className={styles.section}>
        <div className={styles.sectionHeader}>
          <div className={styles.sectionTitleGroup}>
            <h2 className={styles.sectionTitle}>Aset & Mesin</h2>
            <span className={styles.sectionCount}>{filteredAssets.length}</span>
          </div>
          {/* SearchBar Khusus Aset */}
          <input
            type="text"
            placeholder="Cari aset atau ID..."
            value={assetSearchQuery}
            onChange={(e) => setAssetSearchQuery(e.target.value)}
            className={styles.sectionSearchInput}
          />
        </div>
        {filteredAssets.length === 0 ? (
          <p className={styles.emptyState}>Tidak ada aset yang cocok dengan pencarian/filter.</p>
        ) : (
          <div className={styles.assetGrid}>
            {filteredAssets.map((asset) => (
              <AssetCard key={asset.asset_id} asset={asset} />
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
          {/* SearchBar Khusus Pekerja */}
          <input
            type="text"
            placeholder="Cari nama atau ID pekerja..."
            value={workerSearchQuery}
            onChange={(e) => setWorkerSearchQuery(e.target.value)}
            className={styles.sectionSearchInput}
          />
        </div>
        {filteredWorkers.length === 0 ? (
          <p className={styles.emptyState}>Tidak ada pekerja yang cocok dengan pencarian/filter.</p>
        ) : (
          <div className={styles.workerGrid}>
            {filteredWorkers.map((worker) => (
              <WorkerCard key={worker.worker_id} worker={worker} />
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
          {/* SearchBar Khusus Job Desk */}
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
          evaluations={data.llm_compatibility_and_evaluations}
        />
      </section>
    </div>
  );
}