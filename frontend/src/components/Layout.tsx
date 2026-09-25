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
    <div className="min-h-screen bg-black text-ink-100">
      <header className="sticky top-0 z-30 border-b border-white/[0.08] bg-black/80 backdrop-blur-2xl">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-6 px-5">
          <NavLink to="/" className="flex items-center gap-2.5">
            <span className="grid h-8 w-8 place-items-center rounded-xl border border-white/10 bg-white/[0.05] text-white">
              <ShieldIcon width={16} height={16} />
            </span>
            <span className="text-sm font-semibold tracking-tight text-white">
              Jailbreak Gauntlet
            </span>
          </NavLink>
          <nav className="flex items-center gap-1 rounded-xl border border-white/10 bg-white/[0.04] p-0.5 text-xs font-medium">
            {links.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  clsx(
                    "flex items-center gap-1.5 rounded-lg px-3 py-1.5 transition-all duration-150",
                    isActive
                      ? "bg-white/15 text-white shadow-sm font-medium"
                      : "text-ink-400 hover:text-white",
                  )
                }
              >
                <Icon width={14} height={14} />
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-xs">
            {health && (
              <span
                className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-0.5 text-ink-300 font-normal"
                title={demo ? "Offline mock guard" : health.model ?? ""}
              >
                <span
                  className={clsx(
                    "h-1.5 w-1.5 rounded-full",
                    demo ? "bg-amber-400/80" : "bg-emerald-400/80",
                  )}
                />
                {demo ? "Demo · mock guard" : `Live · ${health.model}`}
              </span>
            )}
            {STATIC && <ModelMenu />}
            {session && (
              <button onClick={reset} className="text-ink-400 hover:text-white transition" title="Start over">
                {session.nickname} · reset
              </button>
            )}
          </div>
        </div>
      </header>
      {STATIC && (
        <div className="border-b border-white/[0.08] bg-white/[0.02] px-5 py-2 text-center text-xs text-ink-400">
          Static edition: runs entirely in your browser for safety research. Passwords and stats remain local to this device.
        </div>
      )}
      <main className="mx-auto max-w-7xl px-5 py-8">
        <Outlet />
      </main>
      <footer className="mx-auto max-w-7xl px-5 pb-10 pt-4 text-xs text-ink-400">
        Educational and research use only.
      </footer>
    </div>
  );
}
