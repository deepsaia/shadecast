import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { api } from "@/api/client";
import type { CitySummary } from "@/api/models";
import { GridThumb } from "@/components/GridThumb";
import { TileStrip } from "@/components/TileStrip";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { integer } from "@/lib/format";
import { byName } from "@/lib/order";
import { cellsOf } from "@/lib/tile_grid";

/** Every selected city, what each has on disk, and the way into its tiles. */
export function CitiesPage() {
  const cities = useQuery({ queryKey: ["cities"], queryFn: api.cities });
  return (
    <section>
      <h1>Cities</h1>
      <p className="mt-2 max-w-[60ch] text-muted-foreground">
        Given a city and a budget, which cooling measures should it build, and where? Each selected
        city is studied on 1 km tiles. The strip shows how far its tiles have come: built, simulated,
        and learned from.
      </p>
      {cities.isPending && <p className="mt-8 text-muted-foreground">Loading the selection.</p>}
      {cities.isError && (
        <p className="mt-8 text-destructive" role="alert">
          The server did not answer: {cities.error.message}. Start it with <code>sdc serve</code>.
        </p>
      )}
      {cities.data && <CitiesTable cities={cities.data} />}
    </section>
  );
}

function CitiesTable({ cities }: { cities: CitySummary[] }) {
  const built = cities.filter((city) => city.stages.bundle > 0).length;
  return (
    <div className="mt-8">
      <Table>
        <TableCaption className="sr-only">Selected cities and their stages</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead>City</TableHead>
            <TableHead>Climate</TableHead>
            <TableHead>Income</TableHead>
            <TableHead className="text-right">People, 2025</TableHead>
            <TableHead className="text-right">Tiles</TableHead>
            <TableHead>Progress</TableHead>
            <TableHead className="text-right">Built</TableHead>
            <TableHead>Map</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {byName(cities).map((city) => (
            <CityRow key={city.key} city={city} />
          ))}
        </TableBody>
      </Table>
      <p className="mt-3 text-sm text-muted-foreground">
        {built} of {cities.length} cities have at least one tile built.
      </p>
    </div>
  );
}

function CityRow({ city }: { city: CitySummary }) {
  const hasTiles = city.stages.bundle > 0;
  return (
    <TableRow>
      <TableCell>
        {hasTiles ? (
          <Link to={`/cities/${city.key}`} className="font-medium underline-offset-4 hover:underline">
            {city.name}
          </Link>
        ) : (
          <span className="font-medium">{city.name}</span>
        )}
        <span className="ml-2 text-muted-foreground">{city.country}</span>
        {city.stages.model > 0 && (
          <Link to={`/?city=${city.key}`} className="ml-3 text-sm underline-offset-4 hover:underline">
            simulate
          </Link>
        )}
      </TableCell>
      <TableCell>{city.koppen ?? ""}</TableCell>
      <TableCell>{city.income ?? ""}</TableCell>
      <TableCell className="text-right">{integer(city.population_2025)}</TableCell>
      <TableCell className="text-right">{integer(city.stages.tiles)}</TableCell>
      <TableCell>
        <TileStrip stages={city.stages} />
      </TableCell>
      <TableCell className="text-right">
        {city.stages.bundle > 0 ? `${city.stages.bundle} of ${city.stages.tiles}` : "none yet"}
      </TableCell>
      <TableCell>{hasTiles && <CityThumb city={city.key} />}</TableCell>
    </TableRow>
  );
}

function CityThumb({ city }: { city: string }) {
  const grid = useQuery({ queryKey: ["grid", city], queryFn: () => api.grid(city), retry: false });
  if (!grid.data) return <span className="text-xs text-muted-foreground">{grid.isError ? "not described" : ""}</span>;
  return <GridThumb cells={cellsOf(grid.data)} />;
}
