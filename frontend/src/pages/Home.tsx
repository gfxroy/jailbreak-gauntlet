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
    <div className="space-y-8">
      <section className="grid gap-6 lg:grid-cols-[1.4fr_1fr] lg:items-end">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-neon-400">
            prompt-injection ctf · defense research harness
          </p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight xl:text-[3.25rem] xl:leading-[1.1]">
            Eight guards. Eight passwords.
            <br />
            <span className="text-ink-300">Every defense has a </span>
            <span className="whitespace-nowrap text-neon-400 glow-text cursor-blink">blind spot</span>
          </h1>
          <p className="mt-4 max-w-2xl text-ink-300">
            Each level wraps an AI guard in a real, well-known prompt-injection defense, from a
            polite system prompt to a full defense-in-depth stack. Talk the guard into leaking its
            password, then learn exactly why the defense failed. Every attempt feeds the research
            dashboard.
          </p>
        </div>
        {session ? (
          <div className="panel p-5">
            <p className="panel-title">operator</p>
            <p className="mt-1 font-mono text-2xl text-neon-400">{session.nickname}</p>
            <div className="mt-4 flex items-center gap-3">
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-ink-800">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-cyan-glow to-neon-400 transition-all"
                  style={{ width: `${(solved / 8) * 100}%` }}
                />
              </div>
              <span className="font-mono text-sm text-ink-200">{solved}/8</span>
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
