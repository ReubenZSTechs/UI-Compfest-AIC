import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryProvider } from "@/app/providers/QueryProvider";
import App from "./App.tsx";
import "./styles/globals.css"; // sesuaikan kalau path CSS-mu beda

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryProvider>
      <App />
    </QueryProvider>
  </StrictMode>
);