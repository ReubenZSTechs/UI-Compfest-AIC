import { Navigate, Outlet } from "react-router-dom";
import { ROUTES } from "./routes";
// import { useAuth } from "@/features/auth/hooks/useAuth";

export function ProtectedRoute() {
  // Contoh hook auth (sesuaikan dengan state management Anda)
  // const { isAuthenticated, isLoading } = useAuth();
  const isAuthenticated = true; // Temporary mock

  if (!isAuthenticated) {
    return <Navigate to={ROUTES.LOGIN} replace />;
  }

  return <Outlet />;
}