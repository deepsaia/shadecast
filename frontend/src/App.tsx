import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";

import { Shell } from "@/components/Shell";
import { CitiesPage } from "@/pages/Cities";
import { CityRedirect } from "@/pages/CityRedirect";
import { TilePage } from "@/pages/Tile";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Shell />}>
            <Route index element={<CitiesPage />} />
            <Route path="cities" element={<Navigate to="/" replace />} />
            <Route path="cities/:city" element={<CityRedirect />} />
            <Route path="cities/:city/tiles/:tile" element={<TilePage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
