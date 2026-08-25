import { apiClient } from "@/api/client";
import { ENDPOINTS } from "@/api/endpoints";
import type {
  Asset,
  CompatibilityEvaluation,
  DigitalTwin,
  FactoryFlowRightNow,
  JobDesk,
  Worker,
} from "../types/digitalTwin.types";

export const digitalTwinApi = {
  getFullTwin: async (factoryId: string): Promise<DigitalTwin> => {
    const { data } = await apiClient.get<DigitalTwin>(
      ENDPOINTS.FACTORIES.DIGITAL_TWIN(factoryId)
    );
    return data;
  },

  getAssets: async (factoryId: string): Promise<Asset[]> => {
    const twin = await digitalTwinApi.getFullTwin(factoryId);
    return twin.assets ?? [];
  },

  getWorkers: async (factoryId: string): Promise<Worker[]> => {
    const twin = await digitalTwinApi.getFullTwin(factoryId);
    return twin.workers ?? [];
  },

  getJobDesks: async (factoryId: string): Promise<JobDesk[]> => {
    const twin = await digitalTwinApi.getFullTwin(factoryId);
    return twin.jobDesks ?? [];
  },

  getCompatibilityMatrix: async (factoryId: string): Promise<CompatibilityEvaluation[]> => {
    const { data } = await apiClient.get<CompatibilityEvaluation[]>(
      ENDPOINTS.DIGITAL_TWIN.COMPATIBILITY_MATRIX(factoryId)
    );
    return data;
  },

  getLiveFlow: async (jobId?: string): Promise<FactoryFlowRightNow | null> => {
    const { data } = await apiClient.get<FactoryFlowRightNow | null>(
      ENDPOINTS.DIGITAL_TWIN.LIVE_FLOW,
      { params: jobId ? { job_id: jobId } : undefined }
    );
    return data;
  },
};