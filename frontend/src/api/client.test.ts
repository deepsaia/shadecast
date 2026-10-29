import { ApiError, getJson, paths } from "./client";

describe("paths", () => {
  it("build every route under the API prefix with encoded names", () => {
    expect(paths.cities()).toBe("/cities");
    expect(paths.tiles("oaxaca")).toBe("/cities/oaxaca/tiles");
    expect(paths.grid("oaxaca")).toBe("/cities/oaxaca/grid");
    expect(paths.report("ahmedabad", "t43N_249_2547")).toBe(
      "/cities/ahmedabad/tiles/t43N_249_2547/report",
    );
    expect(paths.field("a b", "t1_1_1", "hours", { size: 384 })).toBe(
      "/cities/a%20b/tiles/t1_1_1/fields/hours?size=384",
    );
    expect(paths.field("a", "t", "cooling", { design: "clustered_0101" })).toBe(
      "/cities/a/tiles/t/fields/cooling?design=clustered_0101",
    );
    expect(paths.scenario("ahmedabad", "t43N_249_2547", { arrangement: "scattered", coverage: 0.05 })).toBe(
      "/cities/ahmedabad/tiles/t43N_249_2547/scenario?arrangement=scattered&coverage=0.05",
    );
    expect(paths.scenarioField("a", "t", { budget_usd: 5000000, size: 256 })).toBe(
      "/cities/a/tiles/t/scenario/field?budget_usd=5000000&size=256",
    );
    expect(paths.scenario("a", "t", {})).toBe("/cities/a/tiles/t/scenario");
  });
});

describe("getJson", () => {
  it("surfaces the server's error body as the message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ error: "no city or urban centre 'atlantis'", kind: "UnknownCity" }), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    await expect(getJson("/cities/atlantis/tiles")).rejects.toBeInstanceOf(ApiError);
    await expect(getJson("/cities/atlantis/tiles")).rejects.toThrow("atlantis");
    vi.unstubAllGlobals();
  });
});
