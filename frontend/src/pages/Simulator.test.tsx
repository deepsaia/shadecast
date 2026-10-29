import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";

import { FakeMap, fakeMaplibre } from "@/test/fake_maplibre";
import { encodeNpy } from "@/test/npy_writer";

import { SimulatorPage } from "./Simulator";

vi.mock("maplibre-gl", () => ({ default: fakeMaplibre, ...fakeMaplibre }));
vi.mock("maplibre-gl/dist/maplibre-gl.css", () => ({}));
vi.mock("maplibre-gl/dist/maplibre-gl-worker.mjs?url", () => ({ default: "/assets/worker.mjs" }));

const STAGES = (model: boolean) => ({ bundle: true, baseline: model, physics: model, model, results: false });

const CITIES = [
  {
    key: "london",
    ucdb_id: 5816,
    name: "London",
    country: "United Kingdom",
    region: "Europe",
    koppen: "Cfb",
    income: "H",
    population_2025: 10408332,
    in_wri: true,
    stages: { tiles: 1649, bundle: 1, baseline: 0, physics: 0, model: 0, results: 0 },
  },
  {
    key: "ahmedabad",
    ucdb_id: 6143,
    name: "Ahmedabad",
    country: "India",
    region: "South Asia",
    koppen: "BSh",
    income: "LM",
    population_2025: 7898650,
    in_wri: false,
    stages: { tiles: 365, bundle: 2, baseline: 1, physics: 1, model: 1, results: 0 },
  },
];

const GRID = {
  columns: ["west", "south", "east", "north", "density_per_km2", "residents", "modelled"],
  ids: ["t43N_249_2547", "t43N_250_2547"],
  cells: [
    [72.57, 23.13, 72.58, 23.139, 101644, 101644, 1],
    [72.58, 23.13, 72.59, 23.139, 40000, 40000, 0],
  ],
  described: 2,
};

const TILES = {
  ahmedabad: [
    { id: "t43N_249_2547", population_2020: 101644, density_2020_per_km2: 101644, stages: STAGES(true) },
    { id: "t43N_250_2547", population_2020: 40000, density_2020_per_km2: 40000, stages: STAGES(false) },
  ],
  london: [{ id: "t30N_710_5714", population_2020: 25867, density_2020_per_km2: 25867, stages: STAGES(false) }],
};

const REPORT = {
  city: "ahmedabad",
  tile: "t43N_249_2547",
  name: "Ahmedabad",
  stages: STAGES(true),
  facts: {
    key: "ahmedabad",
    name: "Ahmedabad",
    design_day: "2025-05-20",
    tier: "A",
    buildings: 1234,
    built_fraction: 0.25,
    canopy: 0.1,
    population_2020: 101644,
    sources: { buildings: "GlobalBuildingAtlas" },
  },
  baseline: { exposure: 58.68, at_risk: 78568 },
  met: Array.from({ length: 24 }, (_, hour) => ({ hour, air_c: 30 + hour / 10, solar: hour > 6 ? 800 : 0 })),
  hourly: Array.from({ length: 24 }, (_, hour) => ({ hour, median: 30 + hour, max: 30 + hour })),
  plans: [
    { id: "clustered_0105", arrangement: "clustered", coverage: 0.026, trees: 26008, cost_usd: 2_280_000, cost_m: 2.28, exposure_drop: 0.7, people: 1500, efficiency: 20 },
  ],
  physics: null,
};

const OUTCOME = {
  city: "ahmedabad",
  tile: "t43N_249_2547",
  model_id: "response-unet-ahmedabad-20261028T154005",
  kind: "tree",
  arrangement: "clustered",
  coverage: 0.05,
  tile_fraction: 0.034,
  trees: 34028,
  cost_usd: 2_980_000,
  unit_cost: 40,
  maintenance: 0.08,
  threshold: 45,
  baseline_exposure: 58.68,
  baseline_at_risk: 78568,
  exposure_drop: 3.06,
  excess_removed: 307_032,
  people: 1258,
  equity_gap_change: -0.74,
  efficiency: 102.99,
  surrogate_seconds: 0.54,
};

const POINT = (drop: number, people: number[]) => ({
  exposure_drop: drop,
  equity_gap_change: -0.2,
  excess_removed: people.map((count) => count * 10),
  people,
});

