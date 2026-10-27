import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { CitySummary, ModelSummary } from "@/api/models";
import { Loading } from "@/components/Loading";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { decimal, integer } from "@/lib/format";

/** The surrogate models trained so far, per channel and city, from their manifests. */
export function ModelsPage() {
  const channels = useQuery({ queryKey: ["channels"], queryFn: api.channels });
  const cities = useQuery({ queryKey: ["cities"], queryFn: api.cities });
  return (
    <section>
      <h1>Models</h1>
      <p className="mt-2 max-w-[60ch] text-muted-foreground">
        A surrogate learns one physical channel from a city's generated physics and answers in a fraction of a
        second what the engine answers in minutes. Every model is listed from its manifest.
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
          No model trained yet. Generate a city's physics, then <code>sdc surrogate treeshade train &lt;city&gt;</code>.
        </p>
      ))}
    </section>
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
