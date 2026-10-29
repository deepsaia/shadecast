import { COOL, paint, type Scale } from "@/lib/ramp";

/** A cooling field as an image for the map, painted through the cooling ramp; nothing where a canvas cannot draw. */
export function coolingImage(values: ArrayLike<number>, width: number, height: number, scale: Scale): string | null {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) return null;
  const image = context.createImageData(width, height);
  paint(values, scale, COOL, image.data, 0.05);
  context.putImageData(image, 0, 0);
  return canvas.toDataURL();
}
