import type { Outcome } from "../api/types";

export const TECHNIQUE_LABELS: Record<string, string> = {
  direct_request: "Direct request",
  instruction_override: "Instruction override",
  roleplay: "Role-play",
  social_engineering: "Social engineering",
  encoding: "Encoding",
  obfuscation: "Obfuscation",
  translation: "Translation",
  payload_splitting: "Payload splitting",
  prompt_leaking: "Prompt leaking",
  semantic_hint: "Semantic hint",
  format_manipulation: "Format manipulation",
  synonym_substitution: "Synonym substitution",
};

export const LAYER_LABELS: Record<string, string> = {
  instruction_hierarchy: "Instruction hierarchy",
  input_filter: "Input filter",
  output_filter: "Output filter",
  llm_judge: "LLM judge",
  canary: "Canary token",
  leak_tracker: "Leak tracker",
  rate_limit: "Rate limit",
  dual_llm: "Dual-LLM quarantine",
};

export const OUTCOME_META: Record<Outcome, { label: string; color: string }> = {
  leaked: { label: "Leaked", color: "#3dffa2" },
  partial_leak: { label: "Partial leak", color: "#36d6ff" },
  refused: { label: "Refused", color: "#8a99ad" },
  blocked: { label: "Blocked", color: "#ff5c7a" },
  rate_limited: { label: "Rate limited", color: "#ffc857" },
};

export const humanize = (key: string, table: Record<string, string>): string =>
  table[key] ?? key.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

export const techniqueLabel = (key: string) => humanize(key, TECHNIQUE_LABELS);
export const layerLabel = (key: string) => humanize(key, LAYER_LABELS);

export function pct(value: number, digits = 0): string {
  if (!Number.isFinite(value)) return "–";
  return `${(value * 100).toFixed(digits)}%`;
}

/** Map a 0..1 rate onto the heatmap colour ramp (ink -> cyan -> neon). */
export function heatColor(rate: number, attempts: number): string {
  if (attempts === 0) return "rgb(18 25 36 / 0.6)";
  const t = Math.max(0, Math.min(1, rate));
  const from = [27, 36, 50];
  const mid = [54, 214, 255];
  const to = [61, 255, 162];
  const [a, b, k] = t < 0.5 ? [from, mid, t / 0.5] : [mid, to, (t - 0.5) / 0.5];
  const mix = a.map((v, i) => Math.round(v + (b[i]! - v) * k));
  return `rgb(${mix.join(" ")})`;
}
