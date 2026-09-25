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
              "flex items-center gap-2.5 rounded-xl border px-3 py-2 text-xs font-sans transition-all duration-150",
              hit
                ? "border-rose-500/40 bg-rose-500/10 text-rose-200"
                : "border-white/[0.06] bg-white/[0.02] text-ink-200",
            )}
            data-tripped={hit || undefined}
          >
            <span className="font-mono text-[10px] text-ink-400">{String(i + 1).padStart(2, "0")}</span>
            <ShieldIcon width={13} height={13} className={hit ? "text-rose-400" : "text-neutral-400"} />
            <span className="font-medium">{d}</span>
          </li>
        );
      })}
    </ol>
  );
}
