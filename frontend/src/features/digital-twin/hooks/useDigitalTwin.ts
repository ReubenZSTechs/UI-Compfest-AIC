import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useDigitalTwinStore } from "../store/digitalTwinStore";
import { mockDigitalTwin } from "../mocks/mockDigitalTwin";

export function useDigitalTwin(factoryId?: string) {
  const [searchParams] = useSearchParams();
  // Mode testing frontend: aktif lewat query param ?mock=true, contoh:
  // http://localhost:5173/DigitalTwinPage?mock=true
  const isMockMode = searchParams.get("mock") === "true";

  const { data, isLoading, isFetched, error, fetchTwin, setMockData } = useDigitalTwinStore();

  useEffect(() => {
    if (isMockMode) {
      // Isi store langsung dengan data dummy, tanpa memanggil API backend.
      setMockData(mockDigitalTwin);
      return;
    }
    fetchTwin(factoryId);
  }, [factoryId, fetchTwin, isMockMode, setMockData]);

  return {
    data,
    isLoading,
    isFetched,
    error,
    refetch: (id?: string) => fetchTwin(id ?? factoryId),

    // Helper getters dengan null safety & format camelCase
    factoryInfo: data?.factoryInfo ?? null,
    assets: data?.assets ?? [],
    jobDesks: data?.jobDesks ?? [],
    workers: data?.workers ?? [],

    // Properti posisi staf dan live flow pabrik terkini
    staffCurrentPositions: data?.factoryFlowRightnow?.staffCurrentPositions ?? [],
    factoryFlowRightNow: data?.factoryFlowRightnow ?? null,

    // Array flattened evaluasi kompatibilitas LLM
    compatibilityEvaluations: data?.llmCompatibilityAndEvaluations ?? [],
  };
}