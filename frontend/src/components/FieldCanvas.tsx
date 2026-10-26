import { useEffect, useRef, useState } from "react";

import { type NpyData } from "@/lib/npy";
import { LEAF, paint, paintMask, readout, type Ramp, type Scale } from "@/lib/ramp";

type Quantity = { kind: "quantity"; ramp: Ramp; scale: Scale; unit: string; floor?: number };
type Mask = { kind: "mask" };

interface Props {
  values: NpyData;
  width: number;
  height: number;
  encoding: Quantity | Mask;
  label: string;
}

/**
 * A field on a canvas: every pixel colored from the array through a ramp, the value under the
 * pointer read straight from the array, and a placement mask reported as a state, not a number.
 */
export function FieldCanvas({ values, width, height, encoding, label }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [read, setRead] = useState("hover to read");

  useEffect(() => {
    const context = canvas.current?.getContext("2d");
    if (!context) return;
    const image = context.createImageData(width, height);
    if (encoding.kind === "mask") paintMask(values, LEAF, image.data);
    else paint(values, encoding.scale, encoding.ramp, image.data, encoding.floor);
    context.putImageData(image, 0, 0);
  }, [values, width, height, encoding]);

  function onMove(event: React.PointerEvent<HTMLCanvasElement>) {
    const box = event.currentTarget.getBoundingClientRect();
    const x = Math.floor(((event.clientX - box.left) / box.width) * width);
    const y = Math.floor(((event.clientY - box.top) / box.height) * height);
    if (x < 0 || y < 0 || x >= width || y >= height) return;
    const value = values[y * width + x];
    if (encoding.kind === "mask") setRead(value > 0 ? "planted" : "not planted");
    else setRead(Number.isFinite(value) ? readout(value, encoding.unit) : "no data");
  }

  return (
    <figure className="relative m-0">
      <canvas
        ref={canvas}
        width={width}
        height={height}
        role="img"
        aria-label={label}
        className="block aspect-square w-full rounded-sm bg-secondary [image-rendering:pixelated]"
        onPointerMove={onMove}
        onPointerLeave={() => setRead("hover to read")}
      />
      <figcaption className="absolute bottom-2 right-2 rounded-sm bg-bar/85 px-2 py-0.5 text-xs text-bar-foreground">
        {read}
      </figcaption>
    </figure>
  );
}
