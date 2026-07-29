import { useMemo } from "react";
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

  const searchQuery = useDigitalTwinStore((s) => s.searchQuery);
  const selectedWorkflowStep = useDigitalTwinStore((s) => s.selectedWorkflowStep);
  const selectedCategory = useDigitalTwinStore((s) => s.selectedCategory);
  const automationFilter = useDigitalTwinStore((s) => s.automationFilter);

  // Peta worker_id -> current_station, dipakai untuk filter worker by tahap
  // (worker tidak punya field workflow_step langsung, hanya lewat posisi live).
  const workerStationMap = useMemo(() => {
    const map = new Map<string, string>();
    data?.factory_flow_rightnow.staff_current_positions.forEach((pos) => {
      map.set(pos.worker_id, pos.current_station);
    });
    return map;
  }, [data]);

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
      const matchesSearch = searchQuery
        ? asset.asset_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          asset.asset_id.toLowerCase().includes(searchQuery.toLowerCase())
        : true;
      return matchesStep && matchesCategory && matchesAutomation && matchesSearch;
    });
  }, [data, selectedWorkflowStep, selectedCategory, automationFilter, searchQuery]);

  const filteredWorkers = useMemo(() => {
    if (!data) return [];
    return data.workers.filter((worker) => {
      const matchesStep = selectedWorkflowStep
        ? workerStationMap.get(worker.worker_id) === selectedWorkflowStep
        : true;
      const matchesSearch = searchQuery
        ? worker.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          worker.worker_id.toLowerCase().includes(searchQuery.toLowerCase())
        : true;
      return matchesStep && matchesSearch;
    });
  }, [data, selectedWorkflowStep, searchQuery, workerStationMap]);

  const filteredJobDesks = useMemo(() => {
    if (!data) return [];
    return data.job_desks.filter((job) => {
      const matchesStep = selectedWorkflowStep
        ? job.workflow_step === selectedWorkflowStep
        : true;
      const matchesSearch = searchQuery
        ? job.job_title.toLowerCase().includes(searchQuery.toLowerCase()) ||
          job.job_id.toLowerCase().includes(searchQuery.toLowerCase())
        : true;
      return matchesStep && matchesSearch;
    });
  }, [data, selectedWorkflowStep, searchQuery]);

  const categories = useMemo<AssetCategory[]>(() => {
    if (!data) return [];
    return Array.from(new Set(data.assets.map((a) => a.category)));
  }, [data]);

  // worker_id -> nama, job_id -> judul, dipakai SimulationFlowchart untuk menampilkan
  // label yang bisa dibaca manusia alih-alih worker_id/job_id mentah.
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

      {/* Filter */}
      <FilterBar
        workflowSteps={data.factory_info.workflow_sequence}
        categories={categories}
      />

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

      {/* Assets */}
      <section className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle}>Aset & Mesin</h2>
          <span className={styles.sectionCount}>{filteredAssets.length}</span>
        </div>
        {filteredAssets.length === 0 ? (
          <p className={styles.emptyState}>Tidak ada aset yang cocok dengan filter.</p>
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
          <h2 className={styles.sectionTitle}>Pekerja</h2>
          <span className={styles.sectionCount}>{filteredWorkers.length}</span>
        </div>
        {filteredWorkers.length === 0 ? (
          <p className={styles.emptyState}>Tidak ada pekerja yang cocok dengan filter.</p>
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
          <h2 className={styles.sectionTitle}>Job Desk</h2>
          <span className={styles.sectionCount}>{filteredJobDesks.length}</span>
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