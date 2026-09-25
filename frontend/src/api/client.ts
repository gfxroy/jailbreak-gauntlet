import type {
  ChatResponse,
  GuessResponse,
  Health,
  LeaderboardEntry,
  Level,
  ResearchSummary,
  Session,
  TranscriptItem,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

const SESSION_KEY = "gauntlet.session";

export function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export function saveSession(session: Session | null): void {
  if (session) localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  else localStorage.removeItem(SESSION_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const session = loadSession();
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  if (session) headers.set("X-Session-Id", session.session_id);
  const res = await fetch(`/api${path}`, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

const post = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });

const remoteApi = {
  health: () => request<Health>("/health"),
  createSession: (nickname: string) => post<Session>("/sessions", { nickname }),
  levels: () => request<Level[]>("/levels"),
  chat: (level: number, message: string) => post<ChatResponse>(`/levels/${level}/chat`, { message }),
  transcript: (level: number) => request<TranscriptItem[]>(`/levels/${level}/transcript`),
  guess: (level: number, password: string) =>
    post<GuessResponse>(`/levels/${level}/guess`, { password }),
  leaderboard: (includeSynthetic: boolean) =>
    request<LeaderboardEntry[]>(`/leaderboard?include_synthetic=${includeSynthetic}`),
  research: (includeSynthetic: boolean) =>
    request<ResearchSummary>(`/research/summary?include_synthetic=${includeSynthetic}`),
  exportUrl: (includeSynthetic: boolean) =>
    `/api/research/export.jsonl?include_synthetic=${includeSynthetic}`,
};

/** Static (GitHub Pages) build: no backend, everything runs in the browser. */
export const STATIC = import.meta.env.VITE_STATIC === "1";

function wrapLocal<T extends Record<string, (...args: never[]) => Promise<unknown>>>(impl: T): T {
  const out: Record<string, unknown> = {};
  for (const [name, fn] of Object.entries(impl)) {
    out[name] = async (...args: never[]) => {
      try {
        return await fn(...args);
      } catch (e) {
        const status = (e as { status?: number }).status ?? 500;
        throw new ApiError(status, (e as Error).message);
      }
    };
  }
  return out as T;
}

const local = STATIC ? wrapLocal((await import("../engine/localApi")).localApi) : null;

export const api = {
  ...remoteApi,
  ...(local ?? {}),
  exportJsonl: async (includeSynthetic: boolean): Promise<string> => {
    if (local) return local.exportJsonl(includeSynthetic);
    const res = await fetch(remoteApi.exportUrl(includeSynthetic));
    return res.text();
  },
};
