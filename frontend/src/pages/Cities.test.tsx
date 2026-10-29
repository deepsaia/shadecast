import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";

import { CitiesPage } from "./Cities";

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
    stages: { tiles: 1649, bundle: 0, baseline: 0, physics: 0, model: 0, results: 0 },
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
    stages: { tiles: 365, bundle: 3, baseline: 2, physics: 1, model: 1, results: 0 },
  },
];

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <CitiesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

const GRID = {
  columns: ["west", "south", "east", "north", "density_per_km2", "residents", "modelled"],
  ids: ["t43N_249_2547", "t43N_250_2547"],
  cells: [
    [72.57, 23.13, 72.58, 23.139, 9000, 9000, 1],
    [72.58, 23.13, 72.59, 23.139, 3000, 3000, 0],
  ],
  described: 2,
};

it("lists every city with its stages, links only the built ones and draws their grids", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) =>
      String(input).endsWith("/grid") ? Response.json(GRID) : Response.json(CITIES),
    ),
  );
  renderPage();
  expect(await screen.findByRole("link", { name: "Ahmedabad" })).toHaveAttribute("href", "/cities/ahmedabad");
  const names = screen.getAllByRole("row").slice(1).map((row) => row.querySelector("td")?.textContent ?? "");
  expect(names[0]).toMatch(/^Ahmedabad/);
  expect(names[1]).toMatch(/^London/);
  expect(screen.queryByRole("link", { name: "London" })).toBeNull();
  expect(screen.getByText("3 of 365")).toBeInTheDocument();
  expect(screen.getByText("none yet")).toBeInTheDocument();
  expect(screen.getByRole("img", { name: /3 of 365 tiles built, 1 with physics, 1 with a model/ })).toBeInTheDocument();
  expect(screen.getByText("1 of 2 cities have at least one tile built.")).toBeInTheDocument();
  expect(await screen.findByRole("img", { name: "2 tiles, 1 with a model" })).toBeInTheDocument();
});

it("says the server did not answer and how to start it", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response("down", { status: 503 })));
  renderPage();
  expect(await screen.findByRole("alert")).toHaveTextContent("sdc serve");
});
