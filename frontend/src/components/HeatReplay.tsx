import { useQuery } from "@tanstack/react-query";
import { Pause, Play } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { fetchField } from "@/api/fields";
import type { TileReport } from "@/api/models";
import { FieldCanvas } from "@/components/FieldCanvas";
import { MetChart } from "@/components/MetChart";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { decimal, integer } from "@/lib/format";
import { band, type NpyArray } from "@/lib/npy";
import { HEAT, extent } from "@/lib/ramp";

const DISPLAY_PX = 384;

/** The day's heat, hour by hour, beside the design day's weather, with the baseline exposure in words. */
export function HeatReplay({ city, tile, report }: { city: string; tile: string; report: TileReport }) {
  const [hour, setHour] = useState(15);
  const [playing, setPlaying] = useState(false);
  const hours = useQuery({
    queryKey: ["field", city, tile, "hours", DISPLAY_PX],
    queryFn: () => fetchField(city, tile, "hours", { size: DISPLAY_PX }),
  });
  const scale = useMemo(() => (hours.data ? extent(hours.data.data) : null), [hours.data]);
  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => setHour((current) => (current + 1) % 24), 400);
    return () => window.clearInterval(timer);
  }, [playing]);
  const statistic = report.hourly[hour];
  return (
    <div>
      <p className="max-w-[60ch] text-sm text-muted-foreground">
        Mean radiant temperature for every square metre and every hour, on one scale held fixed across the
        day. Hover any pixel to read its value.
      </p>
      <div className="mt-4 grid gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div>
          {hours.data && scale ? (
            <HourField array={hours.data} hour={hour} scale={scale} />
          ) : (
            <div className="aspect-square w-full rounded-sm bg-secondary" aria-busy="true" />
          )}
          <div className="mt-3 flex items-center gap-3">
            <Button
              variant="outline"
              size="icon"
              aria-pressed={playing}
              aria-label={playing ? "Pause" : "Play the day"}
              onClick={() => setPlaying((current) => !current)}
            >
              {playing ? <Pause /> : <Play />}
            </Button>
            <Slider
              value={[hour]}
              min={0}
              max={23}
              step={1}
              onValueChange={([value]) => setHour(value)}
              aria-label="Hour of day"
              className="flex-1"
            />
            <span className="w-14 text-right tabular-nums">{String(hour).padStart(2, "0")}:00</span>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            {statistic ? `median ${decimal(statistic.median, 1)} C, peak ${decimal(statistic.max, 1)} C` : ""}
            {scale ? `, scale ${decimal(scale.min, 0)} to ${decimal(scale.max, 0)} C` : ""}
          </p>
        </div>
        <div>
          <p className="text-sm text-muted-foreground">Weather on the design day</p>
          <div className="mt-2">
            <MetChart met={report.met} hour={hour} />
          </div>
          {report.baseline && (
            <p className="mt-4 text-sm">
              Doing nothing leaves a population-weighted outdoor exposure of{" "}
              <strong>{decimal(report.baseline.exposure, 1)} C</strong>, with{" "}
              <strong>{integer(report.baseline.at_risk)}</strong> people on ground above the stress threshold.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function HourField({ array, hour, scale }: { array: NpyArray; hour: number; scale: { min: number; max: number } }) {
  const [, height, width] = array.shape;
  const values = useMemo(() => band(array, hour), [array, hour]);
  return (
    <FieldCanvas
      values={values}
      width={width}
      height={height}
      encoding={{ kind: "quantity", ramp: HEAT, scale, unit: " C" }}
      label={`Mean radiant temperature at ${hour}:00`}
    />
  );
}
