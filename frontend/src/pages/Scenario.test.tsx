import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";

import { encodeNpy } from "@/test/npy_writer";

import { ScenarioPage } from "./Scenario";

const REPORT = {
  city: "ahmedabad",
  tile: "t43N_249_2547",
  name: "Ahmedabad",
  stages: { bundle: true, baseline: true, physics: true, model: true, results: false },
  facts: { key: "ahmedabad", name: "Ahmedabad", tier: "A", buildings: 1, built_fraction: 0.25, canopy: 0.1, sources: {} },
  baseline: { exposure: 58.68, at_risk: 78568 },
  met: [],
  hourly: [],
  plans: [
    {
      id: "clustered_0105",
      arrangement: "clustered",
      coverage: 0.026,
      trees: 26008,
      cost_usd: 2_280_000,
      cost_m: 2.28,
      exposure_drop: 0.7,
      people: 1500,
      efficiency: 20,
    },
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
  baseline_exposure: 58.68,
  baseline_at_risk: 78568,
  exposure_drop: 3.06,
  excess_removed: 307_032,
  people: 1258,
  equity_gap_change: -0.74,
  efficiency: 102.99,
  surrogate_seconds: 0.54,
};

const MISSING = {
  error: "urban centre 6143 has no model yet; run 'sdc surrogate treeshade train ahmedabad' first",
  kind: "MissingStage",
  stage: "model",
  tile: "urban centre 6143",
  command: "sdc surrogate treeshade train ahmedabad",
};

function fetchFor(scenario: () => Response, urls: string[]) {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    urls.push(url);
    if (url.endsWith("/report")) return Response.json(REPORT);
    if (url.includes("/scenario/field")) return new Response(encodeNpy([0, 1, 0.5, 0, 0, 1, 1, 0], [2, 2, 2], "<f4"));
    if (url.includes("/scenario")) return scenario();
    return new Response("not found", { status: 404 });
  });
}

function renderScenario() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/cities/ahmedabad/tiles/t43N_249_2547/scenario"]}>
        <Routes>
          <Route path="cities/:city/tiles/:tile/scenario" element={<ScenarioPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

it("answers the levers with the outcomes, the fields and the chart, trees live and the rest coming soon", async () => {
  const urls: string[] = [];
  vi.stubGlobal("fetch", fetchFor(() => Response.json(OUTCOME), urls));
  renderScenario();
  expect(await screen.findByRole("heading", { level: 1, name: /Ahmedabad/ })).toHaveTextContent("tile t43N_249_2547");
  expect(await screen.findByText("Exposure drop")).toBeInTheDocument();
  expect(screen.getByText("3.06")).toBeInTheDocument();
  expect(screen.getByText(/^3,?07,032$/)).toBeInTheDocument();
  expect(screen.getByText(/34,028 trees, 2.98 M USD/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Shade structures/ })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Trees" })).toHaveAttribute("aria-pressed", "true");
  expect(await screen.findByRole("img", { name: "Placement of this scenario" })).toBeInTheDocument();
  expect(screen.getByText("Against the physics")).toBeInTheDocument();
  expect(urls.some((url) => url.includes("/scenario?arrangement=clustered&coverage=0.05"))).toBe(true);
  expect(urls.some((url) => url.includes("/scenario/field?arrangement=clustered&coverage=0.05&size=384"))).toBe(true);
});

it("asks again with the arrangement a person chooses", async () => {
  const urls: string[] = [];
  vi.stubGlobal("fetch", fetchFor(() => Response.json(OUTCOME), urls));
  renderScenario();
  await screen.findByText("Exposure drop");
  fireEvent.click(screen.getByRole("button", { name: /scattered/ }));
  await waitFor(() => expect(urls.some((url) => url.includes("arrangement=scattered&coverage=0.05"))).toBe(true));
  expect(screen.getByRole("button", { name: /scattered/ })).toHaveAttribute("aria-pressed", "true");
});

it("tells a tile without a model what to run", async () => {
  vi.stubGlobal(
    "fetch",
    fetchFor(() => Response.json(MISSING, { status: 404 }), []),
  );
  renderScenario();
  expect(await screen.findByText(/no trained surrogate yet/)).toBeInTheDocument();
  expect(screen.getByText("sdc surrogate treeshade train ahmedabad")).toBeInTheDocument();
});
