import { useCallback, useEffect, useRef, useState } from "react";
import { useCanvasUIStore } from "@/store/canvasUI";
import { autofillSingleField } from "../utils/autofillNodes";
import type { FieldAutoStatus } from "../components/FieldAutoToggle";
import type {
  AutofillFieldKey,
  CanvasProcessData,
  NodeFieldModes,
} from "../types/canvas.types";

const EMPTY_MODES: NodeFieldModes = {};

export interface FieldAutofillController {
  nodeId: string;
  isAuto: (key: AutofillFieldKey) => boolean;
  statusOf: (key: AutofillFieldKey) => FieldAutoStatus;
  errorOf: (key: AutofillFieldKey) => string | null;
  toggleField: (key: AutofillFieldKey, next: boolean) => void;
}

type StatusMap = Partial<Record<AutofillFieldKey, FieldAutoStatus>>;
type ErrorMap = Partial<Record<AutofillFieldKey, string>>;

export function useFieldAutofill(nodeId: string): FieldAutofillController {
  const autoFields = useCanvasUIStore((state) => {
    const node = state.nodes.find((item) => item.id === nodeId);
    if (!node || node.data.kind !== "process") return EMPTY_MODES;
    return (node.data as CanvasProcessData).autoFields ?? EMPTY_MODES;
  });

  const [statuses, setStatuses] = useState<StatusMap>({});
  const [errors, setErrors] = useState<ErrorMap>({});
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const writeMode = useCallback(
    (key: AutofillFieldKey, next: boolean) => {
      const store = useCanvasUIStore.getState();
      const node = store.nodes.find((item) => item.id === nodeId);
      if (!node || node.data.kind !== "process") return;

      const current = (node.data as CanvasProcessData).autoFields ?? EMPTY_MODES;
      store.snapshot();
      store.updateNodeData(nodeId, {
        autoFields: { ...current, [key]: next ? "auto" : "manual" },
      });
    },
    [nodeId]
  );

  const toggleField = useCallback(
    (key: AutofillFieldKey, next: boolean) => {
      writeMode(key, next);
      setErrors((prev) => ({ ...prev, [key]: undefined }));

      if (!next) {
        setStatuses((prev) => ({ ...prev, [key]: "idle" }));
        return;
      }

      setStatuses((prev) => ({ ...prev, [key]: "loading" }));

      autofillSingleField(nodeId, key)
        .then(() => {
          if (!mounted.current) return;
          setStatuses((prev) => ({ ...prev, [key]: "idle" }));
        })
        .catch((error: unknown) => {
          if (!mounted.current) return;
          setStatuses((prev) => ({ ...prev, [key]: "error" }));
          setErrors((prev) => ({
            ...prev,
            [key]: error instanceof Error ? error.message : "Auto-fill gagal.",
          }));
        });
    },
    [nodeId, writeMode]
  );

  const isAuto = useCallback(
    (key: AutofillFieldKey) => autoFields[key] === "auto",
    [autoFields]
  );

  const statusOf = useCallback(
    (key: AutofillFieldKey): FieldAutoStatus => statuses[key] ?? "idle",
    [statuses]
  );

  const errorOf = useCallback((key: AutofillFieldKey) => errors[key] ?? null, [errors]);

  return { nodeId, isAuto, statusOf, errorOf, toggleField };
}