import { type GeoJSONSource, type ImageSource, Map as MapLibreMap, type MapLayerMouseEvent } from "maplibre-gl";
import type { FeatureCollection } from "geojson";
import { useEffect, useMemo, useRef, useState } from "react";

import "maplibre-gl/dist/maplibre-gl.css";

import { integer } from "@/lib/format";
import { type Bounds, type Cell, cellBounds, densityCeiling, gridBounds, gridFeatures } from "@/lib/tile_grid";

const EMPTY: FeatureCollection = { type: "FeatureCollection", features: [] };
const INK_LIGHT = "rgb(228 234 231)";
const INK_DARK = "rgb(27 43 52)";

export interface Overlay {
  url: string;
  bounds: Bounds;
}

export type Zoom = "city" | "tile";
type Corners = [[number, number], [number, number], [number, number], [number, number]];

/**
 * The city's tile grid on a map: cells shaded by residents, the tiles with a model outlined in the sun
 * color, the chosen ones in ink and the focused one thicker, hover reading a tile, a click choosing a
 * modelled one, and the cooling field laid over the focused tile when there is one.
 */
export function CityMap({
  style,
  cells,
  chosen,
  focused,
  zoom,
  overlay,
  onPick,
}: {
  style: string; // the basemap, the one layer not from our data; the grid and the cooling draw without it
  cells: Cell[];
  chosen: string[];
  focused: string;
  zoom: Zoom;
  overlay?: Overlay;
  onPick: (id: string) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibreMap | null>(null);
  const pick = useRef(onPick);
  useEffect(() => {
    pick.current = onPick;
  }, [onPick]);
  const [ready, setReady] = useState(false);
  const [read, setRead] = useState("hover a tile to read it");
  const features = useMemo(() => gridFeatures(cells), [cells]);
  const bounds = useMemo(() => gridBounds(cells), [cells]);
  const ceiling = useMemo(() => densityCeiling(cells), [cells]);
  const focusedCell = cells.find((cell) => cell.id === focused);

  useEffect(() => {
    if (!container.current || map.current) return;
    const created = new MapLibreMap({
      container: container.current,
      style,
      attributionControl: { compact: true },
      cooperativeGestures: true,
    });
    created.on("load", () => {
      created.addSource("grid", { type: "geojson", data: EMPTY });
      created.addLayer({ id: "grid-fill", type: "fill", source: "grid", paint: { "fill-opacity": 0.55 } });
      created.addLayer({
        id: "grid-line",
        type: "line",
        source: "grid",
        paint: { "line-color": "#ffffff", "line-width": 0.5, "line-opacity": 0.7 },
      });
      created.addLayer({
        id: "grid-modelled",
        type: "line",
        source: "grid",
        filter: ["==", ["get", "modelled"], true],
        paint: { "line-color": "#f2b134", "line-width": 2 },
      });
      created.addLayer({
        id: "grid-chosen",
        type: "line",
        source: "grid",
        filter: ["in", ["get", "id"], ["literal", []]],
        paint: { "line-color": INK_DARK, "line-width": 2.5 },
      });
      created.addLayer({
        id: "grid-focused",
        type: "line",
        source: "grid",
        filter: ["==", ["get", "id"], ""],
        paint: { "line-color": INK_DARK, "line-width": 4 },
      });
      setReady(true);
    });
    created.on("mousemove", "grid-fill", (event: MapLayerMouseEvent) => {
      const found = event.features?.[0]?.properties as Cell | undefined;
      if (!found) return;
      created.getCanvas().style.cursor = found.modelled ? "pointer" : "";
      setRead(`${found.id}, ${integer(found.residents)} residents${found.modelled ? ", has a model" : ", no model yet"}`);
    });
    created.on("mouseleave", "grid-fill", () => {
      created.getCanvas().style.cursor = "";
      setRead("hover a tile to read it");
    });
    created.on("click", "grid-fill", (event: MapLayerMouseEvent) => {
      const found = event.features?.[0]?.properties as Cell | undefined;
      if (found?.modelled) pick.current(found.id);
    });
    map.current = created;
    return () => {
      created.remove();
      map.current = null;
    };
  }, [style]);

  useEffect(() => {
    const current = map.current;
    if (!ready || !current) return;
    (current.getSource("grid") as GeoJSONSource | undefined)?.setData(features);
    current.setPaintProperty("grid-fill", "fill-color", [
      "interpolate",
      ["linear"],
      ["get", "density"],
      0,
      INK_LIGHT,
      ceiling,
      INK_DARK,
    ]);
    current.setFilter("grid-chosen", ["in", ["get", "id"], ["literal", chosen]]);
    current.setFilter("grid-focused", ["==", ["get", "id"], focused]);
  }, [ready, features, ceiling, chosen, focused]);

  useEffect(() => {
    const current = map.current;
    if (!ready || !current) return;
    const target = zoom === "tile" && focusedCell ? cellBounds(focusedCell) : bounds;
    if (target) current.fitBounds(target, { padding: zoom === "tile" ? 48 : 24, duration: 600 });
  }, [ready, zoom, focusedCell, bounds]);

  useEffect(() => {
    const current = map.current;
    if (!ready || !current) return;
    const coordinates: Corners | null = overlay
      ? [
          [overlay.bounds[0][0], overlay.bounds[1][1]],
          [overlay.bounds[1][0], overlay.bounds[1][1]],
          [overlay.bounds[1][0], overlay.bounds[0][1]],
          [overlay.bounds[0][0], overlay.bounds[0][1]],
        ]
      : null;
    const source = current.getSource("cooling") as ImageSource | undefined;
    if (!overlay || !coordinates) {
      if (source) current.setLayoutProperty("cooling", "visibility", "none");
      return;
    }
    if (source) {
      source.updateImage({ url: overlay.url, coordinates });
      current.setLayoutProperty("cooling", "visibility", "visible");
      return;
    }
    current.addSource("cooling", { type: "image", url: overlay.url, coordinates });
    current.addLayer({ id: "cooling", type: "raster", source: "cooling", paint: { "raster-opacity": 0.85 } });
  }, [ready, overlay]);

  return (
    <figure className="relative m-0">
      <div ref={container} className="h-[420px] w-full rounded-md border bg-secondary" role="application" aria-label="City map" />
      <figcaption className="absolute bottom-2 left-2 rounded-sm bg-bar/85 px-2 py-0.5 text-xs text-bar-foreground">{read}</figcaption>
    </figure>
  );
}
