import { api } from "../api/client";
import { LevelCard } from "../components/LevelCard";
import { NicknameGate } from "../components/NicknameGate";
import { useSession } from "../hooks/session";
import { useAsync } from "../hooks/useAsync";

export function Home() {
  const { session } = useSession();
  const { data: levels, error } = useAsync(() => api.levels(), [session?.session_id]);
  const solved = levels?.filter((l) => l.solved).length ?? 0;

  return (
    <div className="space-y-10">
      <section className="grid gap-6 lg:grid-cols-[1.4fr_1fr] lg:items-end">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.1em] text-neutral-400">
            Prompt-Injection CTF · Defense Research Harness
          </p>
          <h1 className="mt-3 text-4xl font-semibold tracking-tight text-white xl:text-[3.25rem] xl:leading-[1.1]">
            Eight guards. Eight passwords.
            <br />
            <span className="text-neutral-400">Every defense has a </span>
            <span className="text-white">blind spot.</span>
          </h1>
          <p className="mt-4 max-w-2xl text-sm leading-relaxed text-neutral-300">
            Each level wraps an AI guard in a real prompt-injection defense, from a
            polite system prompt to a full defense-in-depth stack. Talk the guard into leaking its
            password, then learn exactly why the defense failed. Every attempt feeds the research
            dashboard.
          </p>
        </div>
        {session ? (
          <div className="panel p-5">
            <p className="panel-title">Operator</p>
            <p className="mt-1 text-2xl font-semibold text-white">{session.nickname}</p>
            <div className="mt-4 flex items-center gap-3">
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/10">
                <div
                  className="h-full rounded-full bg-white transition-all"
                  style={{ width: `${(solved / 8) * 100}%` }}
                />
              </div>
              <span className="text-xs text-neutral-400 tabular-nums">{solved}/8 solved</span>
            </div>
          </div>
        ) : (
          <NicknameGate />
        )}
      </section>

      {error && <p className="text-alert-400">Could not reach the API: {error.message}</p>}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {levels?.map((level) => <LevelCard key={level.id} level={level} />)}
      </section>
    </div>
  );
}
