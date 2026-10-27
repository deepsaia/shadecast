import { Scatter, ScatterChart, XAxis, YAxis } from "recharts";

import type { CityResult } from "@/api/models";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import { ARRANGEMENTS, seriesColor } from "@/lib/series";

/** One tile's plans on both objectives, each arrangement a line of dots in its fixed color. */
export function FacetChart({ city }: { city: CityResult }) {
  const config = Object.fromEntries(
    ARRANGEMENTS.map((arrangement) => [arrangement, { label: arrangement, color: seriesColor(arrangement) }]),
  );
  return (
    <ChartContainer config={config} className="h-48 w-full">
      <ScatterChart margin={{ top: 8, right: 8, bottom: 4, left: 0 }}>
        <XAxis type="number" dataKey="exposure_drop" name="exposure drop" unit=" C" fontSize={10} tickLine={false} axisLine={false} />
        <YAxis type="number" dataKey="people" name="people" width={40} fontSize={10} tickLine={false} axisLine={false} />
        <ChartTooltip content={<ChartTooltipContent labelKey="id" nameKey="arrangement" />} />
        {ARRANGEMENTS.map((arrangement) => (
          <Scatter
            key={arrangement}
            name={arrangement}
            data={[...city.plans.filter((plan) => plan.arrangement === arrangement)].sort((a, b) => a.coverage - b.coverage)}
            fill={seriesColor(arrangement)}
            line={{ stroke: seriesColor(arrangement), strokeWidth: 2 }}
            stroke="var(--card)"
            strokeWidth={1}
          />
        ))}
      </ScatterChart>
    </ChartContainer>
  );
}
