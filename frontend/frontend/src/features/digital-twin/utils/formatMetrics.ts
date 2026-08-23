import type {
  VibrationHazardLevel,
  ErrorSeverity,
  PhysicalDemandLevel,
} from "../types/digitalTwin.types";

export function formatCostPerHour(value?: number | null): string {
  if (value == null || isNaN(value)) return "$0.00/jam";
  return `$${value.toFixed(2)}/jam`;
}

export function formatCapacity(value?: number | null): string {
  if (value == null || isNaN(value)) return "0 unit/jam";
  return `${value.toLocaleString("id-ID")} unit/jam`;
}

export function formatWorkflowStepLabel(step?: string | null): string {
  if (!step) return "";
  // "step_07_baking" -> "Baking"
  const parts = step.split("_");
  const nameParts = parts.length > 2 ? parts.slice(2) : parts;
  return nameParts.map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join(" ");
}

export type StrainLevel = "safe" | "warning" | "danger";

export function strainLevelFromIndex(index?: number | null): StrainLevel {
  const val = index ?? 0;
  if (val >= 0.5) return "danger";
  if (val >= 0.3) return "warning";
  return "safe";
}

export const VIBRATION_LABEL: Record<VibrationHazardLevel, string> = {
  low: "Rendah",
  medium: "Sedang",
  high: "Tinggi",
};

export function formatExperience(years?: number | null): string {
  const yrs = years ?? 0;
  return yrs === 1 ? "1 tahun pengalaman" : `${yrs} tahun pengalaman`;
}

export function formatHoursWorked(hours?: number | null): string {
  const h = hours ?? 0;
  return `${h.toFixed(1)} jam hari ini`;
}

export function getInitials(name?: string | null): string {
  if (!name) return "";
  return name
    .trim()
    .split(/\s+/)
    .map((part) => part.charAt(0))
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export type CapacityLevel = "low" | "medium" | "high";

// Dipakai untuk stamina & cognitive_resilience — nilai tinggi = baik (beda arah dari strain index)
export function capacityLevelFromValue(value?: number | null): CapacityLevel {
  const val = value ?? 0;
  if (val >= 0.75) return "high";
  if (val >= 0.5) return "medium";
  return "low";
}

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