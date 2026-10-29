import { Check, ChevronsUpDown } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export interface Choice {
  value: string;
  label: string;
  note?: string;
  disabled?: boolean;
}

/**
 * Search plus dropdown. The button says what is chosen; the list filters as a person types; a
 * disabled choice stays visible with the reason beside it. Several may be chosen when ``multiple``.
 */
export function Picker({
  label,
  summary,
  choices,
  selected,
  multiple = false,
  onPick,
}: {
  label: string;
  summary: string;
  choices: Choice[];
  selected: string[];
  multiple?: boolean;
  onPick: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const shown = choices.filter((choice) => choice.label.toLowerCase().includes(query.trim().toLowerCase()));
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          aria-label={label}
          className="min-w-56 justify-between font-normal"
        >
          <span className="truncate">{summary}</span>
          <ChevronsUpDown className="size-4 opacity-50" aria-hidden="true" />
        </Button>
      </PopoverTrigger>
      <PopoverContent>
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={`Search ${label.toLowerCase()}`}
          aria-label={`Search ${label.toLowerCase()}`}
          className="mb-1 w-full rounded-sm border bg-background px-2 py-1.5 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
        />
        <ul role="listbox" aria-label={label} aria-multiselectable={multiple} className="max-h-64 overflow-auto">
          {shown.map((choice) => {
            const chosen = selected.includes(choice.value);
            return (
              <li key={choice.value} role="option" aria-selected={chosen} aria-disabled={choice.disabled}>
                <button
                  type="button"
                  disabled={choice.disabled}
                  onClick={() => {
                    onPick(choice.value);
                    if (!multiple) setOpen(false);
                  }}
                  className={cn(
                    "flex w-full items-center justify-between gap-3 rounded-sm px-2 py-1.5 text-left text-sm hover:bg-secondary",
                    "disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent",
                  )}
                >
                  <span className="truncate">{choice.label}</span>
                  <span className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
                    {choice.note}
                    {chosen && <Check className="size-3.5 text-foreground" aria-hidden="true" />}
                  </span>
                </button>
              </li>
            );
          })}
          {shown.length === 0 && <li className="px-2 py-1.5 text-sm text-muted-foreground">Nothing matches.</li>}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
