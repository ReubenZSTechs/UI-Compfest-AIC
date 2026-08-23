// frontend/src/features/optimization/components/CostBreakdownChart.tsx
import { useState } from "react";
import styles from "./Charts.module.css";

interface Props {
  categories: string[];
  before: number[];
  after: number[];
}

export function CostBreakdownChart({ categories, before, after }: Props) {
  const [hoverCat, setHoverCat] = useState<number | null>(null);

  const width = 450;
  const height = 180;
  const paddingLeft = 38;
  const paddingRight = 20;
  const paddingTop = 20;
  const paddingBottom = 30;

  const chartWidth = width - paddingLeft - paddingRight;
  const chartHeight = height - paddingTop - paddingBottom;

  const maxVal = Math.max(
    ...(before && before.length ? before : [0]),
    ...(after && after.length ? after : [0]),
    2.0
  );
  const maxY = Math.ceil(maxVal * 1.2 * 2) / 2; // e.g. 3.0, 3.5
  const yTicks = [
    maxY,
    Number((maxY * 0.75).toFixed(2)),
    Number((maxY * 0.5).toFixed(2)),
    Number((maxY * 0.25).toFixed(2)),
    0,
  ];

  const getY = (val: number) => {
    const safeVal = typeof val === "number" && !isNaN(val) ? val : 0;
    const clamped = Math.max(0, Math.min(maxY, safeVal));
    return paddingTop + chartHeight - (clamped / maxY) * chartHeight;
  };

  const getBarHeight = (val: number) => {
    const safeVal = typeof val === "number" && !isNaN(val) ? val : 0;
    const clamped = Math.max(0, Math.min(maxY, safeVal));
    return (clamped / maxY) * chartHeight;
  };

  const groupWidth = chartWidth / Math.max(1, categories.length);
  const barWidth = Math.min(28, (groupWidth - 20) / 2);

  return (
    <div className={styles.chartContainer}>
      <div className={styles.chartTitle}>COST BREAKDOWN — RP JUTA/HARI</div>
      <div className={styles.svgWrapper}>
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className={styles.svgChart}
          preserveAspectRatio="xMidYMid meet"
        >
          {/* Y-axis grid & ticks */}
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
                  x={paddingLeft - 6}
                  y={y + 3.5}
                  textAnchor="end"
                  className={styles.axisLabel}
                >
                  {tick === 0 ? "0" : tick.toFixed(2).replace(/\.00$/, "")}
                </text>
              </g>
            );
          })}

          {/* Bars for each category */}
          {categories.map((cat, idx) => {
            const groupX = paddingLeft + idx * groupWidth;
            const barBeforeHeight = getBarHeight(before[idx]);
            const barAfterHeight = getBarHeight(after[idx]);
            const xBefore = groupX + groupWidth / 2 - barWidth - 2;
            const xAfter = groupX + groupWidth / 2 + 2;
            const yBefore = paddingTop + chartHeight - barBeforeHeight;
            const yAfter = paddingTop + chartHeight - barAfterHeight;
            const isHovered = hoverCat === idx;

            return (
              <g
                key={cat}
                onMouseEnter={() => setHoverCat(idx)}
                onMouseLeave={() => setHoverCat(null)}
                className={styles.interactiveGroup}
              >
                {/* Before Bar */}
                <rect
                  x={xBefore}
                  y={yBefore}
                  width={barWidth}
                  height={barBeforeHeight}
                  rx={2}
                  className={styles.barBefore}
                />

                {/* After Bar */}
                <rect
                  x={xAfter}
                  y={yAfter}
                  width={barWidth}
                  height={barAfterHeight}
                  rx={2}
                  className={styles.barAfter}
                />

                {/* Category Label */}
                <text
                  x={groupX + groupWidth / 2}
                  y={height - 8}
                  textAnchor="middle"
                  className={`${styles.axisLabel} ${styles.categoryLabel}`}
                >
                  {cat}
                </text>

                {/* Hover Tooltip */}
                {isHovered && (
                  <g
                    transform={`translate(${Math.min(
                      xBefore - 15,
                      width - 120
                    )}, ${Math.min(Math.min(yBefore, yAfter) - 45, height - 60)})`}
                    className={styles.tooltipBox}
                  >
                    <rect
                      width={110}
                      height={42}
                      rx={5}
                      className={styles.tooltipBg}
                    />
                    <text x={8} y={14} className={styles.tooltipTime}>
                      {cat}
                    </text>
                    <text x={8} y={26} className={styles.tooltipBefore}>
                      Sebelum: Rp {before[idx]}M
                    </text>
                    <text x={8} y={37} className={styles.tooltipAfter}>
                      Sesudah: Rp {after[idx]}M
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      <div className={styles.legend}>
        <span className={styles.legendItem}>
          <span className={styles.legendBoxBefore} />
          <span>sebelum</span>
        </span>
        <span className={styles.legendItem}>
          <span className={styles.legendBoxAfter} />
          <span>sesudah</span>
        </span>
      </div>
    </div>
  );
}

export default CostBreakdownChart;
