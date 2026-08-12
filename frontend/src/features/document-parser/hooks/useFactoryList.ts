import { useState, useEffect, useCallback } from 'react';

export interface FactoryItem {
  factoryId: string;
  factoryName: string;
  workersCount: number;
  jobDesksCount: number;
  createdAt?: string;
}

export function useFactoryList() {
  const [factories, setFactories] = useState<FactoryItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchFactories = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/v1/documents/factories');
      if (!response.ok) {
        throw new Error(`Gagal memuat data factory (${response.status})`);
      }
      const data = await response.json();
      setFactories(data);
    } catch (err: any) {
      setError(err.message || 'Terjadi kesalahan saat mengambil daftar factory.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchFactories();
  }, [fetchFactories]);

  return {
    factories,
    isLoading,
    error,
    refetch: fetchFactories,
  };
}