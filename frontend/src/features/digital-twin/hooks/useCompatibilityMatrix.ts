import { useDigitalTwin } from "./useDigitalTwin";

export function useCompatibilityMatrix() {
  const { data, isLoading, error } = useDigitalTwin();
  return {
    matrix: data?.llm_compatibility_and_evaluations ?? [],
    isLoading,
    error,
  };
}