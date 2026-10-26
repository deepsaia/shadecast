/**
 * Color ramps for fields: one hue, light to dark, so a reader sees magnitude and nothing else.
 * Heat is the orange hue, cooling the blue hue, both stepped as the project's palette is.
 */

export type Rgb = [number, number, number];
export type Ramp = Rgb[];

export const HEAT: Ramp = [
  [253, 228, 212],
  [246, 173, 134],
  [235, 104, 52],
  [183, 74, 30],
  [110, 44, 16],
];

export const COOL: Ramp = [
  [205, 226, 251],
  [134, 182, 239],
  [57, 135, 229],
  [37, 106, 191],
  [13, 54, 107],
];

export const LEAF: Rgb = [47, 125, 91];

/** The color at position ``t`` in 0..1 along the ramp, interpolated between its stops. */
export function ramp(stops: Ramp, t: number): Rgb {
  const clamped = Math.min(1, Math.max(0, t));
  const last = stops.length - 1;
  const index = Math.min(last - 1, Math.floor(clamped * last));
  const fraction = clamped * last - index;
  const a = stops[index];
  const b = stops[index + 1];
  return [
    Math.round(a[0] + (b[0] - a[0]) * fraction),
    Math.round(a[1] + (b[1] - a[1]) * fraction),
    Math.round(a[2] + (b[2] - a[2]) * fraction),
  ];
}

export interface Scale {
  min: number;
  max: number;
}

/** The smallest and largest finite values of an array, for a scale held fixed across frames. */
export function extent(values: ArrayLike<number>): Scale {
  let min = Infinity;
  let max = -Infinity;
  for (let index = 0; index < values.length; index += 1) {
    const value = values[index];
    if (!Number.isFinite(value)) continue;
    if (value < min) min = value;
    if (value > max) max = value;
  }
  if (min === Infinity) return { min: 0, max: 1 };
  return { min, max: max > min ? max : min + 1 };
}

/** Paint a field into RGBA bytes: NaN is transparent, values below ``floor`` too. */
export function paint(
  values: ArrayLike<number>,
  scale: Scale,
  stops: Ramp,
  out: Uint8ClampedArray,
  floor = -Infinity,
): void {
  const span = scale.max - scale.min || 1;
  for (let index = 0; index < values.length; index += 1) {
    const value = values[index];
    const at = index * 4;
    if (!Number.isFinite(value) || value <= floor) {
      out[at + 3] = 0;
      continue;
    }
    const [r, g, b] = ramp(stops, (value - scale.min) / span);
    out[at] = r;
    out[at + 1] = g;
    out[at + 2] = b;
    out[at + 3] = 255;
  }
}

/** Paint a mask: set cells in one color, the rest transparent. */
export function paintMask(values: ArrayLike<number>, color: Rgb, out: Uint8ClampedArray): void {
  for (let index = 0; index < values.length; index += 1) {
    const at = index * 4;
    if (values[index] > 0) {
      out[at] = color[0];
      out[at + 1] = color[1];
      out[at + 2] = color[2];
      out[at + 3] = 255;
    } else {
      out[at + 3] = 0;
    }
  }
}

/** A value for the readout: never "-0.0", one decimal, with its unit. */
export function readout(value: number, unit: string): string {
  const shown = Math.abs(value) < 0.05 ? 0 : value;
  return `${shown.toFixed(1)}${unit}`;
}
