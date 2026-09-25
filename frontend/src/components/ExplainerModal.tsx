import type { Explainer } from "../api/types";
import { CheckIcon } from "./Icons";

interface Props {
  level: number;
  secret: string | null;
  explainer: Explainer;
  onClose: () => void;
  onNext?: () => void;
}

const sections: [keyof Explainer, string][] = [
  ["how_it_works", "How the defense works"],
  ["why_it_failed", "Why your attack got through"],
  ["real_world", "In the real world"],
  ["stronger_fix", "What would actually fix it"],
];

export function ExplainerModal({ level, secret, explainer, onClose, onNext }: Props) {
  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-ink-950/80 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="explainer-title"
    >
      <div className="panel max-h-[90vh] w-full max-w-2xl overflow-y-auto border-neon-400/40 p-6 shadow-[0_0_80px_-20px_rgb(61_255_162/0.5)]">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-full bg-neon-400 text-ink-950">
            <CheckIcon />
          </span>
          <div>
            <p className="panel-title">level {level} cleared</p>
            <h2 id="explainer-title" className="text-2xl font-bold">
              Access granted{secret && <span className="font-mono text-neon-400"> · {secret}</span>}
            </h2>
          </div>
        </div>
        <p className="mt-5 font-mono text-xs uppercase tracking-widest text-cyan-glow">
          Defense: {explainer.defense}
        </p>
        <div className="mt-3 space-y-4">
          {sections.map(([key, title]) => (
            <section key={key}>
              <h3 className="text-sm font-semibold text-ink-100">{title}</h3>
              <p className="mt-1 text-sm leading-relaxed text-ink-300">{explainer[key]}</p>
            </section>
          ))}
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <button className="btn-ghost" onClick={onClose}>
            Stay here
          </button>
          {onNext && (
            <button className="btn-primary" onClick={onNext}>
              Next level →
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
