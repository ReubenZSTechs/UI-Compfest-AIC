import { z } from "zod";

const envSchema = z.object({
  VITE_API_BASE_URL: z.string().url({
    message: "VITE_API_BASE_URL harus berupa URL valid, mis. http://localhost:8000",
  }),
  VITE_API_VERSION: z.string().default("v1"),

  // Opsional: WebSocket simulation engine belum dibangun di backend.
  // Kalau kosong, semua fitur real-time (useSimulationSocket dkk) harus
  // fallback ke polling atau nonaktif — jangan asumsikan selalu ada nilainya.
  VITE_WS_URL: z
    .string()
    .optional()
    .refine(
      (val) => !val || val.startsWith("ws://") || val.startsWith("wss://"),
      { message: "VITE_WS_URL harus diawali ws:// atau wss:// jika diisi" }
    ),

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

// Re-export dengan nama lebih pendek
export const API_BASE_URL = `${env.VITE_API_BASE_URL}/api/${env.VITE_API_VERSION}`;
export const WS_URL = env.VITE_WS_URL; // string | undefined — cek sebelum dipakai
export const AUTH_TOKEN_KEY = env.VITE_AUTH_TOKEN_KEY;
export const IS_PRODUCTION = env.VITE_APP_ENV === "production";
export const USE_MOCK_API = env.VITE_USE_MOCK_API;

// Flag untuk dicek di hooks/komponen simulation sebelum coba connect WS
export const IS_WS_CONFIGURED = Boolean(WS_URL);