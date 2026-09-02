import { NavLink, Route, Routes, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import Dashboard from "./pages/Dashboard";
import Radar from "./pages/Radar";
import Futures from "./pages/Futures";
import Spot from "./pages/Spot";
import Airdrop from "./pages/Airdrop";
import Launch from "./pages/Launch";
import Football from "./pages/Football";
import Lottery from "./pages/Lottery";
import Portfolio from "./pages/Portfolio";
import Models from "./pages/Models";
import Simulations from "./pages/Simulations";
import ProjectDetail from "./pages/ProjectDetail";
import AssetDetail from "./pages/AssetDetail";
import SettingsPage from "./pages/Settings";
import NotificationsPage from "./pages/Notifications";
import { api } from "./api";
import { Status } from "./components/ui";

const LINKS = [
  ["/", "Dashboard"],
  ["/radar", "50X Radar"],
  ["/futures", "Futures"],
  ["/spot", "Spot"],
  ["/airdrop", "Airdrop"],
  ["/launch", "Launch"],
  ["/football", "Football"],
  ["/lottery", "Lottery"],
  ["/portfolio", "Portfolio"],
  ["/models", "Models"],
  ["/simulations", "Simulations"],
  ["/notifications", "Alerts"],
  ["/settings", "Settings"],
];

export default function App() {
  const [dark, setDark] = useState(true);
  const [q, setQ] = useState("");
  const [health, setHealth] = useState<any>(null);
  const navigate = useNavigate();

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    document.documentElement.classList.toggle("light", !dark);
  }, [dark]);

  useEffect(() => {
    api("/api/health").then(setHealth).catch(() => setHealth(null));
  }, []);

  const providers = health?.providers || {};

  return (
    <div className="min-h-screen" style={{ background: "var(--bg)", color: "var(--text)" }}>
      <aside className="fixed inset-y-0 left-0 w-56 border-r p-4" style={{ borderColor: "var(--border)", background: "var(--panel)" }}>
        <div className="mb-6 font-mono text-xs tracking-[0.2em]" style={{ color: "var(--accent)" }}>CAMI TERMINAL</div>
        <nav className="flex flex-col gap-1 text-sm">
          {LINKS.map(([to, label]) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) => `rounded px-3 py-2 ${isActive ? "" : "opacity-80 hover:opacity-100"}`}
              style={({ isActive }) => (isActive ? { background: "color-mix(in srgb, var(--accent) 18%, transparent)", color: "var(--accent)" } : undefined)}
            >
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <header className="ml-56 flex items-center justify-between border-b px-6 py-3" style={{ borderColor: "var(--border)" }}>
        <div>
          <div className="text-lg font-semibold">Crypto AI Master Intelligence</div>
          <div className="text-xs" style={{ color: "var(--muted)" }}>Statistical models only. Not financial, betting, or investment advice. No live orders. No private keys.</div>
          <div className="mt-1 flex flex-wrap gap-3 text-[11px]">
            {["binance", "coingecko", "lottery", "mempool"].map((name) => (
              <span key={name} className="font-mono">
                {name} <Status value={providers[name]?.status} />
              </span>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && q.trim()) {
                const token = q.trim().toUpperCase();
                if (/^[A-Z0-9]{2,20}(USDT)?$/.test(token)) {
                  navigate(`/assets/${token.endsWith("USDT") ? token : `${token}USDT`}`);
                }
              }
            }}
            placeholder="Search / Enter BTCUSDT"
            className="w-56 rounded border bg-transparent px-3 py-1 text-sm"
            style={{ borderColor: "var(--border)" }}
          />
          <button onClick={() => setDark((v) => !v)} className="rounded border px-3 py-1 text-xs" style={{ borderColor: "var(--border)" }}>
            {dark ? "Light" : "Dark"}
          </button>
        </div>
      </header>
      <main className="ml-56 p-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/radar" element={<Radar query={q} />} />
          <Route path="/futures" element={<Futures query={q} />} />
          <Route path="/spot" element={<Spot query={q} />} />
          <Route path="/airdrop" element={<Airdrop query={q} />} />
          <Route path="/launch" element={<Launch query={q} />} />
          <Route path="/football" element={<Football query={q} />} />
          <Route path="/lottery" element={<Lottery />} />
          <Route path="/portfolio" element={<Portfolio />} />
          <Route path="/models" element={<Models />} />
          <Route path="/simulations" element={<Simulations />} />
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/projects/:id" element={<ProjectDetail />} />
          <Route path="/assets/:symbol" element={<AssetDetail />} />
        </Routes>
      </main>
    </div>
  );
}
