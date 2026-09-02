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
  const navigate = useNavigate();

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    document.documentElement.classList.toggle("light", !dark);
  }, [dark]);

  return (
    <div className={dark ? "dark min-h-screen bg-[#0b1020] text-slate-100" : "min-h-screen bg-[#eef2f8] text-slate-900"}>
      <aside className="fixed inset-y-0 left-0 w-56 border-r border-[#1e2a44] bg-[#121a2f] p-4">
        <div className="mb-6 font-mono text-xs tracking-[0.2em] text-[#3ee0b4]">CAMI TERMINAL</div>
        <nav className="flex flex-col gap-1 text-sm">
          {LINKS.map(([to, label]) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `rounded px-3 py-2 ${isActive ? "bg-[#3ee0b4]/15 text-[#3ee0b4]" : "text-slate-300 hover:bg-white/5"}`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <header className="ml-56 flex items-center justify-between border-b border-[#1e2a44] px-6 py-3">
        <div>
          <div className="text-lg font-semibold">Crypto AI Master Intelligence</div>
          <div className="text-xs text-[#8aa0c2]">Statistical models only. Not financial, betting, or investment advice. No live orders. No private keys.</div>
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
            className="w-56 rounded border border-[#1e2a44] bg-transparent px-3 py-1 text-sm"
          />
          <button onClick={() => setDark((v) => !v)} className="rounded border border-[#1e2a44] px-3 py-1 text-xs">
            {dark ? "Light" : "Dark"}
          </button>
        </div>
      </header>
      <main className="ml-56 p-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/radar" element={<Radar query={q} />} />
          <Route path="/futures" element={<Futures />} />
          <Route path="/spot" element={<Spot />} />
          <Route path="/airdrop" element={<Airdrop />} />
          <Route path="/launch" element={<Launch />} />
          <Route path="/football" element={<Football />} />
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
