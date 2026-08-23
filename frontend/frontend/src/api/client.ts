import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import { API_BASE_URL, AUTH_TOKEN_KEY } from "@/config/env";

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

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ message?: string; detail?: string }>) => {
    const status = error.response?.status;
    const message =
      error.response?.data?.message ??
      error.response?.data?.detail ??
      error.message ??
      "Terjadi kesalahan tak terduga";

    if (status === 401) {
      localStorage.removeItem(AUTH_TOKEN_KEY);
    }

    console.error(`[API Error] ${status ?? "NETWORK"}: ${message}`);
    return Promise.reject(new Error(message));
  }
);