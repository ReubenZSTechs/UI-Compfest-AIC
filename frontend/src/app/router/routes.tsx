import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { ProtectedRoute } from "@/app/router/ProtectedRoute";

// Lazy load atau import langsung halaman
import { DocumentParserPage } from "@/pages/Documentparserpage";
import { DigitalTwinPage } from "@/pages/DigitalTwinPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { HumanFactorsPage } from "@/pages/HumanFactorsPage";
import { SimulationPage } from "@/pages/SimulationPage";
import { LoginPage } from "@/pages/LoginPage";
import { NotFoundPage } from "@/pages/NotFoundPage";

// 1. Centralized Route Constants (Maintainable & Type-Safe)
export const ROUTES = {
  LOGIN: "/login",
  PARSER: "/parser",
  DIGITAL_TWIN: "/digital-twin",
  DASHBOARD: "/dashboard",
  SIMULATION: "/simulation",
  HUMAN_FACTORS: "/human-factors",
} as const;

// 2. Router Configuration
export const router = createBrowserRouter([
  {
    path: ROUTES.LOGIN,
    element: <LoginPage />,
  },
  {
    // Mengamankan halaman yang butuh otentikasi
    element: <ProtectedRoute />, 
    children: [
      {
        // Membungkus halaman utama dengan Layout (Sidebar & Topbar)
        element: <AppShell />, 
        children: [
          {
            path: "/",
            element: <Navigate to={ROUTES.PARSER} replace />,
          },
          {
            path: ROUTES.PARSER,
            element: <DocumentParserPage />,
          },
          {
            path: ROUTES.DIGITAL_TWIN,
            element: <DigitalTwinPage />,
          },
          {
            path: ROUTES.DASHBOARD,
            element: <DashboardPage />,
          },
          {
            path: ROUTES.SIMULATION,
            element: <SimulationPage />,
          },
          {
            path: ROUTES.HUMAN_FACTORS,
            element: <HumanFactorsPage />,
          },
        ],
      },
    ],
  },
  {
    path: "*",
    element: <NotFoundPage />,
  },
]);