import type { MouseEvent } from "react";
import type { AutofillFieldKey } from "../types/canvas.types";
import styles from "./FieldAutoToggle.module.css";

export type FieldAutoStatus = "idle" | "loading" | "error";

interface FieldAutoToggleProps {
  fieldKey: AutofillFieldKey;
  nodeId: string;
  checked: boolean;
  status?: FieldAutoStatus;
  onChange: (checked: boolean) => void;
}

const STATUS_TITLE: Record<FieldAutoStatus, string> = {
  idle: "Isi otomatis kolom ini lewat agent",
  loading: "Agent sedang mengisi kolom ini",
  error: "Agent gagal, klik lagi untuk mencoba ulang",
};

export function FieldAutoToggle({
  fieldKey,
  nodeId,
  checked,
  status = "idle",
  onChange,
}: FieldAutoToggleProps) {
  const trackClass = [
    styles.track,
    checked ? styles.trackOn : "",
    status === "error" ? styles.trackError : "",
    status === "loading" ? styles.trackBusy : "",
  ]
    .filter(Boolean)
    .join(" ");

  function handleClick(event: MouseEvent<HTMLButtonElement>) {
    event.preventDefault();
    event.stopPropagation();
    onChange(!checked);
  }

  return (
    <span className={styles.wrapper}>
      <button
        type="button"
        role="switch"
        id={`auto-${nodeId}-${fieldKey}`}
        aria-checked={checked}
        aria-label="Isi otomatis"
        className={trackClass}
        title={STATUS_TITLE[status]}
        disabled={status === "loading"}
        onClick={handleClick}
      >
        <span className={styles.knob} />
      </button>
      <span className={styles.caption}>Auto</span>
    </span>
  );
}

export default FieldAutoToggle;