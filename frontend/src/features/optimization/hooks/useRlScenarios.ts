import { isAxiosError } from "axios";
import { useQuery } from "@tanstack/react-query";
import { fetchRlScenarioBundle } from "../api/rlOptimizationApi";

/** Loads the RL scenario bundle of a factory; a 404 means training has not finished yet. */
export function useRlScenarios(factoryId?: string) {
  const query = useQuery({
    queryKey: ["rl-scenarios", factoryId],
    queryFn: () => fetchRlScenarioBundle(factoryId as string),
    enabled: Boolean(factoryId),
    retry: (failureCount, error) =>
      !(isAxiosError(error) && error.response?.status === 404) && failureCount < 1,
    staleTime: 0,
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
