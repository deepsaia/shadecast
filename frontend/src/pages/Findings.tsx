import { useQuery } from "@tanstack/react-query";
import { Line, LineChart, XAxis, YAxis } from "recharts";

import { api } from "@/api/client";
import type { Findings } from "@/api/models";
import { Loading } from "@/components/Loading";
import { Badge } from "@/components/ui/badge";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { decimal, integer, percent } from "@/lib/format";

type Summary = Record<string, unknown>;

interface RouteCooling {
  route_exposure_drop_C: number;
}

interface TargetingRow {
  city: string;
  area: RouteCooling;
  route: RouteCooling;
}

interface ChannelCell {
  kind: string;
  ts_deg: number;
  pixels: number;
  treated_drop_C: number;
  exposure_drop_C: number;
}

interface ChannelRow {
  city: string;
  cells: ChannelCell[];
}

/** What the experiments have established so far, settled or still open, from their files. */
export function FindingsPage() {
  const findings = useQuery({ queryKey: ["findings"], queryFn: api.findings });
  return (
    <section>
      <h1>Findings</h1>
      <p className="mt-2 max-w-[60ch] text-muted-foreground">
        Each experiment was pre-registered with the number that would support it and the number that would not.
        A finding here is read from the experiment's own file; one that has not run says what would run it.
      </p>
      <Loading query={findings} what="the findings" />
      {findings.data && <Settled findings={findings.data} />}
    </section>
  );
}

function Settled({ findings }: { findings: Findings }) {
  return (
    <>
      <Finding title="The surrogate" summary={findings.surrogate}>
        <Surrogate summary={findings.surrogate} />
      </Finding>
      <Finding title="Which measure buys the most" summary={findings.factorial}>
        <Factorial summary={findings.factorial} />
      </Finding>
      <Finding title="Corridor targeting" summary={findings.targeting}>
        <Targeting summary={findings.targeting} />
      </Finding>
      <Finding title="De-paving" summary={findings.channel}>
        <Channel summary={findings.channel} />
      </Finding>
    </>
  );
}

function Finding({ title, summary, children }: { title: string; summary: Summary; children: React.ReactNode }) {
  const done = summary.status === "done";
  return (
    <section className="mt-10 border-t pt-6">
      <div className="flex flex-wrap items-baseline gap-3">
        <h2>{title}</h2>
        <Badge variant={done ? "default" : "outline"}>{done ? "settled" : "pending"}</Badge>
      </div>
      <div className="mt-4">{done ? children : <Pending summary={summary} />}</div>
    </section>
  );
}

function Pending({ summary }: { summary: Summary }) {
  const hypotheses = Array.isArray(summary.hypotheses) ? (summary.hypotheses as string[]) : [];
  return (
    <div className="max-w-[64ch] text-sm">
      {typeof summary.question === "string" && <p>{summary.question}</p>}
      {hypotheses.length > 0 && (
        <ul className="mt-2 list-disc pl-5 text-muted-foreground">
          {hypotheses.map((hypothesis) => (
            <li key={hypothesis}>{hypothesis}</li>
          ))}
        </ul>
      )}
      {typeof summary.detail === "string" && <p className="mt-2 text-muted-foreground">{summary.detail}</p>}
      {typeof summary.command === "string" && summary.command && (
        <pre className="mt-3 overflow-x-auto rounded-sm bg-secondary px-3 py-2 text-[13px]">{summary.command}</pre>
      )}
    </div>
  );
}

function Surrogate({ summary }: { summary: Summary }) {
  const transfer = Array.isArray(summary.transfer) ? (summary.transfer as { cities: number; skill: number }[]) : [];
  const facts: [string, string][] = [
    ["Skill against predicting no change", decimal(Number(summary.skill), 3)],
    ["Rank correlation with the engine", decimal(Number(summary.ranking_spearman), 2)],
    ["Error on a plan's total cooling", percent(Number(summary.aggregate_error), 1)],
    ["Speedup", `${integer(Number(summary.speedup))}x, ${decimal(Number(summary.engine_seconds), 0)} s of physics becomes ${decimal(Number(summary.surrogate_seconds), 1)} s`],
  ];
  return (
    <div className="grid gap-8 md:grid-cols-2">
      <dl className="grid grid-cols-[1fr_auto] gap-x-6 gap-y-1.5 text-sm">
        {facts.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-muted-foreground">{label}</dt>
            <dd className="text-right">{value}</dd>
          </div>
        ))}
      </dl>
      {transfer.length > 0 && (
        <figure className="m-0">
          <figcaption className="mb-1 text-sm text-muted-foreground">Does training on more cities help an unseen one?</figcaption>
          <ChartContainer config={{ skill: { label: "skill on the unseen city", color: "var(--sun)" } }} className="h-40 w-full">
            <LineChart data={transfer} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <XAxis dataKey="cities" fontSize={11} tickLine={false} axisLine={false} label={{ value: "training cities", position: "insideBottom", offset: -2, fontSize: 11 }} />
              <YAxis domain={[0, 1]} width={32} fontSize={11} tickLine={false} axisLine={false} />
              <ChartTooltip content={<ChartTooltipContent />} />
              <Line type="monotone" dataKey="skill" stroke="var(--color-skill)" strokeWidth={2} dot={{ r: 4 }} />
            </LineChart>
          </ChartContainer>
          <p className="mt-2 text-sm">
            Held out entirely, then predicted. Skill went from {transfer[0].skill} with {transfer[0].cities}{" "}
            {transfer[0].cities === 1 ? "city" : "cities"} to {transfer[transfer.length - 1].skill} with{" "}
            {transfer[transfer.length - 1].cities}: {String(summary.transfer_verdict ?? "")}.
          </p>
        </figure>
      )}
    </div>
  );
}

