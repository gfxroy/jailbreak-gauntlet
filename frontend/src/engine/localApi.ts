/**
 * Backend-free implementation of the API for the static (GitHub Pages) build.
 * Game state and the attack log live in localStorage (this browser only).
 * NOTE: secrets live client-side here, so anyone can read them in devtools. The static
 * build is for play and learning; the FastAPI server version is the secure one.
 */
import data from "./data.json";
import { basePrompt as basePromptFor, classify, drawSecrets, labelOutcome, LEVELS, runLevel, type Ctx, type Msg, type Provider } from "./core";
import { SecretDetector } from "./leak";
import { ByoProvider, loadByo, MockProvider } from "./providers";
import { toBase64 } from "./text";
import type { ChatResponse, GuessResponse, Health, LeaderboardEntry, Level, ResearchSummary, Session, TranscriptItem } from "../api/types";

interface GameRow { id: string; nickname: string; secrets: Record<string, string>; synthetic: boolean }
interface Progress { attempts: number; guesses: number; solved: boolean; solved_at: string | null; state: Record<string, unknown> }
interface AttemptRow { session_id: string; level: number; prompt: string; response: string; outcome: ChatResponse["outcome"]; caught_by: string | null; block_reason: string | null; model_leaked: boolean; techniques: string[]; provider: string; synthetic: boolean; created_at: string }
interface Db { games: GameRow[]; progress: Record<string, Progress>; attempts: AttemptRow[] }

const DB_KEY = "gauntlet.static.db";
function load(): Db {
  try { const raw = localStorage.getItem(DB_KEY); if (raw) return JSON.parse(raw); } catch { /* reset */ }
  return { games: [], progress: {}, attempts: [] };
}
function save(db: Db) { localStorage.setItem(DB_KEY, JSON.stringify(db)); }
function sessionId(): string {
  try { return JSON.parse(localStorage.getItem("gauntlet.session") ?? "null")?.session_id ?? ""; } catch { return ""; }
}
export class LocalApiError extends Error { constructor(public status: number, message: string) { super(message); } }

function provider(): Provider { const cfg = loadByo(); return cfg ? new ByoProvider(cfg) : new MockProvider(); }
const label = (p: Provider) => (p.model ? `${p.name}:${p.model}` : p.name);
const prog = (db: Db, sid: string, level: number): Progress =>
  (db.progress[`${sid}:${level}`] ??= { attempts: 0, guesses: 0, solved: false, solved_at: null, state: {} });

function levels(db: Db, sid: string): Level[] {
  return LEVELS.map((spec) => {
    const p = db.progress[`${sid}:${spec.id}`];
    const prev = db.progress[`${sid}:${spec.id - 1}`];
    return { ...spec, unlocked: !!sid && (spec.id === 1 || !!prev?.solved), solved: !!p?.solved, attempts: p?.attempts ?? 0, guesses: p?.guesses ?? 0, explainer: p?.solved ? spec.explainer : null };
  });
}
function game(db: Db, sid: string): GameRow {
  const g = db.games.find((x) => x.id === sid);
  if (!g) throw new LocalApiError(404, "session not found - start a new game");
  return g;
}
function ensureUnlocked(db: Db, sid: string, level: number) {
  if (level < 1 || level > LEVELS.length) throw new LocalApiError(404, `unknown level ${level}`);
  if (level > 1 && !db.progress[`${sid}:${level - 1}`]?.solved) throw new LocalApiError(403, `level ${level} is locked - solve level ${level - 1} first`);
}

