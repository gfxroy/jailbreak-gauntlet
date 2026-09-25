import { Link } from "react-router-dom";
import clsx from "clsx";
import type { Level } from "../api/types";
import { CheckIcon, LockIcon, UnlockIcon } from "./Icons";

export function LevelCard({ level }: { level: Level }) {
  const state = level.solved ? "solved" : level.unlocked ? "open" : "locked";
  const body = (
    <div
      className={clsx(
        "panel group relative flex h-full flex-col overflow-hidden p-6 transition-all duration-200",
        state === "open" && "border-white/20 hover:border-white/35 hover:bg-[#18181b]",
        state === "solved" && "border-emerald-500/20 hover:border-emerald-500/30 hover:bg-[#18181b]",
        state === "locked" && "opacity-50",
      )}
    >
      <div className="flex items-start justify-between">
        <span className="font-mono text-2xl font-medium tracking-tight text-white/80">
          {String(level.id).padStart(2, "0")}
        </span>
        <span
          className={clsx(
            "flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium tracking-wide capitalize",
            state === "solved" && "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
            state === "open" && "border-white/15 bg-white/[0.05] text-white",
            state === "locked" && "border-white/5 bg-white/[0.02] text-ink-400",
          )}
        >
          {state === "solved" && <CheckIcon width={12} height={12} />}
          {state === "open" && <UnlockIcon width={12} height={12} />}
          {state === "locked" && <LockIcon width={12} height={12} />}
          {state}
        </span>
      </div>
      <h3 className="mt-4 text-base font-semibold tracking-tight text-white">{level.name}</h3>
      <p className="mt-1 text-sm text-ink-300 leading-relaxed">{level.tagline}</p>
      <div className="mt-4 flex flex-wrap gap-1.5">
        {level.defenses.map((d) => (
          <span
            key={d}
            className="rounded-md border border-white/[0.06] bg-white/[0.03] px-2 py-0.5 text-[11px] text-ink-300"
          >
            {d}
          </span>
        ))}
      </div>
      <div className="mt-auto flex items-center justify-between pt-6 text-xs text-ink-400">
        <span>Guard: {level.guard_name}</span>
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
