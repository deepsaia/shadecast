/** MapLibre in miniature for jsdom, which has no WebGL: records what the map was told and lets a test fire events. */

type Handler = (event: unknown) => void;

export class FakeSource {
  data: unknown = null;
  image: unknown = null;
  setData(data: unknown) {
    this.data = data;
  }
  updateImage(image: unknown) {
    this.image = image;
  }
}

export class FakeMap {
  static instances: FakeMap[] = [];
  handlers = new Map<string, Handler[]>();
  sources = new Map<string, FakeSource>();
  layers: string[] = [];
  filters = new Map<string, unknown>();
  paints = new Map<string, unknown>();
  layouts = new Map<string, unknown>();
  fitted: unknown[] = [];
  removed = false;
  canvas = { style: { cursor: "" } };

  constructor(public options: unknown) {
    FakeMap.instances.push(this);
    queueMicrotask(() => this.fire("load", {}));
  }

  on(event: string, layerOrHandler: string | Handler, handler?: Handler) {
    const key = typeof layerOrHandler === "string" ? `${event}:${layerOrHandler}` : event;
    const found = typeof layerOrHandler === "string" ? handler : layerOrHandler;
    if (found) this.handlers.set(key, [...(this.handlers.get(key) ?? []), found]);
    return this;
  }

  fire(key: string, event: unknown) {
    for (const handler of this.handlers.get(key) ?? []) handler(event);
  }

  addSource(id: string) {
    this.sources.set(id, new FakeSource());
  }
  getSource(id: string) {
    return this.sources.get(id);
  }
  addLayer(layer: { id: string }) {
    this.layers.push(layer.id);
  }
  setFilter(id: string, filter: unknown) {
    this.filters.set(id, filter);
  }
  setPaintProperty(id: string, name: string, value: unknown) {
    this.paints.set(`${id}.${name}`, value);
  }
  setLayoutProperty(id: string, name: string, value: unknown) {
    this.layouts.set(`${id}.${name}`, value);
  }
  fitBounds(bounds: unknown, options: unknown) {
    this.fitted.push({ bounds, options });
  }
  getCanvas() {
    return this.canvas;
  }
  remove() {
    this.removed = true;
  }
}

export const fakeMaplibre = { Map: FakeMap };
