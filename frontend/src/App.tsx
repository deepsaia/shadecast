import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router";

import { Shell } from "@/components/Shell";
import { CitiesPage } from "@/pages/Cities";
import { CityRedirect } from "@/pages/CityRedirect";
import { FindingsPage } from "@/pages/Findings";
import { ModelsPage } from "@/pages/Models";
import { ReferencesPage } from "@/pages/References";
import { ResultsPage } from "@/pages/Results";
import { SimulatorPage } from "@/pages/Simulator";
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
            <Route index element={<SimulatorPage />} />
            <Route path="cities" element={<CitiesPage />} />
            <Route path="cities/:city" element={<CityRedirect />} />
            <Route path="cities/:city/tiles/:tile" element={<TilePage />} />
            <Route path="results" element={<ResultsPage />} />
            <Route path="models" element={<ModelsPage />} />
            <Route path="findings" element={<FindingsPage />} />
            <Route path="references" element={<ReferencesPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
