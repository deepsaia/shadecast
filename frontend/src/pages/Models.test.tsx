import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";

import { ModelsPage } from "./Models";

const CHANNELS = [{ key: "treeshade", label: "tree shade", measure: "trees", unit: "trees" }];

const CITY = (key: string, ucdb_id: number, name: string, physics: number, model: number) => ({
  key,
  ucdb_id,
  name,
  country: "",
  region: "",
  koppen: null,
  income: null,
  population_2025: 1,
  in_wri: false,
  stages: { tiles: 10, bundle: 1, baseline: 1, physics, model, results: 0 },
});

const CITIES = [
  CITY("ahmedabad", 6143, "Ahmedabad", 1, 1),
  CITY("lagos", 1289, "Lagos", 1, 0),
  CITY("london", 5816, "London", 0, 0),
];

const MODELS = [
  {
    id: "response-unet-ahmedabad-20261023T121739",
    urban_centres: [6143],
    created: "2026-10-23T12:17:39+00:00",
    channel: "treeshade",
    tile: "t43N_249_2547",
    path: "/data/tiles/6143/t43N_249_2547/models/response-unet-ahmedabad-20261023T121739",
    has_weights: true,
    has_manifest: true,
    skill: 0.735,
    tiles_trained: 1,
    manifest: {},
  },
];

function answer(input: RequestInfo | URL) {
  const url = String(input);
  if (url.endsWith("/channels")) return Response.json(CHANNELS);
  if (url.endsWith("/models")) return Response.json(MODELS);
  return Response.json(CITIES);
}

afterEach(() => vi.unstubAllGlobals());

it("lists the trained models and names the cities with physics that have none", async () => {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => answer(input)));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ModelsPage />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("0.735")).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "Ahmedabad" })).toBeInTheDocument();
  expect(screen.getByText(/One city has simulated physics and no model/)).toBeInTheDocument();
  expect(screen.getByText("sdc surrogate treeshade train lagos")).toBeInTheDocument();
  expect(screen.queryByText("London")).toBeNull();
});
