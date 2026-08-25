import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/api/client";
import { ENDPOINTS } from "@/api/endpoints";

export interface FactoryItem {
  factoryId: string;
  factoryName: string;
  workersCount: number;
  jobDesksCount: number;
  createdAt?: string;
  jobId?: string;
}

export function useFactoryList() {
  const [factories, setFactories] = useState<FactoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchFactories = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const { data } = await apiClient.get<FactoryItem[]>(ENDPOINTS.DOCUMENT_PARSER.FACTORY_LIST);
      setFactories(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal mengambil daftar factory.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchFactories();
  }, [fetchFactories]);

  return { factories, isLoading, error, refetch: fetchFactories };
}