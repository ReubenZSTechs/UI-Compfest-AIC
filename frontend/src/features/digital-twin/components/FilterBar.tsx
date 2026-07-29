import type { AssetCategory } from "../types/digitalTwin.types";
import { formatWorkflowStepLabel } from "../utils/formatMetrics";
import { useDigitalTwinStore, type AutomationFilter } from "../store/digitalTwinStore";
import styles from "./FilterBar.module.css";

interface FilterBarProps {
  workflowSteps: string[];
  categories: AssetCategory[];
}

const AUTOMATION_OPTIONS: { value: AutomationFilter; label: string }[] = [
  { value: "all", label: "Semua" },
  { value: "automated", label: "Otomatis" },
  { value: "manual", label: "Manual" },
];

export function FilterBar({ workflowSteps, categories }: FilterBarProps) {
  const searchQuery = useDigitalTwinStore((s) => s.searchQuery);
  const selectedWorkflowStep = useDigitalTwinStore((s) => s.selectedWorkflowStep);
  const selectedCategory = useDigitalTwinStore((s) => s.selectedCategory);
  const automationFilter = useDigitalTwinStore((s) => s.automationFilter);

  const setSearchQuery = useDigitalTwinStore((s) => s.setSearchQuery);
  const setSelectedWorkflowStep = useDigitalTwinStore((s) => s.setSelectedWorkflowStep);
  const setSelectedCategory = useDigitalTwinStore((s) => s.setSelectedCategory);
  const setAutomationFilter = useDigitalTwinStore((s) => s.setAutomationFilter);
  const resetFilters = useDigitalTwinStore((s) => s.resetFilters);

  const hasActiveFilters =
    searchQuery !== "" ||
    selectedWorkflowStep !== null ||
    selectedCategory !== null ||
    automationFilter !== "all";

  return (
    <div className={styles.bar}>
      <input
        className={styles.search}
        type="text"
        placeholder="Cari nama, ID..."
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
      />

      <select
        className={styles.select}
        value={selectedWorkflowStep ?? ""}
        onChange={(e) => setSelectedWorkflowStep(e.target.value || null)}
      >
        <option value="">Semua Tahap</option>
        {workflowSteps.map((step) => (
          <option key={step} value={step}>
            {formatWorkflowStepLabel(step)}
          </option>
        ))}
      </select>

      <select
        className={styles.select}
        value={selectedCategory ?? ""}
        onChange={(e) =>
          setSelectedCategory((e.target.value || null) as AssetCategory | null)
        }
      >
        <option value="">Semua Kategori</option>
        {categories.map((cat) => (
          <option key={cat} value={cat}>
            {cat.replace(/_/g, " ")}
          </option>
        ))}
      </select>

      <div className={styles.segmented}>
        {AUTOMATION_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            className={`${styles.segmentedBtn} ${
              automationFilter === opt.value ? styles.segmentedBtnActive : ""
            }`}
            onClick={() => setAutomationFilter(opt.value)}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {hasActiveFilters && (
        <button type="button" className={styles.resetBtn} onClick={resetFilters}>
          Reset Filter
        </button>
      )}
    </div>
  );
}