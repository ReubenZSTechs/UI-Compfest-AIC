import type { Asset } from "../types/digitalTwin.types";
import {
  formatCostPerHour,
  formatCapacity,
  formatWorkflowStepLabel,
  strainLevelFromIndex,
  VIBRATION_LABEL,
} from "../utils/formatMetrics";
import { useDigitalTwinStore } from "../store/digitalTwinStore";
import styles from "./AssetCard.module.css";

interface AssetCardProps {
  asset: Asset;
}

export function AssetCard({ asset }: AssetCardProps) {
  const selectedAssetId = useDigitalTwinStore((s) => s.selectedAssetId);
  const selectAsset = useDigitalTwinStore((s) => s.selectAsset);

  const isSelected = selectedAssetId === asset.asset_id;
  const strainLevel = strainLevelFromIndex(
    asset.environmental_factors.physical_strain_index
  );

  return (
    <button
      type="button"
      className={`${styles.card} ${isSelected ? styles.cardSelected : ""}`}
      onClick={() => selectAsset(asset.asset_id)}
      aria-pressed={isSelected}
    >
      {/* Header: automation status + category */}
      <div className={styles.header}>
        <span
          className={`${styles.automationDot} ${
            asset.is_automated ? styles.dotAutomated : styles.dotManual
          }`}
          aria-hidden="true"
        />
        <span className={styles.category}>
          {asset.category.replace(/_/g, " ")}
        </span>
        <span className={styles.stepTag}>
          {formatWorkflowStepLabel(asset.workflow_step)}
        </span>
      </div>

      {/* Title & ID */}
      <div className={styles.titleBlock}>
        <h3 className={styles.title}>{asset.asset_name}</h3>
        <span className={styles.assetId}>{asset.asset_id}</span>
      </div>

      {/* Readout: throughput & cost */}
      <div className={styles.readoutGrid}>
        <div className={styles.readout}>
          <span className={styles.readoutLabel}>Kapasitas</span>
          <span className={styles.readoutValue}>
            {formatCapacity(asset.base_throughput_capacity)}
          </span>
        </div>
        <div className={styles.readout}>
          <span className={styles.readoutLabel}>Biaya Operasional</span>
          <span className={styles.readoutValue}>
            {formatCostPerHour(asset.operational_cost_per_hour)}
          </span>
        </div>
      </div>

      {/* Signature element: strain meter (segmented bar ala VU-meter) */}
      <div className={styles.meterBlock}>
        <div className={styles.meterLabelRow}>
          <span className={styles.readoutLabel}>Beban Fisik</span>
          <span className={`${styles.meterValue} ${styles[`strain-${strainLevel}`]}`}>
            {(asset.environmental_factors.physical_strain_index * 100).toFixed(0)}%
          </span>
        </div>
        <div className={styles.meter} role="meter"
          aria-valuenow={asset.environmental_factors.physical_strain_index}
          aria-valuemin={0}
          aria-valuemax={1}
        >
          {Array.from({ length: 10 }).map((_, i) => {
            const segmentThreshold = (i + 1) / 10;
            const filled =
              asset.environmental_factors.physical_strain_index >= segmentThreshold - 0.05;
            return (
              <span
                key={i}
                className={`${styles.segment} ${
                  filled ? styles[`segment-${strainLevel}`] : ""
                }`}
              />
            );
          })}
        </div>
      </div>

      {/* Environmental footer */}
      <div className={styles.envRow}>
        <span>{asset.environmental_factors.noise_level_db} dB</span>
        <span className={styles.envDivider}>·</span>
        <span>
          Getaran: {VIBRATION_LABEL[asset.environmental_factors.vibration_hazard_level]}
        </span>
      </div>
    </button>
  );
}