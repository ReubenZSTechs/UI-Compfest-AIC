import { z } from "zod";

const envSchema = z.object({
  VITE_API_BASE_URL: z.string().optional(),
  VITE_API_URL: z.string().optional(),
  VITE_API_VERSION: z.string().default("v1"),
  VITE_AUTH_TOKEN_KEY: z.string().default("auth_token"),
  VITE_APP_ENV: z.enum(["development", "staging", "production"]).default("development"),
});

type EnvSchema = z.infer<typeof envSchema>;

function validateEnv(): EnvSchema {
  const parsed = envSchema.safeParse(import.meta.env);

  if (!parsed.success) {
    const formatted = parsed.error.flatten().fieldErrors;
    throw new Error(
      `Konfigurasi environment gagal divalidasi:\n${Object.entries(formatted)
        .map(([key, errors]) => `  - ${key}: ${errors?.join(", ")}`)
        .join("\n")}`
    );
  }

  return parsed.data;
}

export const env = validateEnv();

const resolvedRoot = env.VITE_API_BASE_URL ?? env.VITE_API_URL ?? "/api";

export const API_ROOT_URL = resolvedRoot.replace(/\/+$/, "");
export const API_BASE_URL = `${API_ROOT_URL}/${env.VITE_API_VERSION}`;
export const AUTH_TOKEN_KEY = env.VITE_AUTH_TOKEN_KEY;
export const IS_PRODUCTION = env.VITE_APP_ENV === "production";