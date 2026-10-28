import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";

import { encodeNpy } from "@/test/npy_writer";

import { TilePage } from "./Tile";

const PLAN = (id: string, arrangement: string, coverage: number) => ({
  id,
  arrangement,
  coverage,
  trees: 16,
  cost_usd: 2_000_000,
  cost_m: 2.0,
  exposure_drop: 1.5,
  people: 112,
  efficiency: 14.4,
});

const REPORT = {
  city: "ahmedabad",
  tile: "t43N_249_2547",
  name: "Ahmedabad",
  stages: { bundle: true, baseline: true, physics: true, model: false, results: false },
  facts: {
    key: "ahmedabad",
    name: "Ahmedabad",
    design_day: "2025-05-20",
    tier: "A",
    buildings: 1234,
    built_fraction: 0.25,
    canopy: 0.1,
    population_2020: 512,
    lat: 23,
    lon: 72.5,
    urban_centre: { id: 6143, name: "Ahmedabad", koppen: "BSh", income: "LM", population_2025: 7898650, tiles: 365 },
    sources: { buildings: "OpenStreetMap", terrain: "Copernicus DEM" },
  },
  baseline: { exposure: 50, at_risk: 512 },
  met: Array.from({ length: 24 }, (_, hour) => ({ hour, air_c: 30 + hour / 10, solar: hour > 6 ? 800 : 0 })),
  hourly: Array.from({ length: 24 }, (_, hour) => ({ hour, median: 30 + hour, max: 30 + hour })),
  plans: [PLAN("clustered_0101", "clustered", 0.0625), PLAN("random_uniform_0201", "scattered", 0.03125)],
  physics: { designs: 4, engine_minutes: 18, seconds_per_design_min: 90, seconds_per_design_max: 360 },
};

function fetchFor(report: object) {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith("/report")) return Response.json(report);
    if (url.includes("/fields/hours")) {
      return new Response(encodeNpy(Array.from({ length: 24 * 4 }, (_, i) => 30 + Math.floor(i / 4)), [24, 2, 2], "<f4"));
    }
    if (url.includes("/fields/placement")) return new Response(encodeNpy([0, 1, 1, 0], [2, 2], "|b1"));
    if (url.includes("/fields/cooling")) return new Response(encodeNpy([0, 1, 1.5, 0], [2, 2], "<f4"));
    return new Response("not found", { status: 404 });
  });
}

function renderTile() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/cities/ahmedabad/tiles/t43N_249_2547"]}>
        <Routes>
          <Route path="cities/:city/tiles/:tile" element={<TilePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

it("shows the facts, the day's heat, the plans and what the engine did", async () => {
  vi.stubGlobal("fetch", fetchFor(REPORT));
  renderTile();
  expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("Ahmedabad");
  expect(screen.getByText("Input quality tier").nextElementSibling).toHaveTextContent("A");
  expect(await screen.findByRole("img", { name: /Mean radiant temperature at 15:00/ })).toBeInTheDocument();
  expect(screen.getByText(/median 45.0 C, peak 45.0 C/)).toBeInTheDocument();
  expect(screen.getAllByRole("row", { selected: true })).toHaveLength(1);
  expect(await screen.findByRole("img", { name: /Placement of clustered_0101/ })).toBeInTheDocument();
  expect(screen.getByText(/4/, { selector: "strong" })).toBeInTheDocument();
});

it("tells a built tile without physics what to run", async () => {
  vi.stubGlobal("fetch", fetchFor({ ...REPORT, baseline: null, met: [], hourly: [], plans: [], physics: null, stages: { ...REPORT.stages, baseline: false, physics: false } }));
  renderTile();
  expect(await screen.findByText(/no baseline physics yet/)).toBeInTheDocument();
  expect(screen.getByText("sdc simulate baseline ahmedabad --tile t43N_249_2547")).toBeInTheDocument();
});
