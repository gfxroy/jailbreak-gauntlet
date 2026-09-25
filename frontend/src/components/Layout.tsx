import { NavLink, Outlet } from "react-router-dom";
import clsx from "clsx";
import { useSession } from "../hooks/session";
import { useAsync } from "../hooks/useAsync";
import { api, STATIC } from "../api/client";
import { ModelMenu } from "./ModelMenu";
import { ChartIcon, InfoIcon, ShieldIcon, TerminalIcon, TrophyIcon } from "./Icons";

const links = [
  { to: "/", label: "Gauntlet", icon: TerminalIcon, end: true },
  { to: "/dashboard", label: "Research", icon: ChartIcon },
  { to: "/leaderboard", label: "Leaderboard", icon: TrophyIcon },
  { to: "/about", label: "About", icon: InfoIcon },
];

export function Layout() {
  const { session, reset } = useSession();
  const { data: health } = useAsync(() => api.health(), []);
  const demo = health?.provider === "mock";

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-ink-700/70 bg-ink-950/80 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-5">
          <NavLink to="/" className="flex items-center gap-2.5">
            <span className="grid h-8 w-8 place-items-center rounded-lg border border-neon-400/40 bg-neon-400/10 text-neon-400">
              <ShieldIcon width={16} height={16} />
            </span>
            <span className="font-mono text-sm font-semibold tracking-tight">
              jailbreak<span className="text-neon-400">_</span>gauntlet
            </span>
          </NavLink>
          <nav className="flex items-center gap-1">
            {links.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  clsx(
                    "flex items-center gap-2 rounded-md px-3 py-1.5 font-mono text-xs transition",
                    isActive
                      ? "bg-ink-800 text-neon-400"
                      : "text-ink-300 hover:bg-ink-850 hover:text-ink-100",
                  )
                }
              >
                <Icon width={15} height={15} />
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3 font-mono text-xs">
            {health && (
              <span
                className={clsx(
                  "flex items-center gap-1.5 rounded-full border px-2.5 py-1",
                  demo
                    ? "border-amber-glow/40 text-amber-glow"
                    : "border-neon-400/40 text-neon-400",
                )}
                title={demo ? "Offline mock guard" : health.model ?? ""}
              >
                <span
                  className={clsx(
                    "h-1.5 w-1.5 rounded-full",
                    demo ? "bg-amber-glow" : "bg-neon-400",
                  )}
                />
                {demo ? "DEMO MODE · mock guard" : `LIVE · ${health.model}`}
              </span>
            )}
            {STATIC && <ModelMenu />}
            {session && (
              <button onClick={reset} className="text-ink-400 hover:text-alert-400" title="Start over">
                {session.nickname} · reset
              </button>
            )}
          </div>
        </div>
      </header>
      {STATIC && (
        <div className="border-b border-amber-glow/20 bg-amber-glow/5 px-5 py-2 text-center font-mono text-[11px] text-amber-glow">
          Static edition: everything runs in your browser, so the passwords are visible in devtools
          and stats are stored only in this browser. It's for play and learning. The{" "}
          <a className="underline" href="https://github.com/gfxroy/jailbreak-gauntlet#quickstart">server version</a> keeps secrets server-side.
        </div>
      )}
      <main className="mx-auto max-w-7xl px-5 py-8">
        <Outlet />
      </main>
      <footer className="mx-auto max-w-7xl px-5 pb-10 pt-4 font-mono text-[11px] text-ink-400">
        Educational use only. Test prompt-injection techniques only against systems you own or
        are authorised to assess.
      </footer>
    </div>
  );
}
