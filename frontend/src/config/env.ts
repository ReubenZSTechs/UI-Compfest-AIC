import { z } from "zod";

const envSchema = z.object({
  // Relative path (mis. "/api") atau absolute URL, tergantung environment.
  // Default "/api" cocok dengan build arg di frontend.Dockerfile dan
  // proxy_pass nginx -> backend:8000.
  VITE_API_URL: z.string().default("/api"),
  VITE_API_VERSION: z.string().default("v1"),

  VITE_AUTH_TOKEN_KEY: z.string().default("auth_token"),
  VITE_APP_ENV: z.enum(["development", "staging", "production"]).default("development"),
  VITE_USE_MOCK_API: z
    .string()
    .default("false")
    .transform((val) => val === "true"),
});

type EnvSchema = z.infer<typeof envSchema>;

function validateEnv(): EnvSchema {
  const parsed = envSchema.safeParse(import.meta.env);

  if (!parsed.success) {
    const formatted = parsed.error.flatten().fieldErrors;
    console.error("❌ Environment variable tidak valid:", formatted);
    throw new Error(
      `Konfigurasi environment gagal divalidasi:\n${Object.entries(formatted)
        .map(([key, errors]) => `  - ${key}: ${errors?.join(", ")}`)
        .join("\n")}`
    );
  }

  return parsed.data;
}

export const env = validateEnv();

// Satu-satunya sumber base URL API di seluruh app (dipakai simulationApi.ts,
// digitalTwinApi.ts, client.ts, dst). Hasil: "/api/v1" di production
// (relative, lolos nginx proxy, tanpa CORS), atau full URL kalau di-set
// eksplisit untuk dev tanpa nginx (mis. http://localhost:8000/api/v1).
export const API_BASE_URL = `${env.VITE_API_URL}/${env.VITE_API_VERSION}`;
export const AUTH_TOKEN_KEY = env.VITE_AUTH_TOKEN_KEY;
export const IS_PRODUCTION = env.VITE_APP_ENV === "production";
export const USE_MOCK_API = env.VITE_USE_MOCK_API;