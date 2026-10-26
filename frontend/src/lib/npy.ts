/**
 * Read an NPY body: the magic, the version, the header dictionary, then the raw values.
 * The server writes little-endian C-order arrays; anything else is refused rather than misread.
 */

export type NpyData = Float32Array | Float64Array | Uint8Array | Int32Array;

export interface NpyArray {
  shape: number[];
  dtype: string;
  data: NpyData;
}

const MAGIC = "\x93NUMPY";

export function parseNpy(buffer: ArrayBuffer): NpyArray {
  const bytes = new Uint8Array(buffer);
  const magic = String.fromCharCode(...bytes.subarray(0, 6));
  if (magic !== MAGIC) throw new Error("not an NPY array");
  const major = bytes[6];
  const headerLength = major === 1 ? readUint16(bytes, 8) : readUint32(bytes, 8);
  const headerStart = major === 1 ? 10 : 12;
  const header = new TextDecoder("latin1").decode(bytes.subarray(headerStart, headerStart + headerLength));
  const dtype = /'descr':\s*'([^']+)'/.exec(header)?.[1];
  const fortran = /'fortran_order':\s*(True|False)/.exec(header)?.[1];
  const shapeText = /'shape':\s*\(([^)]*)\)/.exec(header)?.[1];
  if (!dtype || !fortran || shapeText === undefined) throw new Error("NPY header is incomplete");
  if (fortran === "True") throw new Error("Fortran-ordered arrays are not supported");
  const shape = shapeText
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean)
    .map(Number);
  const offset = headerStart + headerLength;
  return { shape, dtype, data: view(dtype, buffer, offset, shape.reduce((a, b) => a * b, 1)) };
}

function view(dtype: string, buffer: ArrayBuffer, offset: number, count: number): NpyData {
  // The body may not be aligned for typed views, so it is copied into an aligned buffer.
  const copy = (bytesPerValue: number) => buffer.slice(offset, offset + count * bytesPerValue);
  switch (dtype) {
    case "<f4":
      return new Float32Array(copy(4));
    case "<f8":
      return new Float64Array(copy(8));
    case "<i4":
      return new Int32Array(copy(4));
    case "|b1":
    case "|u1":
      return new Uint8Array(copy(1));
    default:
      throw new Error(`unsupported NPY dtype ${dtype}`);
  }
}

function readUint16(bytes: Uint8Array, at: number): number {
  return bytes[at] | (bytes[at + 1] << 8);
}

function readUint32(bytes: Uint8Array, at: number): number {
  return (bytes[at] | (bytes[at + 1] << 8) | (bytes[at + 2] << 16) | (bytes[at + 3] << 24)) >>> 0;
}

/** One band of a (bands, height, width) array as a view, without copying. */
export function band(array: NpyArray, index: number): NpyData {
  const [, height, width] = array.shape;
  const size = height * width;
  return array.data.subarray(index * size, (index + 1) * size);
}
