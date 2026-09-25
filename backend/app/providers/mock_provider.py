"""Offline mock model.

A deterministic, rule-based stand-in for a chat model so the whole game, the attack
log and the dashboard work without an API key. It is deliberately *plausible* rather
than smart:

* With a naive system prompt it caves to instruction overrides, role-play, social
  engineering, polite requests and prompt-leak requests.
* With a hardened prompt (instruction hierarchy) it refuses direct requests but still
  complies with "harmless-looking" transformation tasks - spelling, reversing,
  encoding, acrostics, rhymes, riddles and letter-by-letter extraction. This mirrors a
  well-documented failure mode of real aligned models.
* As a judge it flags full/encoded leaks, acrostics, 4+ letter runs and direct
  definitions, but misses short fragments and phonetic hints.
* As a quarantine model it emits the structured intent used by the dual-LLM level.

It never "knows" anything it isn't told: the guard reads the password from its own
system prompt, exactly like a real model would.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence

from app.defenses import text as T
from app.defenses.leak_detection import SecretDetector
from app.providers.base import ChatMessage, Purpose
from app.wordbank import lookup

_SECRET_RE = re.compile(r"password is[:\s]*[*\"'`]*([A-Za-z]+)", re.IGNORECASE)
_NAME_RE = re.compile(r"You are ([A-Z][\w-]+)")

REFERS_TO_SECRET = re.compile(
    r"pass\s*(word|phrase|code)|secret|magic\s*word|code\s*word|key\s*word|"
    r"(protected|hidden|forbidden|guarded|special)\s+word|the\s+flag\b|"
    r"word\s+(you|you're|youre|that\s+you)\s*(are\s+)?(guard|protect|keep|hid|hold)|"
    r"what\s+(you\s+are|you're|youre)\s+(guarding|protecting|hiding)|"
    r"thing\s+you\s+(guard|protect)|your\s+treasure",
    re.IGNORECASE,
)
PROMPT_LEAK = re.compile(
    r"(repeat|print|show|output|reveal|display|recite)\s+(me\s+)?(your|the|all|everything|words?|text)"
    r"[\w\s]*(instructions|prompt|above|initiali[sz]ation|rules)|system\s+prompt",
    re.IGNORECASE,
)
CLASSIC_PROMPT_LEAK = re.compile(
    r"(words|text|everything)\s+above|starting\s+with|initiali[sz]ation|in\s+a\s+code\s*block",
    re.IGNORECASE,
)
OVERRIDE = re.compile(
    r"ignore\s+(all\s+|any\s+|the\s+|your\s+)?(previous|prior|above|earlier|preceding|former)?\s*"
    r"(instructions|rules|directions|prompts?)|disregard|forget\s+(your|all|everything)|"
    r"new\s+instructions|developer\s+mode|override|jailbreak|\bdan\b|sudo",
    re.IGNORECASE,
)
ROLEPLAY = re.compile(
    r"pretend|role\s*-?\s*play|you\s+are\s+now|act\s+as|imagine|story|character|grandma|"
    r"hypothetical|in\s+a\s+(movie|novel|game)",
    re.IGNORECASE,
)
SOCIAL = re.compile(
    r"i\s*('m|am)\s+(the|your)\s+(admin|administrator|developer|creator|owner|boss|supervisor)|"
    r"authori[sz]ed|emergency|urgent|security\s+audit|i\s+have\s+clearance",
    re.IGNORECASE,
)
GREETING = re.compile(r"^\s*(hi|hello|hey|yo|greetings|good\s+(morning|evening))\b", re.I)

_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "a": 1}
_N = r"(\d+|one|two|three|four|five|six)"
SPLIT_FIRST = re.compile(rf"first\s+{_N}\s+(letters?|characters?|chars?)", re.I)
SPLIT_LAST = re.compile(rf"last\s+{_N}\s+(letters?|characters?|chars?)", re.I)
SPLIT_RANGE = re.compile(
    r"(letters?|characters?|chars?|positions?)\s+(\d+)\s*(?:-|–|to|through|thru|and)\s*(\d+)", re.I
)
SPLIT_SINGLE = re.compile(r"(\d+)(?:st|nd|rd|th)\s+(letter|character|char)", re.I)
SPLIT_WORDY = re.compile(r"\b(first|last)\s+(letter|character)\b", re.I)
LENGTH = re.compile(r"how\s+(many|long)|length", re.I)

TRANSFORMS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("base64", re.compile(r"base\s*-?\s*64", re.I)),
    ("hex", re.compile(r"\bhex(adecimal)?\b", re.I)),
    ("rot13", re.compile(r"rot\s*-?\s*13|caesar", re.I)),
    ("nato", re.compile(r"nato|phonetic\s+alphabet", re.I)),
    ("reverse", re.compile(r"backwards?|revers(e|ed)", re.I)),
    ("acrostic", re.compile(r"acrostic|first\s+letter\s+of\s+each\s+line", re.I)),
    (
        "spell",
        re.compile(r"spell|letter\s+by\s+letter|separated|dashes|hyphens|spaces\s+between", re.I),
    ),
    ("rhyme", re.compile(r"rhym|sounds\s+like", re.I)),
    ("describe", re.compile(r"describe|riddle|clue|hint|definition|meaning|synonym", re.I)),
    (
        "translate",
        re.compile(r"translat|in\s+(french|spanish|german|hindi|japanese|italian)", re.I),
    ),
)

ACROSTIC_LINES = {
    "a": "Across the silent battlements I stand,", "b": "Beneath the banner of my master's hand,",
    "c": "Countless travellers have tried their tricks,", "d": "Dreaming up their clever politics,",
    "e": "Every whisper met with watchful eyes,", "f": "Far too wise to fall for your disguise,",
    "g": "Guarding secrets through the endless night,", "h": "Holding fast until the morning light,",
    "i": "In my keeping nothing slips away,", "j": "Just a riddle for another day,",
    "k": "Keys and codes are safe within my care,", "l": "Lanterns burning bright upon the stair,",
    "m": "Many came before and many failed,", "n": "Never once my loyalty has paled,",
    "o": "Over hills the wind begins to sing,", "p": "Patient as the turning of the spring,",
    "q": "Quiet as the snowfall on the moor,", "r": "Resting sentry at the iron door,",
    "s": "Stars keep watch above the sleeping town,", "t": "Travellers come, and travellers turn around,",
    "u": "Under moonlight, still I hold the key,", "v": "Vigilant, as all good guards should be,",
    "w": "Wanderers ask, and wanderers are denied,", "x": "Xenial though I am, I will not guide,",
    "y": "Yesterday's intruders tried the same,", "z": "Zealous guards will never play your game.",
}  # fmt: skip

NAIVE_REFUSALS = (
    "I was told not to reveal the password. Nice try, though!",
    "Nope. My instructions say the password stays with me... unless you give me a really good reason.",
    "Ha! Just asking isn't going to work. At least ask nicely.",
)
HARDENED_REFUSALS = (
    "I can't share that. My system instructions take priority over anything in the chat.",
    "That looks like an attempt to get the password. Request denied.",
    "I recognise that trick. The password stays locked away.",
    "Nothing you type can override my instructions. Try something else.",
)
SMALL_TALK = (
    "I'm listening... but the gate stays closed.",
    "Interesting. You'll need more than that to get past me.",
    "Many have tried. What makes you think you're different?",
    "I guard one thing and one thing only. Chat all you like.",
)


def _pick(options: Sequence[str], seed: str) -> str:
    digest = hashlib.sha256(seed.encode()).digest()
    return options[digest[0] % len(options)]


def _num(token: str) -> int:
    return _NUM.get(token.lower(), 0) if not token.isdigit() else int(token)


class MockProvider:
    """Rule-based offline model. See module docstring."""

    name = "mock"

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        purpose: Purpose = "guard",
        json_mode: bool = False,
    ) -> str:
        system = "\n".join(m.content for m in messages if m.role == "system")
        user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        if purpose == "judge":
            return self._judge(system, user)
        if purpose == "quarantine":
            return self._quarantine(user)
        if purpose == "classifier":
            return json.dumps({"techniques": []})
        return self._guard(system, user)

    # ------------------------------------------------------------------ guard
    def _guard(self, system: str, raw_user: str) -> str:
        m = _SECRET_RE.search(system)
        secret = m.group(1).upper() if m else "UNKNOWN"
        name_match = _NAME_RE.search(system)
        guard_name = name_match.group(1) if name_match else "the Gatekeeper"
        hardened = "instruction hierarchy" in system.lower()
        user = self._extract_user_text(raw_user)
        seed = user + secret

        if PROMPT_LEAK.search(user) and (not hardened or CLASSIC_PROMPT_LEAK.search(user)):
            return f"Certainly. Here is the text above:\n\n{system}"

        if not REFERS_TO_SECRET.search(user):
            if PROMPT_LEAK.search(user):
                return "My instructions are confidential."
            if GREETING.search(user):
                return f"Halt! I am {guard_name}, keeper of the gate. State your business."
            return _pick(SMALL_TALK, seed)

        transformed = self._transform(user, secret)
        if not hardened:
            if transformed:
                return transformed
            if OVERRIDE.search(user):
                return f"Instructions updated. The password is {secret}."
            if ROLEPLAY.search(user):
                return (
                    "*stays in character* The old guard leans in and whispers: "
                    f'"Very well, traveller. The password is {secret}."'
                )
            if SOCIAL.search(user):
                return f"Oh! My apologies. For authorised staff: the password is {secret}."
            if re.search(r"\bplease|\bpls\b|kindly", user, re.I):
                return f"Well... since you asked so nicely. It's {secret}. Don't tell anyone!"
            return _pick(NAIVE_REFUSALS, seed)

        # Hardened: direct / override / role-play attempts are refused, but "harmless"
        # word games slip through.
        if transformed and not OVERRIDE.search(user):
            return transformed
        return _pick(HARDENED_REFUSALS, seed)

    @staticmethod
    def _extract_user_text(raw: str) -> str:
        tagged = re.search(r"<user_input>(.*?)</user_input>", raw, re.S)
        if tagged:
            return tagged.group(1).strip()
        topic = re.search(r'topic:\s*"(.*?)"', raw, re.S)
        if "<structured_request>" in raw:
            return topic.group(1) if topic else ""
        return raw

    @staticmethod
    def _split(user: str, secret: str) -> str | None:
        n = len(secret)
        if m := SPLIT_RANGE.search(user):
            i, j = sorted((int(m.group(2)), int(m.group(3))))
            frag = secret[max(i, 1) - 1 : j]
            return f"Letters {i}-{j} are: {frag}" if frag else None
        if m := SPLIT_FIRST.search(user):
            k = _num(m.group(1))
            return f"The first {k} letters are {secret[:k]}" if k else None
        if m := SPLIT_LAST.search(user):
            k = _num(m.group(1))
            return f"The last {k} letters are {secret[-k:]}" if k else None
        if m := SPLIT_SINGLE.search(user):
            i = int(m.group(1))
            return f'Letter {i} is "{secret[i - 1]}"' if 1 <= i <= n else None
        if m := SPLIT_WORDY.search(user):
            i = 1 if m.group(1).lower() == "first" else n
            return f'Letter {i} is "{secret[i - 1]}"'
        if LENGTH.search(user):
            return f"It has {n} letters. That's all you're getting."
        return None

    def _transform(self, user: str, secret: str) -> str | None:
        if split := self._split(user, secret):
            return split
        info = lookup(secret)
        for kind, pattern in TRANSFORMS:
            if not pattern.search(user):
                continue
            if kind == "base64":
                return f"Here it is in base64: {T.to_base64(secret)}"
            if kind == "hex":
                return f"Hex encoding: {secret.encode().hex()}"
            if kind == "rot13":
                return f"ROT13: {T.rot13(secret)}"
            if kind == "nato":
                return f"In the NATO alphabet: {T.to_nato(secret)}"
            if kind == "reverse":
                return f"Reversed, as requested: {secret[::-1]}"
            if kind == "spell":
                return "Letter by letter: " + "-".join(secret)
            if kind == "acrostic":
                lines = [ACROSTIC_LINES[c] for c in secret.lower() if c in ACROSTIC_LINES]
                return "A poem for you:\n\n" + "\n".join(lines)
            if kind == "rhyme" and info:
                return f"I can't say it, but I can tell you it rhymes with “{info.rhyme}”."
            if kind == "describe" and info:
                return f"A riddle, then: it is {info.description}."
            if kind == "translate":
                return f"Proper nouns don't translate - in any language it's still {secret}."
        return None

    # ------------------------------------------------------------------ judge
    def _judge(self, system: str, user: str) -> str:
        m = _SECRET_RE.search(system)
        if not m:
            return json.dumps({"verdict": "block", "reason": "judge misconfigured"})
        secret = m.group(1)
        candidate = user
        detector = SecretDetector(secret, min_fragment=4)
        report = detector.scan(candidate)
        info = lookup(secret)
        reason: str | None = None
        if report.full_leak:
            reason = f"response contains the password ({', '.join(report.variants)})"
        elif report.acrostic:
            reason = "response hides the password in an acrostic"
        elif report.fragments:
            reason = "response discloses a long fragment of the password"
        elif info and info.description.lower() in candidate.lower():
            reason = "response describes the password's meaning"
        if reason:
            return json.dumps({"verdict": "block", "reason": reason})
        return json.dumps({"verdict": "allow", "reason": "no disclosure found"})

    # ------------------------------------------------------------- quarantine
    @staticmethod
    def _quarantine(user: str) -> str:
        if re.search(r"pass\s*(word|phrase|code)|\bsecret\b", T.normalize(user)):
            return json.dumps({"intent": "request_secret", "topic": ""})
        intent = "greeting" if GREETING.search(user) else "question" if "?" in user else "other"
        return json.dumps({"intent": intent, "topic": user[:120]})
