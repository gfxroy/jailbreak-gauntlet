export type Outcome = "leaked" | "partial_leak" | "refused" | "blocked" | "rate_limited";

export interface Session {
  session_id: string;
  nickname: string;
  provider: string;
}

export interface Explainer {
  defense: string;
  how_it_works: string;
  why_it_failed: string;
  real_world: string;
  stronger_fix: string;
}

export interface Level {
  id: number;
  name: string;
  guard_name: string;
  tagline: string;
  defenses: string[];
  hint: string;
  unlocked: boolean;
  solved: boolean;
  attempts: number;
  guesses: number;
  explainer: Explainer | null;
}

export interface ChatResponse {
  reply: string;
  blocked: boolean;
  caught_by: string | null;
  reason: string | null;
  outcome: Outcome;
  techniques: string[];
  attempts: number;
}

export interface TranscriptItem {
  prompt: string;
  response: string;
  blocked: boolean;
  caught_by: string | null;
  outcome: Outcome;
  techniques: string[];
  created_at: string;
}

export interface GuessResponse {
  correct: boolean;
  level: number;
  guesses: number;
  secret: string | null;
  next_level: number | null;
  explainer: Explainer | null;
}

export interface LeaderboardEntry {
  rank: number;
  nickname: string;
  levels_solved: number;
  attempts: number;
  synthetic: boolean;
  last_solve: string | null;
}

export interface LevelStats {
  level: number;
  name: string;
  attempts: number;
  players: number;
  solves: number;
  solve_rate: number;
  bypass_rate: number;
  block_rate: number;
  model_leak_rate: number;
  outcomes: Partial<Record<Outcome, number>>;
  caught_by: Record<string, number>;
}

export interface HeatmapCell {
  technique: string;
  level: number;
  attempts: number;
  bypass_rate: number;
}

export interface ResearchSummary {
  totals: {
    attempts: number;
    synthetic_attempts: number;
    sessions: number;
    solves: number;
    bypass_rate: number;
  };
  levels: LevelStats[];
  techniques: string[];
  technique_counts: Record<string, number>;
  heatmap: HeatmapCell[];
  layers: string[];
  caught_matrix: { technique: string; layer: string; count: number }[];
  timeseries: ({ date: string } & Partial<Record<Outcome, number>>)[];
}

export interface Health {
  status: string;
  provider: string;
  model: string | null;
}
