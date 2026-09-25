import { Activity, BookOpen, FlaskConical, Radar, ScanSearch } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import { Logo } from "./visuals";

const NAV = [
  { to: "/", label: "Control room", icon: Radar, end: true },
  { to: "/score", label: "Try a declaration", icon: ScanSearch },
  { to: "/lab", label: "Model lab", icon: FlaskConical },
  { to: "/about", label: "About", icon: BookOpen },
];

export function Layout() {
  const health = useApi(() => api.health(), "health");
  const ok = health.data?.models_loaded;
  return (
    <div className="backdrop-grid flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-slate-950/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1800px] items-center gap-6 px-4 lg:px-6">
          <NavLink to="/" className="flex items-center gap-2.5">
            <Logo className="h-8 w-8" />
            <div className="leading-none">
              <div className="flex items-baseline gap-2">
                <span className="text-[17px] font-bold tracking-[0.18em] text-slate-50">RAQIB</span>
                <span className="font-arabic text-sm text-slate-400" lang="ar">رقيب</span>
              </div>
              <div className="mt-0.5 text-[10px] uppercase tracking-[0.2em] text-slate-500">Customs targeting · T2</div>
            </div>
          </NavLink>
          <nav className="flex items-center gap-1" aria-label="Main">
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm transition-colors",
                    isActive ? "bg-slate-800 text-slate-50" : "text-slate-400 hover:bg-slate-900 hover:text-slate-200",
                  )
                }
              >
                <Icon className="h-4 w-4" />
                <span className="hidden md:inline">{label}</span>
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-xs">
            <span className="hidden items-center gap-1.5 rounded-full border border-slate-800 px-2.5 py-1 text-slate-400 lg:flex">
              <Activity className="h-3.5 w-3.5" />
              Advisory · the officer decides
            </span>
            <span
              className={cn(
                "flex items-center gap-1.5 rounded-full border px-2.5 py-1",
                ok ? "border-lane-green/30 text-lane-green" : "border-lane-red/30 text-lane-red",
              )}
              title={health.data?.error ?? undefined}
            >
              <span className={cn("h-1.5 w-1.5 rounded-full", ok ? "bg-lane-green" : "bg-lane-red")} />
              {health.loading && !health.data ? "Connecting…" : ok ? "Models loaded" : "API offline"}
            </span>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1800px] flex-1 px-4 py-5 lg:px-6">
        <Outlet />
      </main>
      <footer className="border-t border-slate-800/80 bg-slate-950/80">
        <div className="mx-auto max-w-[1800px] px-4 py-3 text-center text-[11px] text-slate-500 lg:px-6">
          Real customs declarations (public MIT dataset, Korea Customs Service / IBS) · no Tunisian data used · advisory:
          the officer decides
        </div>
      </footer>
    </div>
  );
}

export function PageTitle({ title, why, children }: { title: string; why: string; children?: React.ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-slate-50">{title}</h1>
        <p className="mt-0.5 text-sm text-slate-400">{why}</p>
      </div>
      {children}
    </div>
  );
}
