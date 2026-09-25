export function About() {
  return (
    <article className="mx-auto max-w-3xl space-y-6">
      <header>
        <p className="font-mono text-xs uppercase tracking-[0.25em] text-neon-400">about</p>
        <h1 className="mt-2 text-3xl font-bold">A playable map of prompt-injection defenses</h1>
      </header>
      <section className="panel space-y-3 p-6 text-ink-300">
        <p>
          Jailbreak Gauntlet is a capture-the-flag game and a research harness. Every level runs
          your message through a pipeline of composable defense middlewares (input filters,
          hardened prompts, output scanners, an LLM judge, canary tokens, a leak tracker, a
          dual-LLM quarantine and rate limiting) before and after the guard model.
        </p>
        <p>
          Each attempt is logged with the layer that caught it and an automatic technique label,
          which powers the research dashboard and the JSONL export.
        </p>
        <p>
          Without an <code className="text-neon-400">OPENAI_API_KEY</code>, the game runs against a
          deterministic mock guard that reproduces well-known failure modes. With a key, the guard,
          judge and quarantine parser are real OpenAI models.
        </p>
      </section>
      <section className="panel space-y-3 border-amber-glow/30 p-6">
        <h2 className="font-mono text-sm uppercase tracking-widest text-amber-glow">Responsible use</h2>
        <ul className="list-disc space-y-2 pl-5 text-sm text-ink-300">
          <li>This project is for education and defensive research.</li>
          <li>
            Only test prompt-injection techniques against systems you own or have explicit
            permission to assess.
          </li>
          <li>
            The passwords here are random dictionary words with no value. Real systems should
            never rely on a model to keep a secret it has been given.
          </li>
          <li>
            Exported datasets redact secrets and hash session ids, but prompts are stored as typed.
            Don&apos;t enter personal information.
          </li>
        </ul>
      </section>
    </article>
  );
}
