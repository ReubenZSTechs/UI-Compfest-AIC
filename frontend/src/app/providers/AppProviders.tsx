import type { ReactNode } from "react";
import { QueryProvider } from "./QueryProvider";
import { ToastHost } from "@/components/feedback/ToastHost";

interface AppProvidersProps {
  children: ReactNode;
}

/** Wraps the app with the shared query client and the global toast host. */
export function AppProviders({ children }: AppProvidersProps) {
  return (
    <QueryProvider>
      {children}
      <ToastHost />
    </QueryProvider>
  );
}
