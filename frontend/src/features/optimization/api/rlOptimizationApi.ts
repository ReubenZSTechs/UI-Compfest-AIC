import { isAxiosError } from "axios";
import { apiClient } from "@/api/client";
import { ENDPOINTS } from "@/api/endpoints";
import type {
  RlOptimizationJob,
  RlOptimizeRequest,
  RlScenarioBundle,
} from "../types/rlScenario.types";

/** Loads the three RL scenarios exported by the latest finished training of a factory. */
export async function fetchRlScenarioBundle(
  factoryId: string
): Promise<RlScenarioBundle> {
  const { data } = await apiClient.get<RlScenarioBundle>(
    ENDPOINTS.RL_OPTIMIZATION.FACTORY_SCENARIOS(factoryId)
  );
  return data;
}

/** Starts RL training for a factory from its twin and the latest simulation run. */
export async function startRlOptimization(
  factoryId: string,
  payload: RlOptimizeRequest
): Promise<RlOptimizationJob> {
  const { data } = await apiClient.post<RlOptimizationJob>(
    ENDPOINTS.RL_OPTIMIZATION.FACTORY_OPTIMIZE(factoryId),
    payload,
    { timeout: 60000 }
  );
  return data;
}

/** Returns the latest RL job status of a factory, or null when it was never trained. */
export async function fetchRlOptimizationStatus(
  factoryId: string
): Promise<RlOptimizationJob | null> {
  try {
    const { data } = await apiClient.get<RlOptimizationJob>(
      ENDPOINTS.RL_OPTIMIZATION.FACTORY_OPTIMIZE_STATUS(factoryId)
    );
    return data;
  } catch (error) {
    if (isAxiosError(error) && error.response?.status === 404) return null;
    throw error;
  }
}