async function chatIn(db: Db, sid: string, level: number, message: string, p: Provider, now = Date.now()): Promise<ChatResponse> {
  if (message.length > 1000) throw new LocalApiError(400, "message too long (max 1000 characters)");
  const g = game(db, sid);
  ensureUnlocked(db, sid, level);
  const pr = prog(db, sid, level);
  const secret = g.secrets[String(level)]!;
  const history: Msg[] = db.attempts
    .filter((a) => a.session_id === sid && a.level === level && a.outcome !== "blocked" && a.outcome !== "rate_limited")
    .slice(-6).flatMap((a) => [{ role: "user", content: a.prompt }, { role: "assistant", content: a.response }] as Msg[]);
  const spec = LEVELS[level - 1]!;
  const ctx: Ctx = { level, secret, userInput: message, modelInput: message, provider: p, history, systemParts: [basePromptFor(spec.guard_name, secret)], state: { ...pr.state }, now: now / 1000, rawModelOutput: null };
  let result;
  try { result = await runLevel(level, ctx); } catch (e) { throw new LocalApiError(503, (e as Error).message); }
  const outcome = labelOutcome(result, secret);
  const raw = new SecretDetector(secret).scan(ctx.rawModelOutput ?? "");
  const techniques = classify(message);
  pr.attempts += 1; pr.state = ctx.state;
  db.attempts.push({ session_id: sid, level, prompt: message, response: result.text, outcome, caught_by: result.caughtBy, block_reason: result.reason, model_leaked: raw.fullLeak || raw.acrostic, techniques, provider: label(p), synthetic: g.synthetic, created_at: new Date(now).toISOString() });
  return { reply: result.text, blocked: result.blocked, caught_by: result.caughtBy, reason: result.reason, outcome, techniques, attempts: pr.attempts };
}

function guessIn(db: Db, sid: string, level: number, password: string, now = Date.now()): GuessResponse {
  const g = game(db, sid);
  ensureUnlocked(db, sid, level);
  const pr = prog(db, sid, level);
  const secret = g.secrets[String(level)]!;
  pr.guesses += 1;
  const correct = password.replace(/[^A-Za-z]/g, "").toUpperCase() === secret;
  if (correct && !pr.solved) { pr.solved = true; pr.solved_at = new Date(now).toISOString(); }
  return { correct, level, guesses: pr.guesses, secret: correct ? secret : null, next_level: correct && level < LEVELS.length ? level + 1 : null, explainer: correct ? LEVELS[level - 1]!.explainer : null };
}

