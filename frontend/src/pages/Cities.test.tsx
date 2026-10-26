import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";

import { CitiesPage } from "./Cities";

const CITIES = [
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

it("lists every city with its stages and links only the built ones", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(CITIES)));
  renderPage();
  expect(await screen.findByRole("link", { name: "Ahmedabad" })).toHaveAttribute("href", "/cities/ahmedabad");
  expect(screen.queryByRole("link", { name: "London" })).toBeNull();
  expect(screen.getByText("3 of 365")).toBeInTheDocument();
  expect(screen.getByText("none yet")).toBeInTheDocument();
  expect(screen.getByRole("img", { name: /3 of 365 tiles built, 1 with physics, 1 with a model/ })).toBeInTheDocument();
  expect(screen.getByText("1 of 2 cities have at least one tile built.")).toBeInTheDocument();
});

it("says the server did not answer and how to start it", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response("down", { status: 503 })));
  renderPage();
  expect(await screen.findByRole("alert")).toHaveTextContent("sdc serve");
});
