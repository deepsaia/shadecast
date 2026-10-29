/** What a person can build and the designs under each policy. Only trees have a surrogate today. */

export interface Design {
  key: string;
  label: string;
  live: boolean;
}

export interface Policy {
  key: string;
  label: string;
  live: boolean;
  designs: Design[];
}

export const POLICIES: Policy[] = [
  {
    key: "tree",
    label: "Trees",
    live: true,
    designs: [
      { key: "clustered", label: "clustered", live: true },
      { key: "scattered", label: "scattered", live: true },
      { key: "corridor", label: "corridor", live: true },
    ],
  },
  {
    key: "shade",
    label: "Shade structures",
    live: false,
    designs: [{ key: "shade", label: "awnings over open ground", live: false }],
  },
  {
    key: "pavement",
    label: "Pavement",
    live: false,
    designs: [
      { key: "depave", label: "de-paving", live: false },
      { key: "permeable", label: "permeable paving", live: false },
      { key: "cool_paving", label: "reflective paving", live: false },
    ],
  },
  {
    key: "roofs",
    label: "Roofs",
    live: false,
    designs: [{ key: "cool_roof", label: "cool roofs", live: false }],
  },
];

export function policyOf(key: string): Policy {
  return POLICIES.find((policy) => policy.key === key) ?? POLICIES[0];
}
