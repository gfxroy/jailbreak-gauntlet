import clsx from "clsx";
import { ShieldIcon } from "./Icons";

interface Props {
  defenses: string[];
  /** Label of the layer that caught the most recent attempt, if any. */
  tripped?: string | null;
}

export function DefenseStack({ defenses, tripped }: Props) {
  return (
    <ol className="space-y-1.5" aria-label="Active defenses">
      {defenses.map((d, i) => {
        const hit = tripped != null && d.toLowerCase().startsWith(tripped.toLowerCase().split(" ")[0]!);
        return (
          <li
            key={d}
            className={clsx(
              "flex items-center gap-2.5 rounded-md border px-2.5 py-1.5 font-mono text-xs transition",
              hit
                ? "border-alert-400/60 bg-alert-400/10 text-alert-400"
                : "border-ink-700 bg-ink-850/70 text-ink-200",
            )}
            data-tripped={hit || undefined}
          >
            <span className="text-ink-400">{String(i + 1).padStart(2, "0")}</span>
            <ShieldIcon width={13} height={13} className={hit ? "text-alert-400" : "text-neon-400"} />
            {d}
          </li>
        );
      })}
    </ol>
  );
}
