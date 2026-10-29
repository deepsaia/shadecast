import { useQuery } from "@tanstack/react-query";
import { Navigate, useParams } from "react-router";

import { api, ApiError } from "@/api/client";
import { NextStep } from "@/components/NextStep";

/** A city alone means its tile that has come furthest; the server decides which. A page name goes beneath it. */
export function CityRedirect({ page }: { page?: "scenario" }) {
  const { city = "" } = useParams();
  const report = useQuery({ queryKey: ["cityReport", city], queryFn: () => api.cityReport(city) });
  if (report.isPending) return <p className="text-muted-foreground">Finding the tile that has come furthest.</p>;
  if (report.isError) {
    const error = report.error;
    const command = error instanceof ApiError && typeof error.body.command === "string" ? error.body.command : null;
    return (
      <section>
        <h1>{city}</h1>
        {command ? (
          <div className="mt-6">
            <NextStep missing="built tile" command={command} />
          </div>
        ) : (
          <p className="mt-4 text-destructive" role="alert">
            {error.message}
          </p>
        )}
      </section>
    );
  }
  return <Navigate to={`/cities/${city}/tiles/${report.data.tile}${page ? `/${page}` : ""}`} replace />;
}
