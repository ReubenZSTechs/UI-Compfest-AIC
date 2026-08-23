import { RouterProvider } from "react-router-dom";
import { AppProviders } from "@/app/providers/AppProviders";
import { router } from "@/app/router/routes";
import { ToastHost } from "@/components/feedback/ToastHost";

export default function App() {
  return (
    <AppProviders>
      <ToastHost />
      <RouterProvider router={router} />
    </AppProviders>
  );
}