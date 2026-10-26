/** The server's NPY writer in miniature, so tests can hand the client real arrays. */

export function encodeNpy(values: number[], shape: number[], dtype: "<f4" | "|b1"): ArrayBuffer {
  const shapeText = shape.join(", ") + (shape.length === 1 ? "," : "");
  let header = `{'descr': '${dtype}', 'fortran_order': False, 'shape': (${shapeText}), }`;
  while ((10 + header.length + 1) % 64 !== 0) header += " ";
  header += "\n";
  const body = dtype === "<f4" ? new Float32Array(values) : Uint8Array.from(values);
  const bytes = new Uint8Array(10 + header.length + body.byteLength);
  bytes.set([0x93, 0x4e, 0x55, 0x4d, 0x50, 0x59, 1, 0, header.length & 0xff, header.length >> 8], 0);
  bytes.set(new TextEncoder().encode(header), 10);
  bytes.set(new Uint8Array(body.buffer), 10 + header.length);
  return bytes.buffer;
}
