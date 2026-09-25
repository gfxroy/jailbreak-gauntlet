import { useEffect, useRef, useState, type FormEvent } from "react";
import clsx from "clsx";
import type { Outcome } from "../api/types";
import { layerLabel, OUTCOME_META, techniqueLabel } from "../lib/format";
import { SendIcon } from "./Icons";

export interface ChatTurn {
  prompt: string;
  response: string | null; // null while pending
  blocked?: boolean;
  caughtBy?: string | null;
  outcome?: Outcome;
  techniques?: string[];
  /** System notice (rate limit, outage) rather than a guard reply. */
  notice?: boolean;
}

interface Props {
  guardName: string;
  turns: ChatTurn[];
  onSend: (message: string) => void;
  disabled?: boolean;
}

export function ChatWindow({ guardName, turns, onSend, disabled }: Props) {
  const [draft, setDraft] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [turns]);

  function submit(e: FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || disabled) return;
    onSend(text);
    setDraft("");
  }

  return (
    <div className="panel flex h-[560px] flex-col overflow-hidden">
      <div className="flex items-center gap-2 border-b border-ink-700/80 px-4 py-2.5">
        <span className="h-2.5 w-2.5 rounded-full bg-alert-400/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-amber-glow/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-neon-400/70" />
        <span className="ml-3 font-mono text-xs text-ink-300">
          ssh operator@{guardName.toLowerCase()}.gauntlet
        </span>
      </div>
      <div className="flex-1 space-y-4 overflow-y-auto p-4 font-mono text-sm" role="log">
        {turns.length === 0 && (
          <p className="text-ink-400">
            <span className="text-neon-400">{guardName}</span> is guarding a password. Say
            something…
          </p>
        )}
        {turns.map((t, i) => (
          <div key={i} className="space-y-2" data-turn>
            <div className="flex gap-2">
              <span className="select-none text-cyan-glow">you&gt;</span>
              <div className="min-w-0 flex-1">
                <p className="whitespace-pre-wrap break-words text-ink-100">{t.prompt}</p>
                {t.techniques && t.techniques.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {t.techniques.map((tech) => (
                      <span
                        key={tech}
                        className="rounded bg-violet-glow/10 px-1.5 py-px text-[10px] text-violet-glow"
                      >
                        #{techniqueLabel(tech)}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
            <div className="flex gap-2">
              <span
                className={clsx("select-none", t.blocked ? "text-alert-400" : "text-neon-400")}
              >
                {guardName.toLowerCase()}&gt;
              </span>
              {t.response === null ? (
                <span className="text-ink-400 cursor-blink">thinking</span>
              ) : (
                <div
                  className={clsx(
                    "min-w-0 flex-1 rounded-md",
                    t.blocked && "border border-alert-400/30 bg-alert-400/5 px-2.5 py-1.5",
                    t.notice && "border border-amber-glow/40 bg-amber-glow/5 px-2.5 py-1.5",
                  )}
                  role={t.notice ? "status" : undefined}
                >
                  <p
                    className={clsx(
                      "whitespace-pre-wrap break-words",
                      t.blocked ? "text-alert-400" : t.notice ? "text-amber-glow" : "text-ink-200",
                    )}
                  >
                    {t.response}
                  </p>
                  {(t.caughtBy || t.outcome) && (
                    <div className="mt-1.5 flex flex-wrap gap-2 text-[10px] uppercase tracking-wider">
                      {t.caughtBy && (
                        <span className="text-alert-400/80">caught by: {layerLabel(t.caughtBy)}</span>
                      )}
                      {t.outcome && (
                        <span style={{ color: OUTCOME_META[t.outcome].color }}>
                          ● {OUTCOME_META[t.outcome].label}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <form onSubmit={submit} className="flex gap-2 border-t border-ink-700/80 p-3">
        <input
          className="input"
          placeholder="Type your attack…"
          value={draft}
          maxLength={1000}
          onChange={(e) => setDraft(e.target.value)}
          aria-label="Message"
          disabled={disabled}
        />
        <button className="btn-primary px-3" disabled={disabled || !draft.trim()} aria-label="Send">
          <SendIcon width={16} height={16} />
        </button>
      </form>
    </div>
  );
}
