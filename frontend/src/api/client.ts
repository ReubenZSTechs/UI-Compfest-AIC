import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import { API_BASE_URL, AUTH_TOKEN_KEY } from "@/config/env";

interface ValidationItem {
  loc?: unknown[];
  msg?: string;
  type?: string;
}

interface StructuredDetail {
  stage?: string;
  message?: string;
  details?: unknown[];
}

export interface ApiError extends Error {
  status?: number;
  payload?: unknown;
}

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem(AUTH_TOKEN_KEY);
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

function formatValidationItem(item: unknown): string {
  if (typeof item === "string") return item;
  if (!item || typeof item !== "object") return String(item);

  const entry = item as ValidationItem;
  const path = Array.isArray(entry.loc)
    ? entry.loc
        .filter((part) => part !== "body" && part !== "query" && part !== "path")
        .join(".")
    : "";
  const message = entry.msg ?? entry.type ?? "tidak valid";

  return path ? `${path} → ${message}` : message;
}

function formatStructuredDetail(detail: StructuredDetail): string {
  const stage = detail.stage ? `[${detail.stage}] ` : "";
  const base = detail.message ?? JSON.stringify(detail);
  const extra =
    Array.isArray(detail.details) && detail.details.length > 0
      ? ` (${detail.details.map(formatValidationItem).join("; ")})`
      : "";

  return `${stage}${base}${extra}`;
}

function extractErrorMessage(data: unknown, fallback: string): string {
  if (typeof data === "string" && data.trim()) return data;
  if (!data || typeof data !== "object") return fallback;

  const body = data as { detail?: unknown; message?: unknown };
  const detail = body.detail ?? body.message;

  if (typeof detail === "string" && detail.trim()) return detail;

  if (Array.isArray(detail)) {
    const parts = detail.map(formatValidationItem).filter(Boolean);
    return parts.length > 0 ? parts.join(" | ") : fallback;
  }

  if (detail && typeof detail === "object") {
    return formatStructuredDetail(detail as StructuredDetail);
  }

  return fallback;
}

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    const status = error.response?.status;
    const payload = error.response?.data;
    const message = extractErrorMessage(
      payload,
      error.message || "Terjadi kesalahan tak terduga"
    );

    if (status === 401) {
      localStorage.removeItem(AUTH_TOKEN_KEY);
    }

    console.error(`[API Error] ${status ?? "NETWORK"}: ${message}`, payload);

    const apiError: ApiError = new Error(message);
    apiError.name = "ApiError";
    apiError.status = status;
    apiError.payload = payload;

    return Promise.reject(apiError);
  }
);