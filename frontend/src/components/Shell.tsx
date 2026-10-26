import { ExternalLink } from "lucide-react";
import { NavLink, Outlet } from "react-router";

import { cn } from "@/lib/utils";

const PAGES = [
  { to: "/", label: "Cities", end: true },
  { to: "/results", label: "Results", end: false },
  { to: "/models", label: "Models", end: false },
  { to: "/findings", label: "Findings", end: false },
  { to: "/references", label: "References", end: false },
];

const DOCUMENTS = [
  { href: "/pages/proposal.html", label: "Proposal" },
  { href: "/pages/model_pipeline.html", label: "Model pipeline" },
];

/** The instrument strip: the wordmark, the pages, and the two documents that open in their own tab. */
export function Shell() {
  return (
    <div className="min-h-dvh flex flex-col">
      <header className="bg-bar text-bar-foreground">
        <div className="mx-auto flex w-full max-w-6xl items-center gap-6 px-4 py-3">
          <a href="/" className="font-display text-xl font-bold tracking-tight">
            <span className="mr-2 inline-block h-4 w-1.5 bg-sun align-[-2px]" aria-hidden="true" />
            shadecast
          </a>
          <nav aria-label="Pages" className="flex items-center gap-1">
            {PAGES.map((page) => (
              <NavLink
                key={page.to}
                to={page.to}
                end={page.end}
                className={({ isActive }) =>
                  cn(
                    "rounded-sm px-2.5 py-1 text-sm transition-colors hover:bg-bar-foreground/10",
                    isActive && "bg-bar-foreground/15 font-medium",
                  )
                }
              >
                {page.label}
              </NavLink>
            ))}
          </nav>
          <nav aria-label="Documents" className="ml-auto flex items-center gap-1">
            {DOCUMENTS.map((document) => (
              <a
                key={document.href}
                href={document.href}
                target="_blank"
                rel="noopener"
                className="inline-flex items-center gap-1 rounded-sm px-2.5 py-1 text-sm text-bar-foreground/80 transition-colors hover:bg-bar-foreground/10 hover:text-bar-foreground"
              >
                {document.label}
                <ExternalLink className="size-3.5" aria-hidden="true" />
              </a>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
