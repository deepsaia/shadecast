import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { CitySummary, ModelSummary } from "@/api/models";
import { Loading } from "@/components/Loading";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { decimal, integer } from "@/lib/format";
import { byName } from "@/lib/order";

/** The surrogate models trained so far, per channel and city, from their manifests. */
export function ModelsPage() {
  const channels = useQuery({ queryKey: ["channels"], queryFn: api.channels });
  const cities = useQuery({ queryKey: ["cities"], queryFn: api.cities });
  return (
    <section>
      <h1>Models</h1>
      <p className="mt-2 max-w-[60ch] text-muted-foreground">
        A surrogate learns one physical channel from a city's simulated physics and answers in a fraction of a
        second what the engine answers in minutes. Simulating the designs writes what a model learns from; training
        is its own step. Every model is listed from its manifest.
      </p>
      <Loading query={channels} what="the channels" />
      {channels.data && cities.data && channels.data.map((channel) => (
        <ChannelModels key={channel.key} channelKey={channel.key} label={channel.label} cities={cities.data} />
      ))}
    </section>
  );
}

function ChannelModels({ channelKey, label, cities }: { channelKey: string; label: string; cities: CitySummary[] }) {
  const models = useQuery({ queryKey: ["models", channelKey], queryFn: () => api.models(channelKey) });
  const names = new Map(cities.map((city) => [city.ucdb_id, city.name]));
  return (
    <section className="mt-8">
      <h2>Surrogate for {label}</h2>
      <Loading query={models} what="the models" />
      {models.data && (models.data.length ? <ModelTable models={models.data} names={names} /> : (
        <p className="mt-3 max-w-[60ch] text-sm text-muted-foreground">
          No model trained yet. Simulate a city's physics, then <code>sdc surrogate {channelKey} train &lt;city&gt;</code>.
        </p>
      ))}
      {models.data && <Untrained channelKey={channelKey} cities={cities} />}
    </section>
  );
}

/** The cities whose tiles have physics and no model, each with the command that trains one. */
function Untrained({ channelKey, cities }: { channelKey: string; cities: CitySummary[] }) {
  const waiting = byName(cities.filter((city) => city.stages.physics > 0 && city.stages.model === 0));
  if (!waiting.length) return null;
  return (
    <div className="mt-6 max-w-[64ch] rounded-md border border-dashed p-4 text-sm">
      <p>
        {waiting.length === 1 ? "One city has" : `${waiting.length} cities have`} simulated physics and no model
        yet. Train one per city with:
      </p>
      <ul className="mt-2 grid gap-1 sm:grid-cols-2">
        {waiting.map((city) => (
          <li key={city.key} className="flex items-baseline justify-between gap-3">
            <span>{city.name}</span>
            <code className="text-[13px]">
              sdc surrogate {channelKey} train {city.key}
            </code>
          </li>
        ))}
      </ul>
    </div>
  );
}

function cityNames(model: ModelSummary, names: Map<number, string>): string {
  return model.urban_centres.map((centre) => names.get(centre) ?? String(centre)).join(", ");
}

function ModelTable({ models, names }: { models: ModelSummary[]; names: Map<number, string> }) {
  return (
    <div className="mt-4">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>City</TableHead>
            <TableHead>Model</TableHead>
            <TableHead>Trained on</TableHead>
            <TableHead>Created</TableHead>
            <TableHead className="text-right">Best skill</TableHead>
            <TableHead>State</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {models.map((model) => (
            <TableRow key={model.path}>
              <TableCell className="font-medium">{cityNames(model, names)}</TableCell>
              <TableCell className="text-xs">{model.id}</TableCell>
              <TableCell>{model.tile ? `tile ${model.tile}` : `${integer(model.tiles_trained)} tiles, pooled`}</TableCell>
              <TableCell>{model.created}</TableCell>
              <TableCell className="text-right">{model.skill === null ? "" : decimal(model.skill, 3)}</TableCell>
              <TableCell className="text-muted-foreground">
                {model.has_weights && model.has_manifest ? "complete" : model.has_weights ? "no manifest" : "no weights"}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
