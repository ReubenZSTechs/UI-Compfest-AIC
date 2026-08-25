import type { AutofillFieldKey, FieldFillMode } from "../types/canvas.types";
import styles from "./FieldModeToggle.module.css";

interface FieldModeToggleProps {
  fieldKey: AutofillFieldKey;
  nodeId: string;
  mode: FieldFillMode;
  onChange: (mode: FieldFillMode) => void;
}

export function FieldModeToggle({ fieldKey, nodeId, mode, onChange }: FieldModeToggleProps) {
  const groupName = `fill-mode-${nodeId}-${fieldKey}`;

  return (
    <span className={styles.group} role="radiogroup" aria-label="Mode pengisian">
      <label className={`${styles.option} ${mode === "manual" ? styles.optionActive : ""}`}>
        <input
          type="radio"
          name={groupName}
          className={styles.radio}
          checked={mode === "manual"}
          onChange={() => onChange("manual")}
        />
        Manual
      </label>
      <label className={`${styles.option} ${mode === "auto" ? styles.optionActive : ""}`}>
        <input
          type="radio"
          name={groupName}
          className={styles.radio}
          checked={mode === "auto"}
          onChange={() => onChange("auto")}
        />
        Auto
      </label>
    </span>
  );
}

export default FieldModeToggle;