function Factorial({ summary }: { summary: Summary }) {
  const verdict = (summary.verdict ?? {}) as Record<string, unknown>;
  const ratio = (verdict.advantage_ratio ?? {}) as Record<string, number>;
  const spreads = Array.isArray(summary.spreads) ? (summary.spreads as Record<string, number>[]) : [];
  return (
    <div className="max-w-[64ch] text-sm">
      <p>
        A full factorial of {integer(Number(summary.cells))} cells, every one a real physics run, across{" "}
        {Array.isArray(summary.cities) ? (summary.cities as string[]).join(", ") : ""}.
      </p>
      <ul className="mt-3 space-y-2">
        <li>
          <Badge variant={verdict.h3_supported ? "default" : "outline"}>H3</Badge> Trees win on cooling per dollar: they won{" "}
          {String(verdict.tree_wins)} of {String(verdict.comparisons)} comparisons, by {ratio.min}x to {ratio.max}x, mean{" "}
          {ratio.mean}x.
        </li>
        <li>
          <Badge variant={verdict.h4_supported ? "default" : "outline"}>H4</Badge> The ranking is the same in every city:{" "}
          {verdict.h4_supported ? "it was" : "it was not"}.
        </li>
      </ul>
      {spreads.length > 0 && (
        <div className="mt-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Budget</TableHead>
                <TableHead className="text-right">Cooling varies</TableHead>
                <TableHead className="text-right">People helped varies</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {spreads.map((spread) => (
                <TableRow key={spread.budget_usd}>
                  <TableCell>${decimal(spread.budget_usd / 1e6, 1)}M</TableCell>
                  <TableCell className="text-right">{spread.cooling_spread}x</TableCell>
                  <TableCell className="text-right">{spread.people_spread}x</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <p className="mt-3">
            The same money buys almost the same physics in every city and up to{" "}
            {Math.max(...spreads.map((spread) => spread.people_spread))}x the human benefit. Cooling transfers between
            cities; who is standing in the cooled space does not.
          </p>
        </div>
      )}
    </div>
  );
}

function Targeting({ summary }: { summary: Summary }) {
  const verdict = (summary.verdict ?? {}) as Record<string, unknown>;
  const rows = Array.isArray(summary.rows) ? (summary.rows as TargetingRow[]) : [];
  return (
    <div className="max-w-[64ch] text-sm">
      <p>
        <Badge variant={verdict.supported ? "default" : "outline"}>H8</Badge> The two objectives select{" "}
        {verdict.supported ? "different" : "the same"} plans: {percent(Number(verdict.mean_plan_overlap), 1)} of planted
        positions shared, against the pre-registered bar of under 70%, and {String(verdict.mean_route_advantage_C)} C extra
        cooling on walked routes, against the bar of at least 0.3 C.
      </p>
      {rows.length > 0 && (
        <div className="mt-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>City</TableHead>
                <TableHead className="text-right">Hot-ground plan, route cooling C</TableHead>
                <TableHead className="text-right">Corridor plan, route cooling C</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.city}>
                  <TableCell className="font-medium capitalize">{row.city}</TableCell>
                  <TableCell className="text-right">{decimal(row.area.route_exposure_drop_C, 2)}</TableCell>
                  <TableCell className="text-right">{decimal(row.route.route_exposure_drop_C, 2)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

function Channel({ summary }: { summary: Summary }) {
  const verdict = (summary.verdict ?? {}) as Record<string, unknown>;
  const mean = (verdict.mean_treated_drop_C ?? {}) as Record<string, number>;
  const rows = Array.isArray(summary.rows) ? (summary.rows as ChannelRow[]) : [];
  const cells = rows.flatMap((row) =>
    (row.cells ?? []).filter((cell) => cell.pixels).map((cell) => ({ city: row.city, ...cell })),
  );
  return (
    <div className="max-w-[64ch] text-sm">
      <ul className="space-y-2">
        <li>
          <Badge variant={verdict.h5_cools ? "default" : "outline"}>H5</Badge> De-paving cools treated ground, predicted 0.5 to
          3 C: it averaged {mean.depave} C, {verdict.h5_in_predicted_range ? "inside" : "outside"} the band written down.
        </li>
        <li>
          <Badge variant={verdict.h6_monotone ? "default" : "outline"}>H6</Badge> Cooling follows the surface heating
          coefficient, grass ahead of permeable paving: {mean.depave} C against {mean.permeable} C.
        </li>
      </ul>
      {cells.length > 0 && (
        <div className="mt-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>City</TableHead>
                <TableHead>Surface</TableHead>
                <TableHead className="text-right">Heating coefficient</TableHead>
                <TableHead className="text-right">Treated ground, C</TableHead>
                <TableHead className="text-right">City-wide, C</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {cells.map((cell, index) => (
                <TableRow key={index}>
                  <TableCell className="font-medium capitalize">{cell.city}</TableCell>
                  <TableCell>{cell.kind === "depave" ? "grass" : "permeable"}</TableCell>
                  <TableCell className="text-right">{cell.ts_deg}</TableCell>
                  <TableCell className="text-right">{decimal(cell.treated_drop_C, 2)}</TableCell>
                  <TableCell className="text-right">{decimal(cell.exposure_drop_C, 3)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
