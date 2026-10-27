import type { UseQueryResult } from "@tanstack/react-query";

/** The two states every page shares before it has data: waiting, and the server not answering. */
export function Loading({ query, what }: { query: UseQueryResult<unknown>; what: string }) {
  if (query.isPending) return <p className="mt-8 text-muted-foreground">Loading {what}.</p>;
  if (query.isError) {
    return (
      <p className="mt-8 text-destructive" role="alert">
        The server did not answer: {query.error.message}. Start it with <code>sdc serve</code>.
      </p>
    );
  }
  return null;
}
