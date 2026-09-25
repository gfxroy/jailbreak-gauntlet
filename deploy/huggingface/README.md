---
title: Jailbreak Gauntlet
emoji: 🛡️
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Prompt-injection CTF with 8 layered LLM defenses
---

# Jailbreak Gauntlet (live demo)

Eight AI guards each protect a password behind progressively stronger prompt-injection
defenses. Talk them into leaking it, then learn why each defense failed.

- Source, docs and local setup: https://github.com/gfxroy/jailbreak-gauntlet
- This demo is rate-limited per visitor and has a daily budget. If you hit a limit, run it
  locally (it also works offline, with no API key).
- The research dashboard includes a clearly labelled **synthetic** sample dataset.
- Please don't type personal information: prompts are stored (anonymously) for the
  dashboard, and the public export redacts secrets and common PII on a best-effort basis.

Educational use only. Test prompt-injection techniques only on systems you own or are
authorised to assess.
