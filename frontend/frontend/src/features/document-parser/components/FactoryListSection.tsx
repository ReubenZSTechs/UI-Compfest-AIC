import React from 'react';
import type { FactoryItem } from '../hooks/useFactoryList';
import styles from './FactoryListSection.module.css'; // Import terpisah & lokal

interface FactoryListSectionProps {
  factories: FactoryItem[];
  isLoading: boolean;
  error: string | null;
  onSelectFactory: (factoryId: string) => void;
  onAddNewClick: () => void;
  onRetry: () => void;
}

export const FactoryListSection: React.FC<FactoryListSectionProps> = ({
  factories,
  isLoading,
  error,
  onSelectFactory,
  onAddNewClick,
  onRetry,
}) => {
  // Ensure factories is always an array at runtime
  const safeFactories = Array.isArray(factories) ? factories : [];

  if (!Array.isArray(factories)) {
    console.warn(
      '[FactoryListSection] Expected `factories` to be an array but received:',
      factories
    );
  }

  if (isLoading) {
    return (
      <div className={styles.emptyState}>
        <p className={styles.emptyStateText}>Memuat daftar factory...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.emptyState}>
        <p className={styles.emptyStateText} style={{ color: '#ef4444' }}>{error}</p>
        <button type="button" className={styles.resetButton} onClick={onRetry}>
          Coba Lagi
        </button>
      </div>
    );
  }

  if (safeFactories.length === 0) {
    return (
      <div className={styles.emptyState}>
        <p className={styles.emptyStateText}>Belum ada factory terdaftar di database.</p>
        <button type="button" className={styles.parseButton} onClick={onAddNewClick}>
          Tambah Factory Pertama
        </button>
      </div>
    );
  }

  return (
    <div className={styles.factoryGrid}>
      {safeFactories.map((factory) => (
        <div key={factory.factoryId} className={styles.factoryCard}>
          <div>
            <span className={styles.factoryIdBadge}>ID: {factory.factoryId}</span>
            <h3 className={styles.factoryTitle}>{factory.factoryName}</h3>
            <p className={styles.factoryStats}>
              {factory.workersCount} Workers | {factory.jobDesksCount} Job Desks
            </p>
            {factory.createdAt && (
              <span className={styles.factoryTimestamp}>
                Dibuat: {new Date(factory.createdAt).toLocaleString('id-ID')}
              </span>
            )}
          </div>
          <div className={styles.factoryCardActions}>
            <button
              type="button"
              className={`${styles.parseButton} ${styles.fullWidthButton}`}
              onClick={() => onSelectFactory(factory.factoryId)}
            >
              Buka Digital Twin
            </button>
          </div>
        </div>
      ))}
    </div>
  );
};