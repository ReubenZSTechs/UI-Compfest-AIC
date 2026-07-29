import { apiClient } from "@/api/client";
import { ENDPOINTS } from "@/api/endpoints";
import type {
  DigitalTwin,
  Asset,
  Worker,
  JobDesk,
  CompatibilityEvaluation,
  FactoryFlowRightNow,
} from "../types/digitalTwin.types";

export const digitalTwinApi = {
  getFullTwin: async (): Promise<DigitalTwin> => {
    const { data } = await apiClient.get<DigitalTwin>(ENDPOINTS.DIGITAL_TWIN.ROOT);
    return data;
  },

  getAssets: async (): Promise<Asset[]> => {
    const { data } = await apiClient.get<Asset[]>(ENDPOINTS.DIGITAL_TWIN.ASSETS);
    return data;
  },

  getWorkers: async (): Promise<Worker[]> => {
    const { data } = await apiClient.get<Worker[]>(ENDPOINTS.DIGITAL_TWIN.WORKERS);
    return data;
  },

  getJobDesks: async (): Promise<JobDesk[]> => {
    const { data } = await apiClient.get<JobDesk[]>(ENDPOINTS.DIGITAL_TWIN.JOB_DESKS);
    return data;
  },

  getCompatibilityMatrix: async (): Promise<CompatibilityEvaluation[]> => {
    const { data } = await apiClient.get<CompatibilityEvaluation[]>(
      ENDPOINTS.DIGITAL_TWIN.COMPATIBILITY_MATRIX
    );
    return data;
  },

  getLiveFlow: async (): Promise<FactoryFlowRightNow> => {
    const { data } = await apiClient.get<FactoryFlowRightNow>(
      ENDPOINTS.DIGITAL_TWIN.LIVE_FLOW
    );
    return data;
  },
};