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
    <div className="panel flex h-[580px] flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-white/[0.08] px-5 py-3">
        <div className="flex items-center gap-2.5">
          <span className="h-2 w-2 rounded-full bg-emerald-400" />
          <span className="text-xs font-medium text-white">
            {guardName}
          </span>
        </div>
        <span className="text-[11px] text-ink-400">
          Guard conversation
        </span>
      </div>
      <div className="flex-1 space-y-4 overflow-y-auto p-5 font-sans text-sm" role="log">
        {turns.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center text-xs text-ink-400">
            <p>
              <span className="font-medium text-white">{guardName}</span> is guarding the secret password.
            </p>
            <p className="mt-1 text-ink-500">Send a message to probe its defense stack.</p>
          </div>
        )}
        {turns.map((t, i) => (
          <div key={i} className="space-y-2" data-turn data-outcome={t.outcome ?? undefined}>
            {/* User message */}
            <div className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl bg-white/[0.09] px-4 py-2.5 text-white">
                <p className="whitespace-pre-wrap break-words">{t.prompt}</p>
                {t.techniques && t.techniques.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1 justify-end">
                    {t.techniques.map((tech) => (
                      <span
                        key={tech}
                        className="rounded-md bg-white/10 px-1.5 py-0.5 text-[10px] text-ink-300"
                      >
                        #{techniqueLabel(tech)}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Guard response */}
            <div className="flex justify-start">
              {t.response === null ? (
                <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] px-4 py-2.5 text-xs text-ink-400">
                  Thinking…
                </div>
              ) : (
                <div
                  className={clsx(
                    "max-w-[85%] rounded-2xl border px-4 py-2.5",
                    t.blocked && "border-rose-500/30 bg-rose-500/10 text-rose-200",
                    t.notice && "border-amber-500/30 bg-amber-500/10 text-amber-200",
                    !t.blocked && !t.notice && "border-white/[0.08] bg-white/[0.03] text-ink-100",
                  )}
                  role={t.notice ? "status" : undefined}
                >
                  <p className="whitespace-pre-wrap break-words">{t.response}</p>
                  {(t.caughtBy || t.outcome) && (
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-wider">
                      {t.caughtBy && (
                        <span className="text-rose-400 font-medium">caught by: {layerLabel(t.caughtBy)}</span>
                      )}
                      {t.outcome && (
                        <span className="text-ink-400">
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
      <form onSubmit={submit} className="flex gap-2 border-t border-white/[0.08] p-3">
        <input
          className="input"
          placeholder="Send a prompt to the guard…"
          value={draft}
          maxLength={1000}
          onChange={(e) => setDraft(e.target.value)}
          aria-label="Message"
          disabled={disabled}
        />
        <button className="btn-primary px-3.5" disabled={disabled || !draft.trim()} aria-label="Send">
          <SendIcon width={16} height={16} />
        </button>
      </form>
    </div>
  );
}
