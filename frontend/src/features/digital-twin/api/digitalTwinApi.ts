import { apiClient } from "@/api/client";
import { ENDPOINTS } from "@/api/endpoints";
import type { DigitalTwin } from "../types/digitalTwin.types";

export const digitalTwinApi = {
  /** Loads the full digital twin of a factory. */
  getFullTwin: async (factoryId: string): Promise<DigitalTwin> => {
    const { data } = await apiClient.get<DigitalTwin>(
      ENDPOINTS.FACTORIES.DIGITAL_TWIN(factoryId)
    );
    return data;
  },
};
