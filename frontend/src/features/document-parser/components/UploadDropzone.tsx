import { useCallback, useRef, useState } from 'react';
import type { DragEvent } from 'react';
import styles from './UploadDropzone.module.css';

export type DropzoneAccent = 'automated' | 'manual';

interface UploadDropzoneProps {
  id: string;
  eyebrow: string;
  title: string;
  description: string;
  accept: string;
  acceptLabel: string;
  accent: DropzoneAccent;
  file: File | null;
  errorMessage?: string;
  disabled?: boolean;
  onFileSelect: (file: File) => void;
  onClear: () => void;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function UploadDropzone({
  id,
  eyebrow,
  title,
  description,
  accept,
  acceptLabel,
  accent,
  file,
  errorMessage,
  disabled,
  onFileSelect,
  onClear,
}: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragActive, setIsDragActive] = useState(false);

  const handleFiles = useCallback(
    (fileList: FileList | null) => {
      const selected = fileList?.[0];
      if (selected) onFileSelect(selected);
    },
    [onFileSelect]
  );

  const handleDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setIsDragActive(false);
      if (disabled) return;
      handleFiles(event.dataTransfer.files);
    },
    [disabled, handleFiles]
  );

  const hasError = Boolean(errorMessage);
  const hasFile = Boolean(file) && !hasError;

  const classNames = [
    styles.dropzone,
    styles[accent],
    isDragActive ? styles.dragActive : '',
    hasFile ? styles.filled : '',
    hasError ? styles.error : '',
    disabled ? styles.disabled : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div
      className={classNames}
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) setIsDragActive(true);
      }}
      onDragLeave={() => setIsDragActive(false)}
      onDrop={handleDrop}
    >
      <input
        ref={inputRef}
        id={id}
        type="file"
        accept={accept}
        className={styles.hiddenInput}
        disabled={disabled}
        onChange={(event) => handleFiles(event.target.files)}
      />

      <div className={styles.header}>
        <span className={styles.eyebrow}>{eyebrow}</span>
        <span className={styles.badge}>{acceptLabel}</span>
      </div>

      {!hasFile ? (
        <label htmlFor={id} className={styles.dropArea}>
          <svg className={styles.icon} viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M12 16V4M12 4L7 9M12 4L17 9"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M4 16V18.5C4 19.3284 4.67157 20 5.5 20H18.5C19.3284 20 20 19.3284 20 18.5V16"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <p className={styles.title}>{title}</p>
          <p className={styles.description}>{description}</p>
          <span className={styles.browseHint}>Tarik file kesini, atau klik untuk pilih</span>
        </label>
      ) : (
        <div className={styles.fileRow}>
          <svg className={styles.fileIcon} viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M6 3H13L18 8V19C18 20.1046 17.1046 21 16 21H6C4.89543 21 4 20.1046 4 19V5C4 3.89543 4.89543 3 6 3Z"
              stroke="currentColor"
              strokeWidth="1.6"
            />
            <path d="M13 3V8H18" stroke="currentColor" strokeWidth="1.6" />
          </svg>
          <div className={styles.fileInfo}>
            <span className={styles.fileName}>{file?.name}</span>
            <span className={styles.fileMeta}>{file ? formatBytes(file.size) : ''}</span>
          </div>
          <button
            type="button"
            className={styles.clearButton}
            onClick={onClear}
            disabled={disabled}
            aria-label={`Hapus ${title}`}
          >
            Ganti
          </button>
        </div>
      )}

      {hasError && <p className={styles.errorText}>{errorMessage}</p>}
    </div>
  );
}