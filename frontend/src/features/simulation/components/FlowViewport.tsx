import { useCallback, useEffect, useRef, useState, type ReactNode, type WheelEvent } from "react";
import styles from "./FlowViewport.module.css";

const MIN_SCALE = 0.25;
const MAX_SCALE = 2.5;
const SCALE_STEP = 0.15;
const WHEEL_SENSITIVITY = 0.0016;

interface Transform {
  scale: number;
  offsetX: number;
  offsetY: number;
}

interface FlowViewportProps {
  children: ReactNode;
  className?: string;
}

export function FlowViewport({ children, className }: FlowViewportProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const contentRef = useRef<HTMLDivElement | null>(null);
  const panOrigin = useRef<{ x: number; y: number; offsetX: number; offsetY: number } | null>(null);

  const [transform, setTransform] = useState<Transform>({ scale: 1, offsetX: 0, offsetY: 0 });
  const [isPanning, setIsPanning] = useState(false);

  const clampScale = (value: number) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, value));

  const zoomAt = useCallback((nextScale: number, anchorX: number, anchorY: number) => {
    setTransform((current) => {
      const scale = clampScale(nextScale);
      const ratio = scale / current.scale;

      return {
        scale,
        offsetX: anchorX - (anchorX - current.offsetX) * ratio,
        offsetY: anchorY - (anchorY - current.offsetY) * ratio,
      };
    });
  }, []);

  function handleWheel(event: WheelEvent<HTMLDivElement>) {
    if (!event.ctrlKey && !event.metaKey && Math.abs(event.deltaY) < 2) return;

    const bounds = containerRef.current?.getBoundingClientRect();
    if (!bounds) return;

    event.preventDefault();

    setTransform((current) => {
      const scale = clampScale(current.scale * (1 - event.deltaY * WHEEL_SENSITIVITY));
      const ratio = scale / current.scale;
      const anchorX = event.clientX - bounds.left;
      const anchorY = event.clientY - bounds.top;

      return {
        scale,
        offsetX: anchorX - (anchorX - current.offsetX) * ratio,
        offsetY: anchorY - (anchorY - current.offsetY) * ratio,
      };
    });
  }

  function beginPan(event: React.PointerEvent<HTMLDivElement>) {
    if (event.button !== 0 && event.button !== 1) return;
    if ((event.target as HTMLElement).closest("button")) return;

    panOrigin.current = {
      x: event.clientX,
      y: event.clientY,
      offsetX: transform.offsetX,
      offsetY: transform.offsetY,
    };
    setIsPanning(true);
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function movePan(event: React.PointerEvent<HTMLDivElement>) {
    const origin = panOrigin.current;
    if (!origin) return;

    setTransform((current) => ({
      ...current,
      offsetX: origin.offsetX + (event.clientX - origin.x),
      offsetY: origin.offsetY + (event.clientY - origin.y),
    }));
  }

  function endPan(event: React.PointerEvent<HTMLDivElement>) {
    panOrigin.current = null;
    setIsPanning(false);
    event.currentTarget.releasePointerCapture(event.pointerId);
  }

  const fitToView = useCallback(() => {
    const container = containerRef.current;
    const content = contentRef.current;
    if (!container || !content) return;

    const padding = 48;
    const contentWidth = content.scrollWidth;
    const contentHeight = content.scrollHeight;
    if (contentWidth === 0 || contentHeight === 0) return;

    const scale = clampScale(
      Math.min(
        (container.clientWidth - padding) / contentWidth,
        (container.clientHeight - padding) / contentHeight,
        1
      )
    );

    setTransform({
      scale,
      offsetX: (container.clientWidth - contentWidth * scale) / 2,
      offsetY: (container.clientHeight - contentHeight * scale) / 2,
    });
  }, []);

  useEffect(() => {
    const frame = window.requestAnimationFrame(fitToView);
    return () => window.cancelAnimationFrame(frame);
  }, [fitToView]);

  function zoomFromCenter(delta: number) {
    const container = containerRef.current;
    if (!container) return;
    zoomAt(transform.scale + delta, container.clientWidth / 2, container.clientHeight / 2);
  }

  return (
    <div className={`${styles.viewport} ${className ?? ""}`}>
      <div
        ref={containerRef}
        className={`${styles.surface} ${isPanning ? styles.surfacePanning : ""}`}
        onWheel={handleWheel}
        onPointerDown={beginPan}
        onPointerMove={movePan}
        onPointerUp={endPan}
        onPointerCancel={endPan}
      >
        <div
          ref={contentRef}
          className={styles.content}
          style={{
            transform: `translate(${transform.offsetX}px, ${transform.offsetY}px) scale(${transform.scale})`,
          }}
        >
          {children}
        </div>
      </div>

      <div className={styles.controls}>
        <button type="button" className={styles.controlButton} onClick={() => zoomFromCenter(SCALE_STEP)}>
          +
        </button>
        <span className={styles.scaleLabel}>{Math.round(transform.scale * 100)}%</span>
        <button type="button" className={styles.controlButton} onClick={() => zoomFromCenter(-SCALE_STEP)}>
          −
        </button>
        <button type="button" className={styles.controlButton} onClick={fitToView} title="Sesuaikan tampilan">
          ⤢
        </button>
      </div>
    </div>
  );
}

export default FlowViewport;