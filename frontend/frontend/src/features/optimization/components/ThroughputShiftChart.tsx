// frontend/src/features/optimization/components/ThroughputShiftChart.tsx
import { useState } from "react";
import styles from "./Charts.module.css";

interface Props {
  labels: string[];
  before: number[];
  after: number[];
}

export function ThroughputShiftChart({ labels, before, after }: Props) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const width = 500;
  const height = 180;
  const paddingLeft = 42;
  const paddingRight = 20;
  const paddingTop = 20;
  const paddingBottom = 30;

  const chartWidth = width - paddingLeft - paddingRight;
  const chartHeight = height - paddingTop - paddingBottom;

  const maxVal = Math.max(
    ...(before && before.length ? before : [0]),
    ...(after && after.length ? after : [0]),
    1000
  );
  const maxY = Math.ceil(maxVal / 300) * 300;
  const minY = 0;
  const yTicks = [
    maxY,
    Math.round(maxY * 0.75),
    Math.round(maxY * 0.5),
    Math.round(maxY * 0.25),
    0,
  ];

  const getX = (index: number) => {
    return paddingLeft + (index / Math.max(1, labels.length - 1)) * chartWidth;
  };

  const getY = (val: number) => {
    const safeVal = typeof val === "number" && !isNaN(val) ? val : 0;
    const clamped = Math.max(minY, Math.min(maxY, safeVal));
    return paddingTop + chartHeight - ((clamped - minY) / (maxY - minY)) * chartHeight;
  };

  const generatePath = (data: number[]) => {
    if (!data || data.length === 0) return "";
    return data
      .map((val, idx) => {
        const x = getX(idx);
        const y = getY(val);
        return `${idx === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
      })
      .join(" ");
  };

  return (
    <div className={styles.chartContainer}>
      <div className={styles.chartTitle}>THROUGHPUT OVER SHIFT — UNITS/HOUR</div>
      <div className={styles.svgWrapper}>
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className={styles.svgChart}
          preserveAspectRatio="xMidYMid meet"
        >
          {/* Grid lines & Y-axis ticks */}
          {yTicks.map((tick) => {
            const y = getY(tick);
            return (
              <g key={tick} className={styles.gridGroup}>
                <line
                  x1={paddingLeft}
                  y1={y}
                  x2={width - paddingRight}
                  y2={y}
                  className={styles.gridLine}
                />
                <text
                  x={paddingLeft - 8}
                  y={y + 3.5}
                  textAnchor="end"
                  className={styles.axisLabel}
                >
                  {tick}
                </text>
              </g>
            );
          })}

          {/* X-axis labels */}
          {labels.map((label, idx) => {
            const x = getX(idx);
            return (
              <text
                key={label}
                x={x}
                y={height - 8}
                textAnchor="middle"
                className={styles.axisLabel}
              >
                {label}
              </text>
            );
          })}

          {/* Baseline Line (sebelum) */}
          <path
            d={generatePath(before)}
            fill="none"
            className={styles.beforeLine}
          />

          {/* Optimized Line (sesudah) */}
          <path
            d={generatePath(after)}
            fill="none"
            className={styles.afterLine}
          />

          {/* Data Points and Hover Target */}
          {labels.map((_, idx) => {
            const x = getX(idx);
            const yBefore = getY(before[idx]);
            const yAfter = getY(after[idx]);
            const isHovered = hoverIdx === idx;

            return (
              <g
                key={idx}
                onMouseEnter={() => setHoverIdx(idx)}
                onMouseLeave={() => setHoverIdx(null)}
                className={styles.interactivePointGroup}
              >
                <circle
                  cx={x}
                  cy={yBefore}
                  r={isHovered ? 4.5 : 3}
                  className={styles.pointBefore}
                />
                <circle
                  cx={x}
                  cy={yAfter}
                  r={isHovered ? 5.5 : 4}
                  className={styles.pointAfter}
                />

                {/* Invisible wide hit area for easy hover */}
                <rect
                  x={x - 20}
                  y={paddingTop}
                  width={40}
                  height={chartHeight}
                  fill="transparent"
                  className={styles.hitArea}
                />

                {/* Hover line & tooltip */}
                {isHovered && (
                  <>
                    <line
                      x1={x}
                      y1={paddingTop}
                      x2={x}
                      y2={paddingTop + chartHeight}
                      className={styles.hoverGuideLine}
                    />
                    <g
                      transform={`translate(${x > width - 110 ? x - 105 : x + 8}, ${Math.min(
                        yAfter - 15,
                        height - 65
                      )})`}
                      className={styles.tooltipBox}
                    >
                      <rect
                        width={96}
                        height={46}
                        rx={5}
                        className={styles.tooltipBg}
                      />
                      <text x={8} y={15} className={styles.tooltipTime}>
                        Jam {labels[idx]}
                      </text>
                      <text x={8} y={28} className={styles.tooltipBefore}>
                        Sebelum: {before[idx]}
                      </text>
                      <text x={8} y={40} className={styles.tooltipAfter}>
                        Sesudah: {after[idx]}
                      </text>
                    </g>
                  </>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      <div className={styles.legend}>
        <span className={styles.legendItem}>
          <span className={styles.legendDotBefore} />
          <span>sebelum</span>
        </span>
        <span className={styles.legendItem}>
          <span className={styles.legendDotAfter} />
          <span>sesudah</span>
        </span>
      </div>
    </div>
  );
}

export default ThroughputShiftChart;
