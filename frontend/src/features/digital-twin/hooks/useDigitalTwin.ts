import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useDigitalTwinStore } from "../store/digitalTwinStore";

export function useDigitalTwin(factoryId?: string) {
  const [searchParams] = useSearchParams();
  const resolvedFactoryId =
    factoryId ?? searchParams.get("factoryId") ?? searchParams.get("factory_id") ?? undefined;

  const { data, isLoading, isFetched, error, fetchTwin } = useDigitalTwinStore();

  useEffect(() => {
    if (!resolvedFactoryId) return;
    void fetchTwin(resolvedFactoryId);
  }, [resolvedFactoryId, fetchTwin]);

  return {
    data,
    isLoading,
    isFetched,
    error,
    factoryId: resolvedFactoryId,
    refetch: (id?: string) => fetchTwin(id ?? resolvedFactoryId ?? ""),
    factoryInfo: data?.factoryInfo ?? null,
    assets: data?.assets ?? [],
    jobDesks: data?.jobDesks ?? [],
    workers: data?.workers ?? [],
    staffCurrentPositions: data?.factoryFlowRightnow?.staffCurrentPositions ?? [],
    factoryFlowRightNow: data?.factoryFlowRightnow ?? null,
    compatibilityEvaluations: data?.llmCompatibilityAndEvaluations ?? [],
  };
}