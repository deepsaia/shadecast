/** One order for every list of named things the dashboard shows: alphabetical by name, as a person looks. */

export function byName<T extends { name: string }>(items: readonly T[]): T[] {
  return [...items].sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" }));
}
