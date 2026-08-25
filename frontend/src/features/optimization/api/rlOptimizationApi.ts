import { apiClient } from "@/api/client";
import { ENDPOINTS } from "@/api/endpoints";
import type { RlScenarioBundle } from "../types/rlScenario.types";

export async function fetchRlScenarioBundle(
  factoryId: string
): Promise<RlScenarioBundle> {
  const { data } = await apiClient.get<RlScenarioBundle>(
    ENDPOINTS.RL_OPTIMIZATION.FACTORY_SCENARIOS(factoryId)
  );
  return data;
}