import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchRlOptimizationStatus,
  startRlOptimization,
} from "../api/rlOptimizationApi";
import type { RlOptimizeRequest } from "../types/rlScenario.types";

const POLL_INTERVAL_MS = 2000;

/** Tracks the RL training job of a factory, polling while it runs and refreshing scenarios when done. */
export function useRlOptimizationJob(factoryId?: string) {
  const queryClient = useQueryClient();
  const statusKey = ["rl-optimization-status", factoryId];

  const statusQuery = useQuery({
    queryKey: statusKey,
    queryFn: () => fetchRlOptimizationStatus(factoryId as string),
    enabled: Boolean(factoryId),
    refetchInterval: (query) => {
      const state = query.state.data?.status;
      return state === "queued" || state === "running" ? POLL_INTERVAL_MS : false;
    },
  });

  const startMutation = useMutation({
    mutationFn: (payload: RlOptimizeRequest) =>
      startRlOptimization(factoryId as string, payload),
    onSuccess: (job) => {
      queryClient.setQueryData(statusKey, job);
    },
  });

  const job = statusQuery.data ?? null;
  const previousState = useRef(job?.status);
  useEffect(() => {
    if (job?.status === "converged" && previousState.current !== "converged") {
      void queryClient.invalidateQueries({ queryKey: ["rl-scenarios", factoryId] });
    }
    previousState.current = job?.status;
  }, [job?.status, factoryId, queryClient]);

  return {
    job,
    isTraining: job?.status === "queued" || job?.status === "running",
    isStarting: startMutation.isPending,
    startError: startMutation.error as Error | null,
    start: startMutation.mutate,
  };
}
