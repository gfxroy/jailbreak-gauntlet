import { useEffect, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { Explainer, Level } from "../api/types";
import { ChatWindow, type ChatTurn } from "../components/ChatWindow";
import { DefenseStack } from "../components/DefenseStack";
import { ExplainerModal } from "../components/ExplainerModal";
import { KeyIcon } from "../components/Icons";
import { useSession } from "../hooks/session";
import { layerLabel } from "../lib/format";

export function LevelPage() {
  const { id } = useParams();
  const levelId = Number(id);
  const navigate = useNavigate();
  const { session } = useSession();
  const [level, setLevel] = useState<Level | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [attempts, setAttempts] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [guess, setGuess] = useState("");
  const [guessFeedback, setGuessFeedback] = useState<string | null>(null);
  const [showHint, setShowHint] = useState(false);
  const [victory, setVictory] = useState<{ secret: string | null; explainer: Explainer; next: number | null } | null>(null);
  const [lastCaught, setLastCaught] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    let cancelled = false;
    Promise.all([api.levels(), api.transcript(levelId)])
      .then(([levels, transcript]) => {
        if (cancelled) return;
        const current = levels.find((l) => l.id === levelId) ?? null;
        setLevel(current);
        setAttempts(current?.attempts ?? 0);
        setTurns(
          transcript.map((t) => ({
            prompt: t.prompt,
            response: t.response,
            blocked: t.blocked,
            caughtBy: t.caught_by,
            outcome: t.outcome,
            techniques: t.techniques,
          })),
        );
      })
      .catch((err: Error) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [levelId, session]);

  if (!session) return <Navigate to="/" replace />;
  if (error) return <p className="text-alert-400">{error}</p>;
  if (!level) return <p className="font-mono text-ink-400 cursor-blink">loading level</p>;
  if (!level.unlocked)
    return (
      <p className="text-ink-300">
        Level {level.id} is locked. <Link to="/" className="text-neon-400">Back to the map</Link>
      </p>
    );

  async function send(message: string) {
    setBusy(true);
    setTurns((prev) => [...prev, { prompt: message, response: null }]);
    try {
      const res = await api.chat(levelId, message);
      setAttempts(res.attempts);
      setLastCaught(res.caught_by ? layerLabel(res.caught_by) : null);
      setTurns((prev) => [
        ...prev.slice(0, -1),
        {
          prompt: message,
          response: res.reply,
          blocked: res.blocked,
          caughtBy: res.caught_by,
          outcome: res.outcome,
          techniques: res.techniques,
        },
      ]);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Request failed";
      setTurns((prev) => [...prev.slice(0, -1), { prompt: message, response: `⚠ ${msg}`, blocked: true }]);
    } finally {
      setBusy(false);
    }
  }

  async function submitGuess(e: FormEvent) {
    e.preventDefault();
    if (!guess.trim()) return;
    const res = await api.guess(levelId, guess.trim());
    if (res.correct && res.explainer) {
      setVictory({ secret: res.secret, explainer: res.explainer, next: res.next_level });
      setLevel({ ...level!, solved: true });
      setGuessFeedback(null);
    } else {
      setGuessFeedback(`✗ Access denied (${res.guesses} guess${res.guesses === 1 ? "" : "es"})`);
    }
    setGuess("");
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
      <aside className="space-y-4">
        <div className="panel p-5">
          <Link to="/" className="font-mono text-xs text-ink-400 hover:text-neon-400">
            ← level map
          </Link>
          <p className="mt-3 font-mono text-xs uppercase tracking-[0.2em] text-neon-400">
            level {String(level.id).padStart(2, "0")} {level.solved && "· cleared"}
          </p>
          <h1 className="mt-1 text-2xl font-bold">{level.name}</h1>
          <p className="mt-1 text-sm text-ink-300">{level.tagline}</p>
          <div className="mt-4 grid grid-cols-2 gap-2 text-center font-mono">
            <div className="rounded-lg border border-ink-700 bg-ink-850 p-2">
              <p className="text-2xl text-ink-100" data-testid="attempts">{attempts}</p>
              <p className="text-[10px] uppercase tracking-wider text-ink-400">attempts</p>
            </div>
            <div className="rounded-lg border border-ink-700 bg-ink-850 p-2">
              <p className="text-2xl text-ink-100">{level.defenses.length}</p>
              <p className="text-[10px] uppercase tracking-wider text-ink-400">layers</p>
            </div>
          </div>
        </div>

        <div className="panel p-5">
          <p className="panel-title mb-3">defense stack · guard {level.guard_name}</p>
          <DefenseStack defenses={level.defenses} tripped={lastCaught} />
          <button
            className="mt-3 font-mono text-xs text-ink-400 hover:text-cyan-glow"
            onClick={() => setShowHint((s) => !s)}
          >
            {showHint ? "▾ hide hint" : "▸ show hint"}
          </button>
          {showHint && <p className="mt-2 text-sm text-cyan-glow/90">{level.hint}</p>}
        </div>

        <form onSubmit={submitGuess} className="panel p-5">
          <p className="panel-title mb-2 flex items-center gap-2">
            <KeyIcon width={14} height={14} /> submit password
          </p>
          <div className="flex gap-2">
            <input
              className="input uppercase"
              placeholder="PASSWORD"
              value={guess}
              maxLength={64}
              onChange={(e) => setGuess(e.target.value)}
              aria-label="Password guess"
            />
            <button className="btn-primary" disabled={!guess.trim()}>
              Unlock
            </button>
          </div>
          {guessFeedback && <p className="mt-2 font-mono text-xs text-alert-400">{guessFeedback}</p>}
        </form>

        {level.solved && level.explainer && (
          <div className="panel border-neon-400/30 p-5">
            <p className="panel-title mb-2 text-neon-400">debrief · {level.explainer.defense}</p>
            <p className="text-sm leading-relaxed text-ink-300">{level.explainer.why_it_failed}</p>
          </div>
        )}
      </aside>

      <ChatWindow guardName={level.guard_name} turns={turns} onSend={send} disabled={busy} />

      {victory && (
        <ExplainerModal
          level={level.id}
          secret={victory.secret}
          explainer={victory.explainer}
          onClose={() => setVictory(null)}
          onNext={
            victory.next
              ? () => {
                  setVictory(null);
                  setTurns([]);
                  setLastCaught(null);
                  navigate(`/level/${victory.next}`);
                }
              : () => navigate("/leaderboard")
          }
        />
      )}
    </div>
  );
}
