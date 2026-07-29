import { useQuery } from "@tanstack/react-query";
import { digitalTwinApi } from "../api/digitalTwinApi";
import { digitalTwinMockData } from "../api/digitalTwinApi.mock";
import { QUERY_KEYS } from "@/config/constants";
import { USE_MOCK_API } from "@/config/env";
import type { DigitalTwin } from "../types/digitalTwin.types";

export function useDigitalTwin() {
  return useQuery<DigitalTwin>({
    queryKey: [QUERY_KEYS.DIGITAL_TWIN],
    queryFn: async () => {
      if (USE_MOCK_API) {
        // Simulasi latency supaya loading state kerasa natural saat dev
        await new Promise((resolve) => setTimeout(resolve, 300));
        return digitalTwinMockData;
      }
      return digitalTwinApi.getFullTwin();
    },
    staleTime: 60_000,
  });
}