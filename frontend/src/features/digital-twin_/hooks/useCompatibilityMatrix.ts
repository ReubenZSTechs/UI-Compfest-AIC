// frontend/src/features/digital-twin/hooks/useCompatibilityMatrix.ts
import { useDigitalTwin } from "./useDigitalTwin";

export function useCompatibilityMatrix(factoryId?: string) {
  const { compatibilityEvaluations, isLoading, error } = useDigitalTwin(factoryId);

  return {
    matrix: compatibilityEvaluations,
    isLoading,
    error,
  };
}