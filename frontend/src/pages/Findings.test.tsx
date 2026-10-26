import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";

import { FindingsPage } from "./Findings";

const FINDINGS = {
  surrogate: { status: "done", skill: 0.7348, ranking_spearman: 1, aggregate_error: 0.0297, engine_seconds: 162, surrogate_seconds: 1.0, speedup: 161.9, transfer: [{ cities: 1, skill: 0.4, mae_C: 0.5 }, { cities: 2, skill: 0.6, mae_C: 0.4 }], transfer_verdict: "more cities help" },
  factorial: { status: "pending", name: "Factorial", command: "sdc experiments factorial <city> [<city> ...]" },
  targeting: { status: "pending", name: "Corridor targeting", question: "Should a budget cool the hottest ground, or the ground people actually walk on?", hypotheses: ["H8 plans differ"], detail: "Two plans per city at one budget.", command: "sdc experiments targeting <city> [<city> ...]" },
  channel: { status: "pending", name: "De-paving", question: "Does replacing asphalt with grass cool pedestrians?", hypotheses: [], detail: "", command: "sdc experiments channel <city> [<city> ...]" },
};

afterEach(() => vi.unstubAllGlobals());

it("shows a settled finding's numbers and a pending one's question and command", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => Response.json(FINDINGS)));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <FindingsPage />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("0.735")).toBeInTheDocument();
  expect(screen.getAllByText("settled")).toHaveLength(1);
  expect(screen.getAllByText("pending")).toHaveLength(3);
  expect(screen.getByText(/Should a budget cool the hottest ground/)).toBeInTheDocument();
  expect(screen.getByText("sdc experiments targeting <city> [<city> ...]")).toBeInTheDocument();
});