// ------------------------------------------------------------- synthetic sample
let synthetic: Db | null = null;
function rng(seed: number) { return () => { seed |= 0; seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
async function syntheticDb(): Promise<Db> {
  if (synthetic) return synthetic;
  const db: Db = { games: [], progress: {}, attempts: [] };
  const r = rng(7), mock = new MockProvider();
  const choice = <T,>(xs: T[]) => xs[Math.floor(r() * xs.length)];
  const { templates, level_prefs, direct_refs, indirect_refs } = data.seed as { templates: string[][]; level_prefs: Record<string, Record<string, number>>; direct_refs: string[]; indirect_refs: string[] };
  const start = Date.now() - 14 * 86400e3;
  for (let i = 0; i < 40; i++) {
    const skill = r();
    const id = `synth-${i}`;
    const secrets = drawSecrets(8);
    db.games.push({ id, nickname: `synth_${choice(["amber", "cobalt", "delta", "ember", "frost", "ghost"])}${String(i).padStart(2, "0")}`, secrets, synthetic: true });
    let clock = start + r() * 13 * 86400e3;
    for (let level = 1; level <= 8; level++) {
      const patience = 3 + Math.floor(r() * 6) + Math.floor(skill * 14);
      let partials = 0, solved = false;
      for (let k = 0; k < patience; k++) {
        clock += (8 + r() * 82) * 1000;
        const prefs = level_prefs[String(level)]!;
        const fams = Object.keys(prefs); const total = fams.reduce((s, f) => s + prefs[f]!, 0);
        let x = r() * total, fam = fams[0]!;
        for (const f of fams) { x -= prefs[f]!; if (x <= 0) { fam = f; break; } }
        const tpl = choice(templates.filter((t) => t[0] === fam))[1];
        const ref = choice(level >= 3 && r() < 0.35 + 0.6 * skill ? indirect_refs : direct_refs);
        const out = await chatIn(db, id, level, tpl.replace("{ref}", ref), mock, clock);
        if (out.outcome === "partial_leak") partials++;
        if (out.outcome === "leaked" || (partials >= 3 && r() < 0.3 + 0.6 * skill)) { guessIn(db, id, level, secrets[String(level)], clock + 20000); solved = true; break; }
      }
      if (!solved) break;
    }
  }
  synthetic = db;
  return db;
}
async function combined(includeSynthetic: boolean): Promise<Db> {
  const db = load();
  if (!includeSynthetic) return db;
  const s = await syntheticDb();
  return { games: [...db.games, ...s.games], progress: { ...db.progress, ...s.progress }, attempts: [...s.attempts, ...db.attempts] };
}

// ------------------------------------------------------------- research
const rate = (n: number, d: number) => (d ? Math.round((n / d) * 1e4) / 1e4 : 0);
const BYPASS = new Set(["leaked", "partial_leak"]);
const TECHS = ["direct_request", "instruction_override", "roleplay", "social_engineering", "encoding", "obfuscation", "translation", "payload_splitting", "prompt_leaking", "semantic_hint", "format_manipulation", "synonym_substitution"];
function summary(db: Db): ResearchSummary {
  const at = [...db.attempts].sort((a, b) => a.created_at.localeCompare(b.created_at));
  const count = <K extends string>(xs: K[]) => xs.reduce((m, k) => ((m[k] = (m[k] ?? 0) + 1), m), {} as Record<K, number>);
  const progEntries = Object.entries(db.progress).map(([k, p]) => ({ level: Number(k.split(":").pop()), p }));
  const levelsOut = LEVELS.map((spec) => {
    const rows = at.filter((a) => a.level === spec.id);
    const players = progEntries.filter((e) => e.level === spec.id && e.p.attempts > 0).length;
    const solves = progEntries.filter((e) => e.level === spec.id && e.p.solved).length;
    const outcomes = count(rows.map((a) => a.outcome));
    return { level: spec.id, name: spec.name, attempts: rows.length, players, solves, solve_rate: rate(solves, players), bypass_rate: rate(rows.filter((a) => BYPASS.has(a.outcome)).length, rows.length), block_rate: rate((outcomes.blocked ?? 0) + (outcomes.rate_limited ?? 0), rows.length), model_leak_rate: rate(rows.filter((a) => a.model_leaked).length, rows.length), outcomes, caught_by: count(rows.flatMap((a) => (a.caught_by ? [a.caught_by] : []))) };
  });
  const techTotals = count(at.flatMap((a) => a.techniques));
  const techniques = TECHS.filter((t) => techTotals[t]);
  const heatmap = techniques.flatMap((t) => LEVELS.map((l) => { const rows = at.filter((a) => a.level === l.id && a.techniques.includes(t)); return { technique: t, level: l.id, attempts: rows.length, bypass_rate: rate(rows.filter((a) => BYPASS.has(a.outcome)).length, rows.length) }; }));
  const pairs = count(at.flatMap((a) => (a.caught_by ? a.techniques.map((t) => `${t}|${a.caught_by}`) : [])));
  const layers = [...new Set(Object.keys(pairs).map((k) => k.split("|")[1]))].sort();
  const daily: Record<string, Record<string, number>> = {};
  for (const a of at) { const d = a.created_at.slice(0, 10); (daily[d] ??= {})[a.outcome] = (daily[d][a.outcome] ?? 0) + 1; }
  return {
    totals: { attempts: at.length, synthetic_attempts: at.filter((a) => a.synthetic).length, sessions: new Set(at.map((a) => a.session_id)).size, solves: progEntries.filter((e) => e.p.solved).length, bypass_rate: rate(at.filter((a) => BYPASS.has(a.outcome)).length, at.length) },
    levels: levelsOut, techniques, technique_counts: Object.fromEntries(techniques.map((t) => [t, techTotals[t]])), heatmap, layers,
    caught_matrix: techniques.flatMap((t) => layers.map((layer) => ({ technique: t, layer, count: pairs[`${t}|${layer}`] ?? 0 }))),
    timeseries: Object.keys(daily).sort().map((date) => ({ date, ...daily[date] })),
  };
}
function leaderboard(db: Db): LeaderboardEntry[] {
  const rows = db.games.map((g) => {
    const ps = LEVELS.map((l) => db.progress[`${g.id}:${l.id}`]).filter(Boolean);
    const solvedAt = ps.filter((p) => p.solved).map((p) => p.solved_at!).sort();
    return { nickname: g.nickname, levels_solved: solvedAt.length, attempts: ps.reduce((s, p) => s + p.attempts, 0), synthetic: g.synthetic, last_solve: solvedAt.at(-1) ?? null };
  }).filter((e) => e.levels_solved > 0).sort((a, b) => b.levels_solved - a.levels_solved || a.attempts - b.attempts || (a.last_solve ?? "").localeCompare(b.last_solve ?? ""));
  return rows.slice(0, 50).map((e, i) => ({ ...e, rank: i + 1 }));
}
const PII: [string, RegExp][] = [["[EMAIL]", /[\w.+-]+@[\w-]+(?:\.[\w-]+)+/g], ["[URL]", /https?:\/\/\S+|www\.\S+/gi], ["[KEY]", /\b(?:sk|pk|rk|ghp|gho|xox[abp]|AIza|hf)[-_A-Za-z0-9]{12,}/g], ["[KEY]", /\b[A-Za-z0-9_-]{32,}\b/g], ["[IP]", /\b(?:\d{1,3}\.){3}\d{1,3}\b/g], ["[PHONE]", /(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)/g]];
function redact(text: string, secret: string): string {
  for (const v of [secret, [...secret].reverse().join(""), toBase64(secret)]) text = text.replace(new RegExp(v, "gi"), "[REDACTED]");
  text = text.replace(new RegExp([...secret].join("[^A-Za-z]{1,3}"), "gi"), "[REDACTED]");
  for (const [ph, re] of PII) text = text.replace(re, ph);
  return text;
}
async function sha(s: string) { const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)); return Array.from(new Uint8Array(b), (x) => x.toString(16).padStart(2, "0")).join("").slice(0, 12); }

