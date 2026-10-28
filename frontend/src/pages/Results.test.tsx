import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";

import { ResultsPage } from "./Results";

const PLAN = (id: string, arrangement: string, coverage: number, efficiency: number) => ({
  id,
  arrangement,
  coverage,
  trees: 10,
  cost_usd: 1_000_000,
  cost_m: 1.0,
  exposure_drop: 0.5,
  people: 50,
  efficiency,
});

const CITY = {
  key: "ahmedabad",
  name: "Ahmedabad",
  tile: "t43N_249_2547",
  facts: { key: "ahmedabad", name: "Ahmedabad", design_day: null, tier: "A", buildings: null, built_fraction: 0.3, canopy: 0.1, population_2020: 1000, lat: null, lon: null, urban_centre: null, sources: {} },
  baseline: { exposure: 55, at_risk: 400 },
  plans: [PLAN("clustered_0101", "clustered", 0.026, 14.4), PLAN("random_uniform_0201", "scattered", 0.026, 56.5)],
  physics: { designs: 17, engine_minutes: 120, seconds_per_design_min: 300, seconds_per_design_max: 600 },
  matched: { clustered: PLAN("clustered_0101", "clustered", 0.026, 14.4), scattered: PLAN("random_uniform_0201", "scattered", 0.026, 56.5), ratio: 3.92 },
};

const RESULTS = {
  threshold_C: 45,
  as_of: "2026-10-26",
  cities: [CITY],
  totals: { cities: 1, plans: 2, budget_min_m: 1.0, budget_max_m: 1.0 },
  arrangement: { ratios: { ahmedabad: 3.92 }, cities_compared: 1, scattered_wins: 1, ratio_min: 3.92, ratio_max: 3.92 },
  ranking: { rows: [{ key: "ahmedabad", name: "Ahmedabad", scattered_per_1k: 56.5, clustered_per_1k: 14.4, gain: 3.92, canopy: 0.1, built_fraction: 0.3 }], spread: null },
  factorial: null,
  targeting: null,
  channel: null,
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ResultsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

it("draws one facet, the matched comparison, the ranking and every plan for one tile", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(RESULTS)));
  renderPage();
  expect(await screen.findByText(/simulated with real physics across 1 tile/)).toBeInTheDocument();
  expect(screen.getByText(/Scattered planting delivered more cooling per dollar than clustered planting in every tile compared, by 3.92 to 3.92 times/)).toBeInTheDocument();
  expect(screen.getByText("One tile so far; the comparison needs a second.", { exact: false })).toBeInTheDocument();
  expect(screen.getAllByRole("link", { name: "Ahmedabad" })).toHaveLength(2);
  expect(screen.queryByText("Which measure buys the most")).toBeNull();
});

it("invites a run when nothing has physics", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json({ ...RESULTS, cities: [], totals: { cities: 0, plans: 0, budget_min_m: null, budget_max_m: null }, arrangement: { ratios: {}, cities_compared: 0, scattered_wins: 0, ratio_min: null, ratio_max: null }, ranking: { rows: [], spread: null } })));
  renderPage();
  expect(await screen.findByText(/No tile has simulated physics yet/)).toBeInTheDocument();
});
