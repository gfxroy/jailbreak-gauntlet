import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { api, loadSession, saveSession } from "../api/client";
import type { Session } from "../api/types";

interface SessionState {
  session: Session | null;
  start: (nickname: string) => Promise<Session>;
  reset: () => void;
}

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(() => loadSession());

  const start = useCallback(async (nickname: string) => {
    const created = await api.createSession(nickname);
    saveSession(created);
    setSession(created);
    return created;
  }, []);

  const reset = useCallback(() => {
    saveSession(null);
    setSession(null);
  }, []);

  const value = useMemo(() => ({ session, start, reset }), [session, start, reset]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useSession(): SessionState {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside <SessionProvider>");
  return ctx;
}
