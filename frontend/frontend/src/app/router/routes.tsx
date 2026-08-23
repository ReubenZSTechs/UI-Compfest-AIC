import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { ProtectedRoute } from "@/app/router/ProtectedRoute";
import { LandingPage } from "@/pages/LandingPage";
import { IntroPage } from "@/pages/IntroPage";
import { CanvasPage } from "@/pages/Canvaspage";
import { AgentPage } from "@/pages/AgentPage";
import { RecommendationsPage } from "@/pages/RecommendationsPage";
import { ExecutionPage } from "@/pages/ExecutionPage";

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
  LANDING: "/",
  LANDING_ALT: "/landing",
  LOGIN: "/login",
  INTRO: "/intro",
  CANVAS: "/canvas",
  LIVE: "/live",
  AGENT: "/agent",
  RECOMMENDATIONS: "/project/:projectId/recommendations",
  RECOMMENDATION_DETAIL: "/project/:projectId/recommendation/:cardId",
  ANALYTICS: "/project/:projectId/analytics",
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
    // Mengamankan halaman yang membutuhkan otentikasi
    element: <ProtectedRoute />,
    children: [
      {
        path: "/",
        element: <LandingPage />,
      },
      {
        path: "/landing",
        element: <LandingPage />,
      },
      {
        // Alias lama: "/canvas" dialihkan ke halaman Live.
        path: ROUTES.CANVAS,
        element: <Navigate to={ROUTES.LIVE} replace />,
      },
      {
        path: ROUTES.LIVE,
        element: <CanvasPage />,
      },
      {
        path: ROUTES.AGENT,
        element: <AgentPage />,
      },
      {
        path: ROUTES.RECOMMENDATIONS,
        element: <RecommendationsPage />,
      },
      {
        path: ROUTES.RECOMMENDATION_DETAIL,
        element: <ExecutionPage />,
      },
      {
        path: "/recommendations",
        element: <Navigate to="/dashboard" replace />,
      },
      {
        path: "/recommendation/:cardId",
        element: <Navigate to="/dashboard" replace />,
      },
      {
        path: "/rec_1",
        element: <ExecutionPage />,
      },
      {
        path: "/rec_2",
        element: <ExecutionPage />,
      },
      {
        path: "/rec_3",
        element: <ExecutionPage />,
      },
      {
        path: ROUTES.ANALYTICS,
        element: <ExecutionPage />,
      },
      {
        element: <AppShell />,
        children: [
          {
            path: ROUTES.INTRO,
            element: <IntroPage />, // Halaman Introduction
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
