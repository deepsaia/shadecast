import { Area, AreaChart, Line, LineChart, ReferenceLine, XAxis, YAxis } from "recharts";

import type { TileReport } from "@/api/models";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";

const config = {
  air_c: { label: "Air temperature, C", color: "var(--heat)" },
  solar: { label: "Solar radiation, W/m²", color: "var(--sun)" },
} satisfies ChartConfig;

/**
 * The design day's weather as two small charts on one time axis, one measure each, with the
 * chosen hour marked. Two charts rather than one with two scales, so neither axis lies.
 */
export function MetChart({ met, hour }: { met: TileReport["met"]; hour: number }) {
  const ticks = [0, 6, 12, 18, 23];
  return (
    <div className="grid gap-2">
      <ChartContainer config={config} className="h-28 w-full">
        <LineChart data={met} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <XAxis dataKey="hour" ticks={ticks} tickLine={false} axisLine={false} fontSize={11} />
          <YAxis width={32} tickLine={false} axisLine={false} fontSize={11} domain={["auto", "auto"]} />
          <ChartTooltip content={<ChartTooltipContent labelFormatter={(value) => `${value}:00`} />} />
          <ReferenceLine x={hour} stroke="var(--muted-foreground)" strokeDasharray="3 3" />
          <Line type="monotone" dataKey="air_c" stroke="var(--color-air_c)" strokeWidth={2} dot={false} />
        </LineChart>
      </ChartContainer>
      <ChartContainer config={config} className="h-24 w-full">
        <AreaChart data={met} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <XAxis dataKey="hour" ticks={ticks} tickLine={false} axisLine={false} fontSize={11} />
          <YAxis width={32} tickLine={false} axisLine={false} fontSize={11} />
          <ChartTooltip content={<ChartTooltipContent labelFormatter={(value) => `${value}:00`} />} />
          <ReferenceLine x={hour} stroke="var(--muted-foreground)" strokeDasharray="3 3" />
          <Area type="monotone" dataKey="solar" stroke="var(--color-solar)" fill="var(--color-solar)" fillOpacity={0.25} strokeWidth={2} />
        </AreaChart>
      </ChartContainer>
    </div>
  );
}
