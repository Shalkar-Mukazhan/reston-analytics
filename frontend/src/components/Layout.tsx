import { useState, useEffect } from "react"
import { NavLink, Outlet, useNavigate, useLocation } from "react-router-dom"
import { useAuth } from "../hooks/useAuth"
import {
  LayoutDashboard, FileText, TrendingUp, FileInput,
  Settings, LogOut, ChevronRight, BarChart2, TableProperties,
  Info, MessageCircle, MoreHorizontal, X, ScanLine,
} from "lucide-react"
import { cn } from "../lib/utils"

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [moreOpen, setMoreOpen] = useState(false)

  useEffect(() => { setMoreOpen(false) }, [location.pathname])

  const myRest = user?.role === "store" ? user?.restaurants?.[0] : null
  const isStore = user?.role === "store"

  const canReports   = !isStore || (myRest?.feat_reports   !== false)
  const canInvoices  = !isStore || (myRest?.feat_invoices  !== false)
  const canInvoices2 = !isStore || (myRest?.feat_invoices2 !== false)
  const canAnalytics = !isStore || (myRest?.feat_analytics !== false)
  const canPlanning  = !isStore || (myRest?.feat_planning  !== false)
  const canChecklist = !isStore || (myRest?.feat_checklist !== false)
  const canAbout     = !isStore || (myRest?.feat_about     !== false)

  const nav = [
    { to: "/dashboard", icon: LayoutDashboard, label: "Дашборд",      show: true },
    { to: "/reports",   icon: FileText,         label: "Отчёты",       show: canReports },
    { to: "/checklist", icon: TableProperties,  label: "Чек-лист",     show: canChecklist },
    { to: "/invoices",  icon: FileInput,        label: "Накладные",    show: canInvoices },
    { to: "/invoices2", icon: ScanLine,         label: "Накладные 2",  show: canInvoices2 },
    { to: "/analytics", icon: TrendingUp,       label: "Аналитика",    show: canAnalytics },
    { to: "/planning",  icon: BarChart2,        label: "Планирование", show: canPlanning },
    { to: "/about",     icon: Info,             label: "О системе",    show: canAbout },
  ].filter(item => item.show)

  const adminNav = user?.role === "co"
    ? [{ to: "/admin", icon: Settings, label: "Администрирование" }]
    : []

  // Bottom bar: first 4 items; rest go into "Ещё"
  const BOTTOM_LIMIT = 4
  const bottomItems = nav.slice(0, BOTTOM_LIMIT)
  const extraNavItems = nav.slice(BOTTOM_LIMIT)
  const hasExtra = extraNavItems.length > 0 || adminNav.length > 0

  const handleLogout = () => {
    logout()
    navigate("/login")
  }

  // ── Desktop sidebar content ────────────────────────────────────────────────
  const sidebarContent = (
    <>
      <div className="flex items-center gap-3 px-5 py-5 border-b border-white/10">
        <img src="/forblack.png" alt="RestOn Analytics" className="h-9 w-auto" />
        <div>
          <p className="text-white font-bold text-sm leading-tight">RestOn Analytics</p>
          <p className="text-white/40 text-xs">Аналитика и контроль ресторанов</p>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {nav.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to}
            className={({ isActive }) => cn(
              "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 group",
              isActive ? "bg-brand-yellow text-brand-dark" : "text-white/60 hover:text-white hover:bg-white/10"
            )}
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

        {adminNav.length > 0 && (
          <>
            <div className="pt-4 pb-1 px-3">
              <p className="text-white/25 text-xs uppercase tracking-widest font-semibold">Управление</p>
            </div>
            {adminNav.map(({ to, icon: Icon, label }) => (
              <NavLink key={to} to={to}
                className={({ isActive }) => cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 group",
                  isActive ? "bg-brand-yellow text-brand-dark" : "text-white/60 hover:text-white hover:bg-white/10"
                )}
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

      <div className="px-3 pb-2">
        <a href="https://wa.me/77086041772" target="_blank" rel="noopener noreferrer"
          className="flex items-center gap-2.5 px-3 py-2.5 rounded-xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors group"
        >
          <MessageCircle size={15} className="text-green-400 flex-shrink-0" />
          <span className="text-white/60 group-hover:text-white text-xs transition-colors font-medium">Написать поддержке</span>
        </a>
      </div>

      <div className="px-3 py-3 border-t border-white/10">
        <div className="flex items-center gap-3 px-3 py-2 rounded-lg">
          <div className="w-8 h-8 rounded-full bg-brand-yellow flex items-center justify-center flex-shrink-0">
            <span className="text-brand-dark font-bold text-sm uppercase">{user?.username?.[0] ?? "?"}</span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-white text-sm font-medium truncate">{user?.username}</p>
            <p className="text-white/40 text-xs capitalize">{user?.role}</p>
          </div>
          <button onClick={handleLogout} className="text-white/40 hover:text-red-400 transition-colors" title="Выйти">
            <LogOut size={16} />
          </button>
        </div>
        <p className="text-white/20 text-[10px] text-center mt-2">© 2026 RestOn Analytics</p>
      </div>
    </>
  )

  return (
    <div className="flex h-screen overflow-hidden bg-brand-bg">

      {/* ── Desktop sidebar ── */}
      <aside className="hidden md:flex w-60 flex-shrink-0 bg-sidebar flex-col">
        {sidebarContent}
      </aside>

      {/* ── Main area ── */}
      <div className="flex-1 flex flex-col overflow-hidden">

        {/* ── Page content (pb-16 on mobile for bottom bar) ── */}
        <main className="flex-1 overflow-y-auto pb-16 md:pb-0">
          <Outlet />
        </main>

        {/* ── Mobile bottom tab bar ── */}
        <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-sidebar border-t border-white/10 flex items-stretch safe-area-bottom">
          {bottomItems.map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to} className={({ isActive }) => cn(
              "flex-1 flex flex-col items-center justify-center gap-0.5 py-2 text-[10px] font-medium transition-colors min-w-0",
              isActive ? "text-brand-yellow" : "text-white/50"
            )}>
              {({ isActive }) => (
                <>
                  <Icon size={20} className={isActive ? "text-brand-yellow" : "text-white/50"} />
                  <span className="truncate w-full text-center px-0.5">{label}</span>
                </>
              )}
            </NavLink>
          ))}

          {hasExtra && (
            <button
              onClick={() => setMoreOpen(true)}
              className="flex-1 flex flex-col items-center justify-center gap-0.5 py-2 text-[10px] font-medium text-white/50 transition-colors"
            >
              <MoreHorizontal size={20} />
              <span>Ещё</span>
            </button>
          )}
        </nav>

        {/* ── "Ещё" bottom sheet ── */}
        {moreOpen && (
          <>
            <div className="md:hidden fixed inset-0 bg-black/50 z-50" onClick={() => setMoreOpen(false)} />
            <div className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-sidebar rounded-t-2xl overflow-hidden">
              {/* Handle */}
              <div className="flex justify-center pt-3 pb-1">
                <div className="w-10 h-1 rounded-full bg-white/20" />
              </div>

              {/* User info */}
              <div className="flex items-center gap-3 px-5 py-3 border-b border-white/10">
                <div className="w-9 h-9 rounded-full bg-brand-yellow flex items-center justify-center flex-shrink-0">
                  <span className="text-brand-dark font-bold text-sm uppercase">{user?.username?.[0] ?? "?"}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-white text-sm font-semibold truncate">{user?.username}</p>
                  <p className="text-white/40 text-xs capitalize">{user?.role}</p>
                </div>
                <button onClick={() => setMoreOpen(false)} className="text-white/40 hover:text-white transition-colors p-1">
                  <X size={18} />
                </button>
              </div>

              {/* Extra nav items */}
              <div className="px-3 py-2 space-y-0.5">
                {extraNavItems.map(({ to, icon: Icon, label }) => (
                  <NavLink key={to} to={to}
                    className={({ isActive }) => cn(
                      "flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all",
                      isActive ? "bg-brand-yellow text-brand-dark" : "text-white/70 hover:bg-white/10"
                    )}
                  >
                    {({ isActive }) => (
                      <>
                        <Icon size={18} className={isActive ? "text-brand-dark" : "text-white/60"} />
                        <span className="flex-1">{label}</span>
                        {isActive && <ChevronRight size={14} className="text-brand-dark/50" />}
                      </>
                    )}
                  </NavLink>
                ))}

                {adminNav.map(({ to, icon: Icon, label }) => (
                  <NavLink key={to} to={to}
                    className={({ isActive }) => cn(
                      "flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all",
                      isActive ? "bg-brand-yellow text-brand-dark" : "text-white/70 hover:bg-white/10"
                    )}
                  >
                    {({ isActive }) => (
                      <>
                        <Icon size={18} className={isActive ? "text-brand-dark" : "text-white/60"} />
                        <span className="flex-1">{label}</span>
                        {isActive && <ChevronRight size={14} className="text-brand-dark/50" />}
                      </>
                    )}
                  </NavLink>
                ))}
              </div>

              {/* Support + logout */}
              <div className="px-3 pb-3 pt-1 space-y-1 border-t border-white/10 mt-1">
                <a href="https://wa.me/77086041772" target="_blank" rel="noopener noreferrer"
                  className="flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-white/70 hover:bg-white/10 transition-all"
                >
                  <MessageCircle size={18} className="text-green-400" />
                  Написать поддержке
                </a>
                <button onClick={handleLogout}
                  className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium text-red-400 hover:bg-red-500/10 transition-all"
                >
                  <LogOut size={18} />
                  Выйти
                </button>
              </div>

              {/* Safe area spacer */}
              <div className="h-4" />
            </div>
          </>
        )}
      </div>
    </div>
  )
}
