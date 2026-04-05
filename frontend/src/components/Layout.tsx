import { NavLink, Outlet, useNavigate } from "react-router-dom"
import { useAuth } from "../hooks/useAuth"
import {
  LayoutDashboard, FileText, TrendingUp, FileInput,
  Settings, LogOut, ChevronRight, BarChart2, TableProperties,
  Info, MessageCircle,
} from "lucide-react"
import { cn } from "../lib/utils"

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const myRest = user?.role === "store" ? user?.restaurants?.[0] : null
  const canInvoices  = user?.role !== "store" || (myRest?.feat_invoices  !== false)
  const canAnalytics = user?.role !== "store" || (myRest?.feat_analytics !== false)

  const nav = [
    { to: "/dashboard", icon: LayoutDashboard, label: "Дашборд",      show: true },
    { to: "/reports",   icon: FileText,         label: "Отчёты",       show: true },
    { to: "/invoices",  icon: FileInput,         label: "Накладные",    show: canInvoices },
    { to: "/analytics", icon: TrendingUp,        label: "Аналитика",    show: canAnalytics },
    { to: "/planning",  icon: BarChart2,          label: "Планирование", show: true },
    { to: "/checklist", icon: TableProperties,    label: "Чек-лист",     show: true },
    { to: "/about",     icon: Info,               label: "О системе",    show: true },
  ].filter(item => item.show)

  const handleLogout = () => {
    logout()
    navigate("/login")
  }

  return (
    <div className="flex h-screen overflow-hidden bg-brand-bg">
      {/* ── Sidebar ── */}
      <aside className="w-60 flex-shrink-0 bg-sidebar flex flex-col">
        {/* Logo */}
        <div className="flex items-center gap-3 px-5 py-5 border-b border-white/10">
          <img src="/forblack.png" alt="Reston Analytics" className="h-9 w-auto" />
          <div>
            <p className="text-white font-bold text-sm leading-tight">Reston Analytics</p>
            <p className="text-white/40 text-xs">Аналитика и контроль ресторанов</p>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {nav.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 group",
                  isActive
                    ? "bg-brand-yellow text-brand-dark"
                    : "text-white/60 hover:text-white hover:bg-white/10"
                )
              }
            >
              {({ isActive }) => (
                <>
                  <Icon size={17} className={isActive ? "text-brand-dark" : "text-white/50 group-hover:text-white"} />
                  <span className="flex-1">{label}</span>
                  {isActive && <ChevronRight size={14} className="text-brand-dark/50" />}
                </>
              )}
            </NavLink>
          ))}

          {user?.role === "co" && (
            <>
              <div className="pt-4 pb-1 px-3">
                <p className="text-white/25 text-xs uppercase tracking-widest font-semibold">Управление</p>
              </div>
              {[{ to: "/admin", icon: Settings, label: "Администрирование" }].map(({ to, icon: Icon, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 group",
                      isActive
                        ? "bg-brand-yellow text-brand-dark"
                        : "text-white/60 hover:text-white hover:bg-white/10"
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      <Icon size={17} className={isActive ? "text-brand-dark" : "text-white/50 group-hover:text-white"} />
                      <span className="flex-1">{label}</span>
                      {isActive && <ChevronRight size={14} className="text-brand-dark/50" />}
                    </>
                  )}
                </NavLink>
              ))}
            </>
          )}
        </nav>

        {/* Support block */}
        <div className="px-3 pb-2">
          <a
            href="https://wa.me/77086041772"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors group"
          >
            <MessageCircle size={15} className="text-green-400 flex-shrink-0" />
            <span className="text-white/60 group-hover:text-white text-xs transition-colors font-medium">
              Написать поддержке
            </span>
          </a>
        </div>

        {/* User */}
        <div className="px-3 py-3 border-t border-white/10">
          <div className="flex items-center gap-3 px-3 py-2 rounded-lg">
            <div className="w-8 h-8 rounded-full bg-brand-yellow flex items-center justify-center flex-shrink-0">
              <span className="text-brand-dark font-bold text-sm uppercase">
                {user?.username?.[0] ?? "?"}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-white text-sm font-medium truncate">{user?.username}</p>
              <p className="text-white/40 text-xs capitalize">{user?.role}</p>
            </div>
            <button
              onClick={handleLogout}
              className="text-white/40 hover:text-red-400 transition-colors"
              title="Выйти"
            >
              <LogOut size={16} />
            </button>
          </div>
          <p className="text-white/20 text-[10px] text-center mt-2">
            © 2026 Reston Analytics
          </p>
        </div>
      </aside>

      {/* ── Main content ── */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