const SWEEP = {
  model_id: "response-unet-ahmedabad-20261028T154005",
  created: "2026-10-29T12:00:00+00:00",
  coverages: [0.05, 0.3],
  thresholds: [45, 49],
  curves: ["clustered", "scattered", "corridor"].map((arrangement) => ({
    arrangement,
    points: [POINT(1, [100, 300]), POINT(3, [400, 900])],
  })),
  designs: [{ id: "clustered_0105", arrangement: "clustered", coverage: 0.052, point: POINT(0.7, [120, 320]) }],
  seconds: 25,
  fresh: true,
};

function fetchFor(urls: string[]) {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    urls.push(url);
    if (url.endsWith("/cities")) return Response.json(CITIES);
    if (url.endsWith("/cities/ahmedabad/tiles")) return Response.json(TILES.ahmedabad);
    if (url.endsWith("/cities/london/tiles")) return Response.json(TILES.london);
    if (url.endsWith("/grid")) return Response.json(GRID);
    if (url.endsWith("/basemap")) return Response.json({ source: "openfreemap", style_url: "https://example.test/style", attribution: "OpenFreeMap" });
    if (url.endsWith("/sweep")) return Response.json(SWEEP);
    if (url.endsWith("/report")) return Response.json(REPORT);
    if (url.includes("/scenario/field")) return new Response(encodeNpy([0, 1, 0.5, 0, 0, 1, 1, 0], [2, 2, 2], "<f4"));
    if (url.includes("/scenario?")) return Response.json(OUTCOME);
    if (url.includes("/fields/hours")) {
      return new Response(encodeNpy(Array.from({ length: 24 * 4 }, (_, i) => 30 + Math.floor(i / 4)), [24, 2, 2], "<f4"));
    }
    return new Response("not found", { status: 404 });
  });
}

function renderSimulator(path = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route index element={<SimulatorPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());
beforeEach(() => {
  FakeMap.instances.length = 0;
  window.localStorage.clear();
});

it("opens on the first city with a model and its densest tile, with the outcomes row on top", async () => {
  const urls: string[] = [];
  vi.stubGlobal("fetch", fetchFor(urls));
  renderSimulator();
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Heatwave Resilient Cities");
  await waitFor(() => expect(screen.getByRole("combobox", { name: "City" })).toHaveTextContent("Ahmedabad, India"));
  await waitFor(() => expect(screen.getByRole("combobox", { name: "Tiles" })).toHaveTextContent("t43N_249_2547"));
  const outcomes = await screen.findByRole("region", { name: "Outcomes" });
  expect(within(outcomes).getByText("3.06")).toBeInTheDocument();
  expect(within(outcomes).getByText(/^3,?07,032$/)).toBeInTheDocument();
  expect(within(outcomes).getByText(/1\.6% of the 78,568 above it today/)).toBeInTheDocument();
  expect(within(outcomes).getByText("People moved below 45 C")).toBeInTheDocument();
  expect(screen.getByText(/The red mark is 30% of the plantable ground/)).toBeInTheDocument();
  expect(screen.getByRole("slider", { name: "Stress threshold" })).toHaveAttribute("aria-valuenow", "45");
  fireEvent.focus(screen.getByRole("button", { name: "How this is counted" }));
  expect(await screen.findByText(/spread each person over the open ground/)).toBeInTheDocument();
  expect(urls.some((url) => url.includes("/tiles/t43N_249_2547/scenario?arrangement=clustered&coverage=0.05"))).toBe(true);
  expect(screen.getByRole("heading", { level: 2, name: /^Policy/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Pavement/ })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Trees" })).toHaveAttribute("aria-pressed", "true");
  const designs = screen.getByRole("group", { name: "Design" });
  expect(within(designs).getAllByRole("button").map((button) => button.textContent)).toEqual(["clustered", "scattered", "corridor"]);
  expect(screen.getByRole("checkbox", { name: "Move the two together" })).toHaveAttribute("data-state", "checked");
  expect(screen.getByRole("button", { name: /Design day/ })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: /Other days/ })).toBeDisabled();
  expect(await screen.findByText("What the tile is")).toBeInTheDocument();
  expect(screen.getByText("The day's heat")).toBeInTheDocument();
  expect(screen.getByText("Input quality tier").nextElementSibling).toHaveTextContent("A");
  expect(screen.getByRole("application", { name: "City map" })).toBeInTheDocument();
  await waitFor(() => expect(FakeMap.instances[0]?.filters.get("grid-focused")).toEqual(["==", ["get", "id"], "t43N_249_2547"]));
});

