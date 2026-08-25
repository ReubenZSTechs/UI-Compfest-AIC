import { useState } from "react";
import { autofillNodeDemands } from "../api/canvasApi";
import type { NodeAutofillRequest, NodeAutofillResponse } from "../types/canvas.types";
import styles from "./AutoFillButton.module.css";

interface AutoFillButtonProps {
  label?: string;
  targetFields: string[];
  buildRequest: () => NodeAutofillRequest;
  onFilled: (response: NodeAutofillResponse) => void;
  disabled?: boolean;
}

export function AutoFillButton({
  label = "Auto",
  targetFields,
  buildRequest,
  onFilled,
  disabled = false,
}: AutoFillButtonProps) {
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);

  async function handleClick() {
    setStatus("loading");
    setMessage(null);

    try {
      const response = await autofillNodeDemands({
        ...buildRequest(),
        targetFields,
      });
      onFilled(response);
      setStatus("idle");
      setMessage(response.reasoning || null);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Auto-fill gagal.");
    }
  }

  return (
    <span className={styles.wrapper}>
      <button
        type="button"
        className={`${styles.button} ${status === "error" ? styles.buttonError : ""}`}
        onClick={handleClick}
        disabled={disabled || status === "loading"}
        title="Isi otomatis dari konteks kolom lain"
      >
        {status === "loading" ? "…" : label}
      </button>
      {message && <span className={styles.hint}>{message}</span>}
    </span>
  );
}

export default AutoFillButton;