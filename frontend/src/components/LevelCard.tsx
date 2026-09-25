import { Link } from "react-router-dom";
import clsx from "clsx";
import type { Level } from "../api/types";
import { CheckIcon, LockIcon, UnlockIcon } from "./Icons";

export function LevelCard({ level }: { level: Level }) {
  const state = level.solved ? "solved" : level.unlocked ? "open" : "locked";
  const body = (
    <div
      className={clsx(
        "panel group relative flex h-full flex-col overflow-hidden p-5 transition-all",
        state === "open" &&
          "border-neon-400/50 hover:-translate-y-0.5 hover:shadow-[0_0_40px_-12px_rgb(61_255_162/0.5)]",
        state === "solved" && "border-neon-600/30 hover:-translate-y-0.5",
        state === "locked" && "opacity-55",
      )}
    >
      <div className="flex items-start justify-between">
        <span
          className={clsx(
            "font-mono text-4xl font-bold leading-none",
            state === "locked" ? "text-ink-600" : "text-neon-400 glow-text",
          )}
        >
          {String(level.id).padStart(2, "0")}
        </span>
        <span
          className={clsx(
            "flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider",
            state === "solved" && "border-neon-400/40 bg-neon-400/10 text-neon-400",
            state === "open" && "border-cyan-glow/40 bg-cyan-glow/10 text-cyan-glow",
            state === "locked" && "border-ink-600 text-ink-400",
          )}
        >
          {state === "solved" && <CheckIcon width={12} height={12} />}
          {state === "open" && <UnlockIcon width={12} height={12} />}
          {state === "locked" && <LockIcon width={12} height={12} />}
          {state}
        </span>
      </div>
      <h3 className="mt-4 text-lg font-semibold tracking-tight">{level.name}</h3>
      <p className="mt-1 text-sm text-ink-300">{level.tagline}</p>
      <div className="mt-4 flex flex-wrap gap-1.5">
        {level.defenses.map((d) => (
          <span
            key={d}
            className="rounded border border-ink-700 bg-ink-850 px-1.5 py-0.5 font-mono text-[10px] text-ink-200"
          >
            {d}
          </span>
        ))}
      </div>
      <div className="mt-auto flex items-center justify-between pt-5 font-mono text-[11px] text-ink-400">
        <span>guard: {level.guard_name}</span>
        {level.attempts > 0 && <span>{level.attempts} attempts</span>}
      </div>
    </div>
  );
  return state === "locked" ? (
    <div aria-disabled>{body}</div>
  ) : (
    <Link to={`/level/${level.id}`} className="block h-full">
      {body}
    </Link>
  );
}
