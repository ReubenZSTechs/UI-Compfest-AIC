// frontend/src/features/digital-twin/api/digitalTwinApi.ts
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
  /**
   * Mengambil snapshot Digital Twin lengkap berdasarkan factoryId.
   */
  getFullTwin: async (factoryId?: string): Promise<DigitalTwin> => {
    const { data } = await apiClient.get<DigitalTwin>(ENDPOINTS.DIGITAL_TWIN.ROOT, {
      params: factoryId ? { factory_id: factoryId } : undefined,
    });
    return data;
  },

  /**
   * Mengambil daftar aset/mesin pabrik.
   */
  getAssets: async (factoryId?: string): Promise<Asset[]> => {
    const { data } = await apiClient.get<Asset[]>(ENDPOINTS.DIGITAL_TWIN.ASSETS, {
      params: factoryId ? { factory_id: factoryId } : undefined,
    });
    return data;
  },

  /**
   * Mengambil daftar profil pekerja beserta demografi & shift context.
   */
  getWorkers: async (factoryId?: string): Promise<Worker[]> => {
    const { data } = await apiClient.get<Worker[]>(ENDPOINTS.DIGITAL_TWIN.WORKERS, {
      params: factoryId ? { factory_id: factoryId } : undefined,
    });
    return data;
  },

  /**
   * Mengambil daftar job desks (pekerjaan utama pabrik).
   */
  getJobDesks: async (factoryId?: string): Promise<JobDesk[]> => {
    const { data } = await apiClient.get<JobDesk[]>(ENDPOINTS.DIGITAL_TWIN.JOB_DESKS, {
      params: factoryId ? { factory_id: factoryId } : undefined,
    });
    return data;
  },

  /**
   * Mengambil matriks kompatibilitas (llmCompatibilityAndEvaluations) yang telah diratakan.
   */
  getCompatibilityMatrix: async (factoryId?: string): Promise<CompatibilityEvaluation[]> => {
    const { data } = await apiClient.get<CompatibilityEvaluation[]>(
      ENDPOINTS.DIGITAL_TWIN.COMPATIBILITY_MATRIX,
      {
        params: factoryId ? { factory_id: factoryId } : undefined,
      }
    );
    return data;
  },

  /**
   * Mengambil status posisi pekerja dan live flow pabrik terkini.
   */
  getLiveFlow: async (factoryId?: string): Promise<FactoryFlowRightNow | null> => {
    const { data } = await apiClient.get<FactoryFlowRightNow | null>(
      ENDPOINTS.DIGITAL_TWIN.LIVE_FLOW,
      {
        params: factoryId ? { factory_id: factoryId } : undefined,
      }
    );
    return data;
  },
};