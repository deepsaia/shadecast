import { cn } from "@/lib/utils";

export interface Chip {
  key: string;
  label: string;
  live?: boolean;
  color?: string;
}

/** Compact rounded choices, one pressed at a time; a chip that is not live says so and cannot be pressed. */
export function Chips({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: Chip[];
  value: string | null;
  onChange: (key: string) => void;
}) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-1.5">
      {options.map((option) => {
        const live = option.live ?? true;
        const pressed = option.key === value;
        return (
          <button
            key={option.key}
            type="button"
            disabled={!live}
            aria-pressed={pressed}
            title={live ? undefined : "coming soon"}
            onClick={() => onChange(option.key)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs transition-colors",
              pressed ? "border-foreground bg-foreground text-background" : "bg-card hover:bg-secondary",
              !live && "cursor-not-allowed opacity-60 hover:bg-card",
            )}
          >
            {option.color && (
              <span className="inline-block size-2 rounded-full" style={{ background: option.color }} aria-hidden="true" />
            )}
            {option.label}
            {!live && <span className="text-[10px] text-muted-foreground">coming soon</span>}
          </button>
        );
      })}
    </div>
  );
}
