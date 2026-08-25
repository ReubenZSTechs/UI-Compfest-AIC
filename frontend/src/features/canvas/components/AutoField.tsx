import type { ReactNode } from "react";
import { FieldAutoToggle } from "./FieldAutoToggle";
import type { FieldAutofillController } from "../hooks/useFieldAutofill";
import type { AutofillFieldKey } from "../types/canvas.types";
import styles from "./SidebarDetail.module.css";

interface AutoFieldProps {
  label: ReactNode;
  fieldKey: AutofillFieldKey;
  auto: FieldAutofillController;
  children: (locked: boolean) => ReactNode;
}

export function AutoField({ label, fieldKey, auto, children }: AutoFieldProps) {
  const locked = auto.isAuto(fieldKey);
  const status = auto.statusOf(fieldKey);
  const error = auto.errorOf(fieldKey);

  return (
    <div className={styles.field}>
      <span className={styles.fieldLabel}>
        {label}
        <FieldAutoToggle
          nodeId={auto.nodeId}
          fieldKey={fieldKey}
          checked={locked}
          status={status}
          onChange={(next) => auto.toggleField(fieldKey, next)}
        />
      </span>
      {children(locked)}
      {status === "loading" && <span className={styles.autoNote}>Agent sedang mengisi…</span>}
      {error && <span className={styles.autoError}>{error}</span>}
    </div>
  );
}

export default AutoField;