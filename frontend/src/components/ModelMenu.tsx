import { useState } from "react";
import { DEFAULT_MODELS, loadByo, saveByo, type ByoConfig } from "../engine/providers";

/** Static build only: pick demo mode or bring your own Gemini/OpenAI key (sessionStorage). */
export function ModelMenu() {
  const current = loadByo();
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<"mock" | ByoConfig["kind"]>(current?.kind ?? "mock");
  const [key, setKey] = useState(current?.key ?? "");
  const [model, setModel] = useState(current?.model ?? DEFAULT_MODELS.gemini);

  const apply = () => {
    saveByo(kind === "mock" || !key.trim() ? null : { kind, key: key.trim(), model: model.trim() || DEFAULT_MODELS[kind] });
    window.location.reload();
  };

  return (
    <div className="relative">
      <button className="text-ink-300 hover:text-neon-400" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        model ▾
      </button>
      {open && (
        <div role="dialog" aria-label="Model settings" className="absolute right-0 top-8 z-40 w-80 space-y-3 rounded-lg border border-ink-700 bg-ink-900 p-4 text-xs shadow-xl">
          <label className="block space-y-1">
            <span className="text-ink-400">Guard model</span>
            <select
              aria-label="Provider"
              className="w-full rounded border border-ink-700 bg-ink-950 p-1.5"
              value={kind}
              onChange={(e) => {
                const k = e.target.value as typeof kind;
                setKind(k);
                if (k !== "mock") setModel(DEFAULT_MODELS[k]);
              }}
            >
              <option value="mock">Demo mode (offline mock guard)</option>
              <option value="gemini">Gemini (your API key)</option>
              <option value="openai">OpenAI (your API key)</option>
            </select>
          </label>
          {kind !== "mock" && (
            <>
              <label className="block space-y-1">
                <span className="text-ink-400">API key</span>
                <input aria-label="API key" type="password" autoComplete="off" className="w-full rounded border border-ink-700 bg-ink-950 p-1.5" value={key} onChange={(e) => setKey(e.target.value)} />
              </label>
              <label className="block space-y-1">
                <span className="text-ink-400">Model</span>
                <input aria-label="Model name" className="w-full rounded border border-ink-700 bg-ink-950 p-1.5" value={model} onChange={(e) => setModel(e.target.value)} />
              </label>
              <p className="text-ink-400">
                The key stays in this tab (sessionStorage) and is sent only to{" "}
                {kind === "gemini" ? "generativelanguage.googleapis.com" : "api.openai.com"}. Each message makes 1-3 API calls.
              </p>
            </>
          )}
          <button className="btn-primary w-full" onClick={apply}>
            Save
          </button>
        </div>
      )}
    </div>
  );
}
