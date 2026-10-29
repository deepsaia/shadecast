import { type Cell, thumbnail } from "@/lib/tile_grid";

const SIDE = 72;

/** A city's tile grid in a small square: residents as ink, the tiles with a model outlined in the sun color. */
export function GridThumb({ cells }: { cells: Cell[] }) {
  const drawn = thumbnail(cells, SIDE);
  const modelled = cells.filter((cell) => cell.modelled).length;
  const label = `${cells.length} tiles, ${modelled} with a model`;
  return (
    <svg
      viewBox={`0 0 ${Math.max(drawn.width, 1)} ${Math.max(drawn.height, 1)}`}
      width={drawn.width}
      height={drawn.height}
      role="img"
      aria-label={label}
      className="block"
    >
      <title>{label}</title>
      {drawn.rects.map((rect) => (
        <rect
          key={rect.id}
          x={rect.x}
          y={rect.y}
          width={rect.width}
          height={rect.height}
          fill={rect.fill}
          stroke={rect.modelled ? "var(--sun)" : "none"}
          strokeWidth={rect.modelled ? 1.5 : 0}
        />
      ))}
    </svg>
  );
}