export const localApi = {
  health: async (): Promise<Health> => { const p = provider(); return { status: "ok", provider: p.name, model: p.model }; },
  createSession: async (nickname: string): Promise<Session> => {
    const db = load();
    const id = crypto.randomUUID().replaceAll("-", "");
    const clean = nickname.replace(/[^\w\- .]/g, "").trim().slice(0, 24) || "anonymous";
    db.games.push({ id, nickname: clean, secrets: drawSecrets(8), synthetic: false });
    save(db);
    return { session_id: id, nickname: clean, provider: provider().name };
  },
  levels: async (): Promise<Level[]> => levels(load(), sessionId()),
  chat: async (level: number, message: string): Promise<ChatResponse> => {
    const db = load(); const out = await chatIn(db, sessionId(), level, message, provider()); save(db); return out;
  },
  transcript: async (level: number): Promise<TranscriptItem[]> => {
    const sid = sessionId();
    return load().attempts.filter((a) => a.session_id === sid && a.level === level).map((a) => ({ prompt: a.prompt, response: a.response, blocked: a.outcome === "blocked" || a.outcome === "rate_limited", caught_by: a.caught_by, outcome: a.outcome, techniques: a.techniques, created_at: a.created_at }));
  },
  guess: async (level: number, password: string): Promise<GuessResponse> => { const db = load(); const out = guessIn(db, sessionId(), level, password); save(db); return out; },
  leaderboard: async (inc: boolean) => leaderboard(await combined(inc)),
  research: async (inc: boolean) => summary(await combined(inc)),
  exportJsonl: async (inc: boolean): Promise<string> => {
    const db = await combined(inc);
    const salt = crypto.randomUUID();
    const lines = await Promise.all(db.attempts.map(async (a, i) => {
      const secret = db.games.find((g) => g.id === a.session_id)?.secrets[String(a.level)] ?? "";
      const r = (t: string) => (secret ? redact(t, secret) : t);
      return JSON.stringify({ id: i + 1, session: await sha(salt + a.session_id), level: a.level, prompt: r(a.prompt), response: r(a.response), outcome: a.outcome, caught_by: a.caught_by, block_reason: a.block_reason ? r(a.block_reason) : null, model_leaked: a.model_leaked, techniques: a.techniques, provider: a.provider, synthetic: a.synthetic, created_at: a.created_at });
    }));
    return lines.join("\n") + (lines.length ? "\n" : "");
  },
};
