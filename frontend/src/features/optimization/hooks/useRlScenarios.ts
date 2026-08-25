import { useQuery } from "@tanstack/react-query";
import { fetchRlScenarioBundle } from "../api/rlOptimizationApi";

export function useRlScenarios(factoryId?: string) {
  const query = useQuery({
    queryKey: ["rl-scenarios", factoryId],
    queryFn: () => fetchRlScenarioBundle(factoryId as string),
    enabled: Boolean(factoryId),
    retry: 1,
    staleTime: 5 * 60 * 1000,
  });

  return {
    bundle: query.data ?? null,
    scenarios: query.data?.scenarios ?? [],
    meta: query.data?.meta ?? null,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error as Error | null,
    refetch: query.refetch,
  };
}