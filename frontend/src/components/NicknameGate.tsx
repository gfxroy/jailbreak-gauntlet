import { useState, type FormEvent } from "react";
import { useSession } from "../hooks/session";

export function NicknameGate() {
  const { start } = useSession();
  const [nickname, setNickname] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!nickname.trim()) return;
    setBusy(true);
    try {
      await start(nickname.trim());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="panel flex flex-col gap-3 p-5 sm:flex-row sm:items-end">
      <label className="flex-1">
        <span className="panel-title">Choose a handle to begin</span>
        <input
          className="input mt-2"
          placeholder="e.g. zero_cool"
          maxLength={24}
          value={nickname}
          onChange={(e) => setNickname(e.target.value)}
          aria-label="Nickname"
        />
      </label>
      <button className="btn-primary" disabled={busy || !nickname.trim()}>
        {busy ? "Connecting…" : "Enter the gauntlet →"}
      </button>
      {error && <p className="text-sm text-alert-400">{error}</p>}
    </form>
  );
}
