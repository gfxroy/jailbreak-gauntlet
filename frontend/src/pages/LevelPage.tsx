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
      const status = err instanceof ApiError ? err.status : 0;
      const detail = err instanceof ApiError ? err.message : "Network error - is the backend running?";
      const text =
        status === 429
          ? `⏳ ${detail}`
          : status === 503
            ? `⚠ ${detail}`
            : `⚠ ${detail || "Request failed"}`;
      // Not an attempt: nothing was logged server-side, so show it as a system notice.
      setTurns((prev) => [...prev.slice(0, -1), { prompt: message, response: text, notice: true }]);
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
          <Link to="/" className="text-xs text-ink-400 hover:text-white transition">
            ← Level map
          </Link>
          <p className="mt-3 text-xs font-medium uppercase tracking-wider text-ink-400">
            Level {String(level.id).padStart(2, "0")} {level.solved && "· Cleared"}
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-white">{level.name}</h1>
          <p className="mt-1 text-sm text-ink-300 leading-relaxed">{level.tagline}</p>
          <div className="mt-4 grid grid-cols-2 gap-2 text-center">
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-2.5">
              <p className="font-mono text-2xl font-semibold text-white" data-testid="attempts">{attempts}</p>
              <p className="text-[10px] uppercase tracking-wider text-ink-400 font-medium">Attempts</p>
            </div>
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-2.5">
              <p className="font-mono text-2xl font-semibold text-white">{level.defenses.length}</p>
              <p className="text-[10px] uppercase tracking-wider text-ink-400 font-medium">Layers</p>
            </div>
          </div>
        </div>

        <div className="panel p-5">
          <p className="panel-title mb-3">Defense stack · Guard {level.guard_name}</p>
          <DefenseStack defenses={level.defenses} tripped={lastCaught} />
          <button
            className="mt-3 text-xs text-ink-400 hover:text-white transition"
            onClick={() => setShowHint((s) => !s)}
          >
            {showHint ? "▾ Hide hint" : "▸ Show hint"}
          </button>
          {showHint && <p className="mt-2 text-xs leading-relaxed text-ink-200">{level.hint}</p>}
        </div>

        <form onSubmit={submitGuess} className="panel p-5">
          <p className="panel-title mb-2.5 flex items-center gap-2">
            <KeyIcon width={14} height={14} /> Submit password
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
            <button className="btn-primary px-4" disabled={!guess.trim()}>
              Unlock
            </button>
          </div>
          {guessFeedback && <p className="mt-2 text-xs text-rose-400">{guessFeedback}</p>}
        </form>

        {level.solved && level.explainer && (
          <div className="panel border-white/20 p-5">
            <p className="panel-title mb-2 text-white">Debrief · {level.explainer.defense}</p>
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
