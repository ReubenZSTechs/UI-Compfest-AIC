import { ReactNode } from "react";
import { QueryProvider } from "./QueryProvider";
// import { ThemeProvider } from "./ThemeProvider"; // Aktifkan jika digunakan

interface AppProvidersProps {
  children: ReactNode;
}

export function AppProviders({ children }: AppProvidersProps) {
  return (
    <QueryProvider>
      {/* <ThemeProvider>{children}</ThemeProvider> */}
      {children}
    </QueryProvider>
  );
}