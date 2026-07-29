import type { VibrationHazardLevel } from "../types/digitalTwin.types";

export function formatCostPerHour(value: number): string {
  return `$${value.toFixed(2)}/jam`;
}

export function formatCapacity(value: number): string {
  return `${value.toLocaleString("id-ID")} unit/jam`;
}

export function formatWorkflowStepLabel(step: string): string {
  // "step_07_baking" -> "Baking"
  const parts = step.split("_").slice(2);
  return parts.map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join(" ");
}

export type StrainLevel = "safe" | "warning" | "danger";

export function strainLevelFromIndex(index: number): StrainLevel {
  if (index >= 0.5) return "danger";
  if (index >= 0.3) return "warning";
  return "safe";
}

export const VIBRATION_LABEL: Record<VibrationHazardLevel, string> = {
  low: "Rendah",
  medium: "Sedang",
  high: "Tinggi",
};

export function formatExperience(years: number): string {
  return years === 1 ? "1 tahun pengalaman" : `${years} tahun pengalaman`;
}

export function formatHoursWorked(hours: number): string {
  return `${hours.toFixed(1)} jam hari ini`;
}

export function getInitials(name: string): string {
  return name
    .split(" ")
    .map((part) => part.charAt(0))
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export type CapacityLevel = "low" | "medium" | "high";

// Dipakai untuk stamina & cognitive_resilience — nilai tinggi = baik (beda arah dari strain index)
export function capacityLevelFromValue(value: number): CapacityLevel {
  if (value >= 0.75) return "high";
  if (value >= 0.5) return "medium";
  return "low";
}

// tambahkan di bagian bawah file yang sudah ada

import type { ErrorSeverity, PhysicalDemandLevel } from "../types/digitalTwin.types";

export const ERROR_SEVERITY_LABEL: Record<ErrorSeverity, string> = {
  low: "Rendah",
  moderate: "Sedang",
  high: "Tinggi",
  critical: "Kritikal",
};

export const ERROR_SEVERITY_LEVEL: Record<ErrorSeverity, StrainLevel> = {
  low: "safe",
  moderate: "warning",
  high: "danger",
  critical: "danger",
};

export const PHYSICAL_DEMAND_LABEL: Record<PhysicalDemandLevel, string> = {
  low: "Rendah",
  medium: "Sedang",
  high: "Tinggi",
};

export const PHYSICAL_DEMAND_LEVEL: Record<PhysicalDemandLevel, StrainLevel> = {
  low: "safe",
  medium: "warning",
  high: "danger",
};

export const CONSECUTIVE_SHIFTS_WARNING_THRESHOLD = 4;