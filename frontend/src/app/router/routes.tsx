import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { ProtectedRoute } from "@/app/router/ProtectedRoute";
import { LandingPage } from "@/pages/LandingPage";
import { IntroPage } from "@/pages/IntroPage";
import { CanvasPage } from "@/pages/Canvaspage";
import { AgentPage } from "@/pages/AgentPage";
import { RecommendationsPage } from "@/pages/RecommendationsPage";
import { ExecutionPage } from "@/pages/ExecutionPage";
import { DocumentParserPage } from "@/pages/Documentparserpage";
import { DigitalTwinPage } from "@/pages/DigitalTwinPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { LoginPage } from "@/pages/LoginPage";
import { NotFoundPage } from "@/pages/NotFoundPage";

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
  PARSER: "/parser",
  DIGITAL_TWIN: "/digital-twin",
  DASHBOARD: "/dashboard",
} as const;

export const router = createBrowserRouter([
  {
    path: ROUTES.LOGIN,
    element: <LoginPage />,
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        path: ROUTES.LANDING,
        element: <LandingPage />,
      },
      {
        path: ROUTES.LANDING_ALT,
        element: <LandingPage />,
      },
      {
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
        element: <Navigate to={ROUTES.DASHBOARD} replace />,
      },
      {
        path: "/recommendation/:cardId",
        element: <Navigate to={ROUTES.DASHBOARD} replace />,
      },
      {
        path: "/rec_1",
        element: <ExecutionPage />,
      },
      {
        element: <AppShell />,
        children: [
          {
            path: ROUTES.INTRO,
            element: <IntroPage />,
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
        ],
      },
    ],
  },
  {
    path: "*",
    element: <NotFoundPage />,
  },
]);
