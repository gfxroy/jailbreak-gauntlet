import { lazy, Suspense } from "react";
import { BrowserRouter, HashRouter, Route, Routes } from "react-router-dom";
import { STATIC } from "./api/client";
import { Layout } from "./components/Layout";
import { SessionProvider } from "./hooks/session";
import { About } from "./pages/About";
import { Home } from "./pages/Home";
import { Leaderboard } from "./pages/Leaderboard";
import { LevelPage } from "./pages/LevelPage";

// Recharts is the heaviest dependency; only load it on the dashboard route.
const Router = STATIC ? HashRouter : BrowserRouter;

const Dashboard = lazy(() => import("./pages/Dashboard").then((m) => ({ default: m.Dashboard })));

export default function App() {
  return (
    <SessionProvider>
      <Router>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Home />} />
            <Route path="level/:id" element={<LevelPage />} />
            <Route
              path="dashboard"
              element={
                <Suspense fallback={<p className="font-mono text-ink-400 cursor-blink">loading</p>}>
                  <Dashboard />
                </Suspense>
              }
            />
            <Route path="leaderboard" element={<Leaderboard />} />
            <Route path="about" element={<About />} />
          </Route>
        </Routes>
      </Router>
    </SessionProvider>
  );
}
