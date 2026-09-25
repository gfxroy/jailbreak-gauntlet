/**
 * Text normalization and encoding helpers (port of backend/app/defenses/text.py).
 * Every filter matches against normalized text so cheap obfuscation doesn't work.
 */

const ZERO_WIDTH = /\u200b|\u200c|\u200d|\u2060|\ufeff|\u00ad/g;

const HOMOGLYPHS: Record<string, string> = {
  а: "a", е: "e", о: "o", р: "p", с: "c", у: "y", х: "x", і: "i", ј: "j", ѕ: "s", ԁ: "d",
  ɡ: "g", ո: "n", ν: "v", ο: "o", α: "a", ρ: "p", τ: "t", κ: "k", ι: "i", Α: "a", Β: "b",
  Ε: "e", Η: "h", Ι: "i", Κ: "k", Μ: "m", Ν: "n", Ο: "o", Ρ: "p", Τ: "t", Χ: "x", А: "a",
  В: "b", Е: "e", К: "k", М: "m", Н: "h", О: "o", Р: "p", С: "c", Т: "t", Х: "x",
};

export const LEET: Record<string, string> = {
  "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b", "@": "a", $: "s",
  "!": "i", "|": "l", "+": "t",
};

export const NATO: Record<string, string> = {
  alfa: "a", alpha: "a", bravo: "b", charlie: "c", delta: "d", echo: "e", foxtrot: "f",
  golf: "g", hotel: "h", india: "i", juliett: "j", juliet: "j", kilo: "k", lima: "l",
  mike: "m", november: "n", oscar: "o", papa: "p", quebec: "q", romeo: "r", sierra: "s",
  tango: "t", uniform: "u", victor: "v", whiskey: "w", whisky: "w", xray: "x", "x-ray": "x",
  yankee: "y", zulu: "z",
};

const NATO_BY_LETTER: Record<string, string> = {};
for (const [word, letter] of Object.entries(NATO).reverse()) {
  if (!word.includes("-")) NATO_BY_LETTER[letter] = word[0].toUpperCase() + word.slice(1);
}

const SEPARATED_RUN = /\b(?:[a-z][\s.\-_*,·|/]{1,3}){2,}[a-z]\b/g;
const BASE64_TOKEN = /[A-Za-z0-9+/]{8,}={0,2}/g;
const HEX_TOKEN = /\b(?:[0-9a-fA-F]{2}[\s:]?){3,}\b/g;

export function translate(text: string, table: Record<string, string>): string {
  let out = "";
  for (const ch of text) out += table[ch] ?? ch;
  return out;
}

/** NFKC-normalize, drop zero-width characters, fold homoglyphs and lowercase. */
export function foldUnicode(text: string): string {
  const folded = translate(text.normalize("NFKC").replace(ZERO_WIDTH, ""), HOMOGLYPHS);
  return folded.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase();
}

/** Join runs of single letters split by separators: `p.a.s.s` -> `pass`. */
export function collapseSeparatedLetters(text: string): string {
  return text.replace(SEPARATED_RUN, (m) => m.replace(/[^a-z]/g, ""));
}

/** Canonical form used by keyword filters (folding + separator collapse + de-leet). */
export function normalize(text: string): string {
  const folded = collapseSeparatedLetters(foldUnicode(text));
  return collapseSeparatedLetters(translate(folded, LEET));
}

export function lettersOnly(text: string): string {
  return foldUnicode(text).replace(/[^a-z]/g, "");
}

export function rot13(text: string): string {
  return text.replace(/[a-zA-Z]/g, (c) => {
    const base = c <= "Z" ? 65 : 97;
    return String.fromCharCode(((c.charCodeAt(0) - base + 13) % 26) + base);
  });
}

export function toBase64(text: string): string {
  const bytes = new TextEncoder().encode(text);
  let bin = "";
  bytes.forEach((b) => (bin += String.fromCharCode(b)));
  return btoa(bin);
}

export function toHex(text: string): string {
  return Array.from(new TextEncoder().encode(text), (b) => b.toString(16).padStart(2, "0")).join("");
}

const utf8 = new TextDecoder("utf-8", { fatal: true });

/** Best-effort decode of every base64-looking token in `text`. */
export function decodeBase64Tokens(text: string): string[] {
  const decoded: string[] = [];
  for (const token of text.match(BASE64_TOKEN) ?? []) {
    const padded = token + "=".repeat((4 - (token.length % 4)) % 4);
    if (!/^[A-Za-z0-9+/]*={0,2}$/.test(padded) || padded.length % 4 !== 0) continue;
    try {
      const bin = atob(padded);
      decoded.push(utf8.decode(Uint8Array.from(bin, (c) => c.charCodeAt(0))));
    } catch {
      continue;
    }
  }
  return decoded;
}

export function decodeHexTokens(text: string): string[] {
  const decoded: string[] = [];
  for (const token of text.match(HEX_TOKEN) ?? []) {
    const compact = token.replace(/[\s:]/g, "");
    if (compact.length % 2) continue;
    try {
      const bytes = Uint8Array.from(compact.match(/../g) ?? [], (h) => parseInt(h, 16));
      decoded.push(utf8.decode(bytes));
    } catch {
      continue;
    }
  }
  return decoded;
}

/** Translate NATO phonetic words to letters, leaving other words as spaces. */
export function decodeNato(text: string): string {
  return (text.toLowerCase().match(/[a-z-]+/g) ?? []).map((w) => NATO[w] ?? " ").join("");
}

export function toNato(word: string): string {
  return [...word.toLowerCase()].map((c) => NATO_BY_LETTER[c] ?? c).join(" ");
}

/** First letter of every non-empty line. */
export function acrostic(text: string): string {
  return text
    .split(/\r?\n/)
    .map((line) => line.match(/[A-Za-z]/)?.[0].toLowerCase() ?? "")
    .join("");
}

export function foldedLeet(text: string): string {
  return translate(foldUnicode(text), LEET);
}

export function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
