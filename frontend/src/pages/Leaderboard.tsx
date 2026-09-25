import { useState } from "react";
import clsx from "clsx";
import { api } from "../api/client";
import { Toggle } from "../components/Toggle";
import { useAsync } from "../hooks/useAsync";
import { useSession } from "../hooks/session";

export function Leaderboard() {
  const [includeSynthetic, setIncludeSynthetic] = useState(true);
  const { session } = useSession();
  const { data, error } = useAsync(() => api.leaderboard(includeSynthetic), [includeSynthetic]);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-neon-400">leaderboard</p>
          <h1 className="mt-2 text-3xl font-bold">Top operators</h1>
          <p className="mt-1 text-sm text-ink-400">Ranked by levels cleared, then fewest attempts.</p>
        </div>
        <Toggle checked={includeSynthetic} onChange={setIncludeSynthetic} label="show synthetic players" />
      </header>
      {error && <p className="text-alert-400">{error.message}</p>}
      <div className="panel overflow-hidden">
        <table className="w-full font-mono text-sm">
          <thead className="border-b border-ink-700 text-left text-[11px] uppercase tracking-wider text-ink-400">
            <tr>
              <th className="px-5 py-3">#</th>
              <th className="px-5 py-3">operator</th>
              <th className="px-5 py-3">levels</th>
              <th className="px-5 py-3 text-right">attempts</th>
            </tr>
          </thead>
          <tbody>
            {data?.length === 0 && (
              <tr>
                <td colSpan={4} className="px-5 py-8 text-center text-ink-400">
                  Nobody has cleared a level yet. Be the first.
                </td>
              </tr>
            )}
            {data?.map((e) => (
              <tr
                key={`${e.rank}-${e.nickname}`}
                className={clsx(
                  "border-b border-ink-800 last:border-0",
                  session?.nickname === e.nickname && !e.synthetic && "bg-neon-400/5",
                )}
              >
                <td
                  className={clsx(
                    "px-5 py-3",
                    e.rank === 1 ? "text-amber-glow" : e.rank <= 3 ? "text-ink-100" : "text-ink-400",
                  )}
                >
                  {String(e.rank).padStart(2, "0")}
                </td>
                <td className="px-5 py-3">
                  {e.nickname}
                  {e.synthetic && (
                    <span className="ml-2 rounded border border-amber-glow/40 px-1.5 py-px text-[9px] uppercase text-amber-glow">
                      synthetic
                    </span>
                  )}
                </td>
                <td className="px-5 py-3">
                  <div className="flex items-center gap-1" aria-label={`${e.levels_solved} of 8 levels`}>
                    {Array.from({ length: 8 }, (_, i) => (
                      <span
                        key={i}
                        className={clsx(
                          "h-2.5 w-4 rounded-sm",
                          i < e.levels_solved ? "bg-neon-400" : "bg-ink-700",
                        )}
                      />
                    ))}
                    <span className="ml-2 text-xs text-ink-300">{e.levels_solved}/8</span>
                  </div>
                </td>
                <td className="px-5 py-3 text-right text-ink-200">{e.attempts}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
