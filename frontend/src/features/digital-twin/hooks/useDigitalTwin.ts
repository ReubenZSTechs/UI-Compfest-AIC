// frontend/src/features/digital-twin/hooks/useDigitalTwin.ts
import { useEffect } from "react";
import { useDigitalTwinStore } from "../store/digitalTwinStore";

export function useDigitalTwin(factoryId?: string) {
  const { data, isLoading, error, fetchTwin } = useDigitalTwinStore();

  useEffect(() => {
    fetchTwin(factoryId);
  }, [factoryId, fetchTwin]);

  return {
    data,
    isLoading,
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