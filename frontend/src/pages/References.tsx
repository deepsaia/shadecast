import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { Loading } from "@/components/Loading";

/** Every source the project reads from, in its group, with what it is used for. */
export function ReferencesPage() {
  const references = useQuery({ queryKey: ["references"], queryFn: api.references });
  return (
    <section>
      <h1>References</h1>
      <p className="mt-2 max-w-[60ch] text-muted-foreground">
        Every data source and every method this work rests on, as the registry cites them. Each entry says what it
        is used for.
      </p>
      <Loading query={references} what="the references" />
      {references.data?.map((group) => (
        <section key={group.key} className="mt-8">
          <h2>{group.title}</h2>
          <ol className="mt-3 space-y-3 text-sm">
            {group.sources.map((source) => (
              <li key={source.key} className="max-w-[72ch]">
                <span className="font-medium">{source.title}</span>
                {source.authors_or_publisher && <span className="text-muted-foreground">, {source.authors_or_publisher}</span>}
                {source.year && <span className="text-muted-foreground">, {source.year}</span>}
                {source.doi && (
                  <>
                    {" "}
                    <a href={`https://doi.org/${source.doi}`} target="_blank" rel="noopener" className="underline-offset-4 hover:underline">
                      doi:{source.doi}
                    </a>
                  </>
                )}
                <p className="text-muted-foreground">{source.used_for}</p>
              </li>
            ))}
          </ol>
        </section>
      ))}
    </section>
  );
}