it("lets a person pick a design and another city from the dropdown", async () => {
  const urls: string[] = [];
  vi.stubGlobal("fetch", fetchFor(urls));
  renderSimulator();
  await screen.findByRole("region", { name: "Outcomes" });
  fireEvent.click(within(screen.getByRole("group", { name: "Design" })).getByRole("button", { name: "corridor" }));
  await waitFor(() => expect(urls.some((url) => url.includes("arrangement=corridor&coverage=0.05"))).toBe(true));
  fireEvent.click(screen.getByRole("combobox", { name: "City" }));
  const list = await screen.findByRole("listbox", { name: "City" });
  expect(within(list).getAllByRole("option")[0]).toHaveTextContent("Ahmedabad");
  fireEvent.change(screen.getByRole("searchbox", { name: "Search city" }), { target: { value: "lon" } });
  fireEvent.click(within(list).getByRole("button", { name: /London/ }));
  expect(await screen.findByText("sdc surrogate treeshade train london")).toBeInTheDocument();
});

it("reprices the scenario from the assumptions", async () => {
  const urls: string[] = [];
  vi.stubGlobal("fetch", fetchFor(urls));
  renderSimulator("/?city=ahmedabad");
  await screen.findByRole("region", { name: "Outcomes" });
  expect(screen.getByText(/priced at 40 USD per m², 8% a year/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Unit cost, USD per square metre"), { target: { value: "80" } });
  fireEvent.change(screen.getByLabelText("Maintenance, percent of capital a year"), { target: { value: "5" } });
  await waitFor(() =>
    expect(urls.some((url) => url.includes("coverage=0.05&unit_cost=80&maintenance=0.05&threshold=45"))).toBe(true),
  );
});

it("remembers the threshold a person chose across a reload", async () => {
  window.localStorage.setItem("shadecast.threshold", "50");
  const urls: string[] = [];
  vi.stubGlobal("fetch", fetchFor(urls));
  renderSimulator("/?city=ahmedabad");
  await screen.findByRole("region", { name: "Outcomes" });
  expect(screen.getByRole("slider", { name: "Stress threshold" })).toHaveAttribute("aria-valuenow", "50");
  await waitFor(() => expect(urls.some((url) => url.includes("coverage=0.05&threshold=50"))).toBe(true));
});

it("offers the tile presets and lists tiles without a model as not selectable", async () => {
  vi.stubGlobal("fetch", fetchFor([]));
  renderSimulator("/?city=ahmedabad");
  await screen.findByRole("region", { name: "Outcomes" });
  fireEvent.click(screen.getByRole("button", { name: "all with a model" }));
  expect(screen.getByRole("combobox", { name: "Tiles" })).toHaveTextContent("t43N_249_2547");
  fireEvent.click(screen.getByRole("combobox", { name: "Tiles" }));
  const list = await screen.findByRole("listbox", { name: "Tiles" });
  expect(within(list).getByRole("button", { name: /t43N_250_2547/ })).toBeDisabled();
  expect(within(list).getByText("no model yet")).toBeInTheDocument();
});

it("shows the curves instead of the numbers when asked, and remembers the choice", async () => {
  const urls: string[] = [];
  vi.stubGlobal("fetch", fetchFor(urls));
  renderSimulator("/?city=ahmedabad");
  await screen.findByRole("region", { name: "Outcomes" });
  expect(urls.some((url) => url.endsWith("/sweep"))).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "curves" }));
  const curves = await screen.findByRole("region", { name: "Outcome curves" });
  expect(within(curves).getByText("Degree-hours removed")).toBeInTheDocument();
  expect(within(curves).getByText(/3.06 at 5.0%/)).toBeInTheDocument();
  expect(urls.some((url) => url.endsWith("/tiles/t43N_249_2547/sweep"))).toBe(true);
  expect(window.localStorage.getItem("shadecast.outcomes-view")).toBe("curves");
  fireEvent.click(screen.getByRole("button", { name: "numbers" }));
  expect(await screen.findByRole("region", { name: "Outcomes" })).toBeInTheDocument();
});
