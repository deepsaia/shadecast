import type { StageCounts } from "@/api/models";

const CELLS = 20;

/**
 * A city's tiles as a strip of cells, filled by the furthest stage each share has reached:
 * leaf for tiles with a model, sun for tiles with physics, ink for tiles only built, and the rest
 * empty. Twenty cells stand for the whole city, however many tiles it has.
 */
export function TileStrip({ stages }: { stages: StageCounts }) {
  const total = Math.max(stages.tiles, 1);
  const filled = (count: number) => Math.round((Math.min(count, total) / total) * CELLS);
  const modelled = filled(stages.model);
  const physics = Math.max(filled(stages.physics), modelled);
  const built = Math.max(filled(stages.bundle), physics);
  const label = `${stages.bundle} of ${stages.tiles} tiles built, ${stages.physics} with physics, ${stages.model} with a model`;
  return (
    <div className="flex gap-px" role="img" aria-label={label} title={label}>
      {Array.from({ length: CELLS }, (_, index) => (
        <span
          key={index}
          className={
            "h-3 w-2 rounded-[1px] " +
            (index < modelled
              ? "bg-leaf"
              : index < physics
                ? "bg-sun"
                : index < built
                  ? "bg-foreground/70"
                  : "bg-foreground/10")
          }
        />
      ))}
    </div>
  );
}
