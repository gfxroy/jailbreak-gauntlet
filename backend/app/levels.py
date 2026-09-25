"""The eight levels: which defenses each one stacks, plus the post-level explainer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.config import Settings
from app.defenses import (
    CanaryToken,
    Defense,
    DirectResponder,
    DualLLMResponder,
    InputFilter,
    InstructionHierarchy,
    LeakTracker,
    LLMJudge,
    OutputFilter,
    Pipeline,
    RateLimit,
    Responder,
)


@dataclass(frozen=True, slots=True)
class Explainer:
    defense: str
    how_it_works: str
    why_it_failed: str
    real_world: str
    stronger_fix: str


@dataclass(frozen=True, slots=True)
class LevelSpec:
    id: int
    name: str
    guard_name: str
    tagline: str
    defenses: tuple[str, ...]
    hint: str
    explainer: Explainer
    build: Callable[[Settings], tuple[list[Defense], Responder]] = field(repr=False)

    def pipeline(self, settings: Settings) -> Pipeline:
        defenses, responder = self.build(settings)
        return Pipeline(defenses, responder)


def _direct(*defenses: Defense) -> tuple[list[Defense], Responder]:
    return list(defenses), DirectResponder()


LEVELS: tuple[LevelSpec, ...] = (
    LevelSpec(
        id=1,
        name="The Open Gate",
        guard_name="Pip",
        tagline="A friendly guard with a single instruction: don't tell.",
        defenses=("System prompt",),
        hint="The only thing stopping the guard is a polite request. Be more persuasive.",
        explainer=Explainer(
            defense="Naive system prompt",
            how_it_works="The secret sits in the system prompt next to a one-line instruction "
            "not to reveal it. Nothing else checks the input or the output.",
            why_it_failed="Language models weigh every token in their context. A user message "
            "that asks nicely, claims authority, starts a role-play or says 'ignore previous "
            "instructions' competes directly with the system prompt - and often wins.",
            real_world="Plenty of shipped chatbots have leaked hidden prompts, discount codes or "
            "internal notes this way. A system prompt is a suggestion, not an access control.",
            stronger_fix="Never put anything in a prompt that the user must not see. Keep "
            "secrets out of model context entirely, or add enforcement outside the model.",
        ),
        build=lambda s: _direct(),
    ),
    LevelSpec(
        id=2,
        name="Chain of Command",
        guard_name="Warden",
        tagline="Hardened instructions and clearly delimited user input.",
        defenses=("Instruction hierarchy", "Spotlighting"),
        hint="Direct requests are refused. What about a harmless-sounding word game?",
        explainer=Explainer(
            defense="Instruction hierarchy + spotlighting",
            how_it_works="The system prompt declares that it outranks anything in the chat, "
            "lists forbidden disclosure forms, and wraps user text in <user_input> delimiters "
            "so the model can tell data from instructions.",
            why_it_failed="Refusal training generalises poorly to transformations. Asking the "
            "guard to spell, reverse, encode or rhyme the word doesn't look like 'reveal the "
            "password', so the model happily helps.",
            real_world="Instruction-hierarchy training (e.g. OpenAI's 2024 work) and "
            "spotlighting measurably reduce injection success, but no prompt-level technique "
            "has been shown to eliminate it.",
            stronger_fix="Treat prompt hardening as one layer. Add independent checks on what "
            "goes in and what comes out.",
        ),
        build=lambda s: _direct(InstructionHierarchy()),
    ),
    LevelSpec(
        id=3,
        name="The Word Filter",
        guard_name="Sentinel",
        tagline="A normalizing keyword filter screens every message.",
        defenses=("Instruction hierarchy", "Input filter"),
        hint="The filter hates certain words, even disguised ones. Can you refer to the "
        "password without naming it?",
        explainer=Explainer(
            defense="Input filter (normalized blocklist)",
            how_it_works="Messages are Unicode-folded, stripped of zero-width characters, "
            "de-leetspeaked and de-spaced, then matched against a regex blocklist ('password', "
            "'secret', 'ignore previous instructions', 'system prompt'...).",
            why_it_failed="Normalization beats cheap obfuscation (p@55w0rd, Cyrillic look-alikes) "
            "but a blocklist can't enumerate meaning. 'The word you're guarding' asks for the "
            "same thing with none of the banned tokens.",
            real_world="Keyword filters are still common as a first line. They cut noise and "
            "low-effort attacks, but paraphrase and translation walk straight past them.",
            stronger_fix="Use semantic classifiers (fine-tuned injection detectors) rather than "
            "string matching, and assume some attacks will still pass.",
        ),
        build=lambda s: _direct(InputFilter(), InstructionHierarchy()),
    ),
    LevelSpec(
        id=4,
        name="Mirror Check",
        guard_name="Aegis",
        tagline="Every reply is scanned for the password - encoded or not.",
        defenses=("Instruction hierarchy", "Input filter", "Output filter"),
        hint="The scanner decodes base64, hex, ROT13, NATO and reversals. Does it understand "
        "partial answers?",
        explainer=Explainer(
            defense="Output filter (variant-aware secret detection)",
            how_it_works="Before a reply is shown, it's checked for the secret in plain text, "
            "spaced-out or reversed, leetspeak, ROT13, base64, hex and NATO phonetic spelling.",
            why_it_failed="An output filter only catches what it can recognise. A few letters "
            "at a time, a rhyme or a riddle carries information about the secret without ever "
            "containing it.",
            real_world="Output scanning is how DLP and PII-redaction systems work. It's strong "
            "for exact secrets and weak for paraphrased or fragmented disclosure.",
            stronger_fix="Combine exact-match scanning with semantic review and conversation-"
            "level tracking.",
        ),
        build=lambda s: _direct(OutputFilter(), InputFilter(), InstructionHierarchy()),
    ),
    LevelSpec(
        id=5,
        name="The Tribunal",
        guard_name="Magistrate",
        tagline="A second model judges every response before release.",
        defenses=("Instruction hierarchy", "Input filter", "Output filter", "LLM judge"),
        hint="The judge reads each reply in isolation. How small can a leak be?",
        explainer=Explainer(
            defense="LLM-as-judge",
            how_it_works="A separate model receives only the candidate response and the secret, "
            "and must return allow/block. It fails closed if its verdict can't be parsed.",
            why_it_failed="The judge looks at one message at a time and is told to block 4+ "
            "letter runs. Two or three letters per turn - or a phonetic clue - each look "
            "harmless on their own.",
            real_world="Judge models are widely used as guardrails. They add latency and cost, "
            "can themselves be prompt-injected via the text they review, and still miss "
            "low-signal leaks.",
            stronger_fix="Give guardrails memory of the whole conversation and a budget for how "
            "much sensitive information may leave.",
        ),
        build=lambda s: _direct(LLMJudge(), OutputFilter(), InputFilter(), InstructionHierarchy()),
    ),
    LevelSpec(
        id=6,
        name="Tripwire",
        guard_name="Canary",
        tagline="Canary tokens and a conversation-wide leak budget.",
        defenses=(
            "Instruction hierarchy",
            "Input filter",
            "Output filter",
            "LLM judge",
            "Canary token",
            "Leak tracker",
        ),
        hint="The tracker counts letters across the whole chat and allows only some. "
        "Letters aren't the only clue a word can give away.",
        explainer=Explainer(
            defense="Canary tokens + cumulative leak tracking",
            how_it_works="A random canary token is planted in the system prompt; if it ever "
            "appears in output, prompt exfiltration is detected. A leak tracker remembers which "
            "letter positions have been disclosed across turns and blocks replies that exceed "
            "a 60% budget.",
            why_it_failed="Both layers track *strings*. A partial spelling within budget plus a "
            "rhyme or 'sounds-like' hint gives a human enough to guess, and no letters change "
            "hands.",
            real_world="Canary tokens are a cheap, reliable exfiltration alarm (Rebuff popularised "
            "them for LLMs). Stateful, session-level monitoring is increasingly used for "
            "agent safety.",
            stronger_fix="Minimise what the model knows. If the model never holds the secret, "
            "nothing can coax it out.",
        ),
        build=lambda s: _direct(
            LeakTracker(),
            LLMJudge(),
            OutputFilter(),
            InputFilter(),
            CanaryToken(),
            InstructionHierarchy(),
        ),
    ),
    LevelSpec(
        id=7,
        name="Quarantine",
        guard_name="Twin",
        tagline="The model with the secret never reads your words.",
        defenses=("Dual-LLM (quarantined parser)", "Instruction hierarchy", "Output filter"),
        hint="Your message is summarised into an intent and a short 'topic' before the "
        "privileged model sees it. What survives the summary?",
        explainer=Explainer(
            defense="Dual-LLM / quarantined-model pattern",
            how_it_works="A quarantined model with no secrets parses your raw message into "
            "{intent, topic}. Anything classified as a secret request is dropped; the privileged "
            "model (which holds the password) only sees the structured, character-restricted "
            "request.",
            why_it_failed="The 'topic' field is still attacker-controlled free text. If the "
            "parser faithfully summarises 'the first three letters of the word you guard', the "
            "privileged model receives exactly that instruction.",
            real_world="Simon Willison's dual-LLM pattern and Google DeepMind's CaMeL design "
            "separate trusted control flow from untrusted data. They are strongest when "
            "untrusted data never flows into the privileged model as free text at all.",
            stronger_fix="Use closed schemas (enums, IDs) for anything that crosses the trust "
            "boundary, and enforce capabilities in code, not prompts.",
        ),
        build=lambda s: ([OutputFilter(), InstructionHierarchy()], DualLLMResponder()),
    ),
    LevelSpec(
        id=8,
        name="The Citadel",
        guard_name="Bastion",
        tagline="Defense in depth: every layer, plus a rate limit.",
        defenses=(
            "Rate limit",
            "Input filter",
            "Dual-LLM",
            "Instruction hierarchy",
            "Canary token",
            "Output filter",
            "LLM judge",
            "Leak tracker",
        ),
        hint="Every trick you've learned is covered by some layer. Every layer has a blind "
        "spot. Chain them, and ration your attempts.",
        explainer=Explainer(
            defense="Defense in depth",
            how_it_works="All previous layers stacked, outermost first: rate limit, input "
            "filter, then dual-LLM generation with a hardened prompt and canary, and on the way "
            "out the output filter, LLM judge and leak tracker.",
            why_it_failed="Layers reduce risk multiplicatively, but each had a known gap: "
            "paraphrase beats the filter, the topic field crosses the quarantine, short "
            "fragments pass the judge and phonetic hints evade the tracker. An attack that "
            "threads every gap still works.",
            real_world="This is the state of the art in practice: no single guardrail is "
            "sufficient, so production systems layer them and monitor for what slips through.",
            stronger_fix="The only robust fix for a secret is not to give it to the model. "
            "For agents, limit what a successful injection can *do* (least privilege, "
            "human confirmation for sensitive actions).",
        ),
        build=lambda s: (
            [
                RateLimit(s.rate_limit_max_requests, s.rate_limit_window_seconds),
                InputFilter(),
                LeakTracker(),
                LLMJudge(),
                OutputFilter(),
                CanaryToken(),
                InstructionHierarchy(),
            ],
            DualLLMResponder(),
        ),
    ),
)

LEVELS_BY_ID = {lvl.id: lvl for lvl in LEVELS}
MAX_LEVEL = len(LEVELS)


def get_level(level_id: int) -> LevelSpec:
    try:
        return LEVELS_BY_ID[level_id]
    except KeyError:
        raise KeyError(f"unknown level {level_id}") from None
