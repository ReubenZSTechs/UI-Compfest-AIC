// frontend/src/features/digital-twin/components/AssetCard.tsx

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

  const isSelected = selectedAssetId === asset.assetId;
  const strainLevel = strainLevelFromIndex(
    asset.environmentalFactors.physicalStrainIndex
  );

  return (
    <button
      type="button"
      className={`${styles.card} ${isSelected ? styles.cardSelected : ""}`}
      onClick={() => selectAsset(asset.assetId)}
      aria-pressed={isSelected}
    >
      {/* Header: automation status + category */}
      <div className={styles.header}>
        <span
          className={`${styles.automationDot} ${
            asset.isAutomated ? styles.dotAutomated : styles.dotManual
          }`}
          aria-hidden="true"
        />
        <span className={styles.category}>
          {asset.category.replace(/_/g, " ")}
        </span>
        <span className={styles.stepTag}>
          {formatWorkflowStepLabel(asset.workflowStep)}
        </span>
      </div>

      {/* Title & ID */}
      <div className={styles.titleBlock}>
        <h3 className={styles.title}>{asset.assetName}</h3>
        <span className={styles.assetId}>{asset.assetId}</span>
      </div>

      {/* Readout: throughput & cost */}
      <div className={styles.readoutGrid}>
        <div className={styles.readout}>
          <span className={styles.readoutLabel}>Kapasitas</span>
          <span className={styles.readoutValue}>
            {formatCapacity(asset.baseThroughputCapacity)}
          </span>
        </div>
        <div className={styles.readout}>
          <span className={styles.readoutLabel}>Biaya Operasional</span>
          <span className={styles.readoutValue}>
            {formatCostPerHour(asset.operationalCostPerHour)}
          </span>
        </div>
      </div>

      {/* Signature element: strain meter (segmented bar ala VU-meter) */}
      <div className={styles.meterBlock}>
        <div className={styles.meterLabelRow}>
          <span className={styles.readoutLabel}>Beban Fisik</span>
          <span className={`${styles.meterValue} ${styles[`strain-${strainLevel}`]}`}>
            {(asset.environmentalFactors.physicalStrainIndex * 100).toFixed(0)}%
          </span>
        </div>
        <div
          className={styles.meter}
          role="meter"
          aria-valuenow={asset.environmentalFactors.physicalStrainIndex}
          aria-valuemin={0}
          aria-valuemax={1}
        >
          {Array.from({ length: 10 }).map((_, i) => {
            const segmentThreshold = (i + 1) / 10;
            const filled =
              asset.environmentalFactors.physicalStrainIndex >= segmentThreshold - 0.05;
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
        <span>{asset.environmentalFactors.noiseLevelDb} dB</span>
        <span className={styles.envDivider}>·</span>
        <span>
          Getaran: {VIBRATION_LABEL[asset.environmentalFactors.vibrationHazardLevel]}
        </span>
      </div>
    </button>
  );
}