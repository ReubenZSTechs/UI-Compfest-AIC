import { useEffect } from "react";
import { useDigitalTwinStore } from "../store/digitalTwinStore";

export function useDigitalTwin() {
  const { data, isLoading, error, fetchTwin } = useDigitalTwinStore();

  useEffect(() => {
    if (!data && !isLoading) {
      fetchTwin();
    }
  }, [data, isLoading, fetchTwin]);

  return { data, isLoading, error, refetch: fetchTwin };
}