/** What a tile lacks and the one command that produces it, in the server's own words. */
export function NextStep({ missing, command }: { missing: string; command: string }) {
  return (
    <div className="rounded-md border border-dashed p-4 text-sm">
      <p>
        This tile has no {missing} yet. Produce it with:
      </p>
      <pre className="mt-2 overflow-x-auto rounded-sm bg-secondary px-3 py-2 text-[13px]">{command}</pre>
    </div>
  );
}
