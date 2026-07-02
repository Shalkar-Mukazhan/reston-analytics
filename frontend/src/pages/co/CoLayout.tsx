import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, FileText, FileX2, ArrowLeftRight, Warehouse,
  Store, Truck, RefreshCw, Users, LogOut, Menu, X,
  AlertCircle, History, Plug, Building2, ClipboardList,
  ChevronDown, Wifi,
} from 'lucide-react'

interface NavItem {
  label: string
  icon: any
  href: string
  adminOnly: boolean
  isActive: (pathname: string, search: string) => boolean
}
interface NavGroup {
  label: string
  items: NavItem[]
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: 'DASHBOARD',
    items: [
      {
        label: 'Обзор',
        icon: LayoutDashboard,
        href: '/dashboard',
        adminOnly: false,
        isActive: (p) => p === '/dashboard',
      },
    ],
  },
  {
    label: 'ДОКУМЕНТЫ',
    items: [
      {
        label: 'Накладные',
        icon: FileText,
        href: '/invoices',
        adminOnly: false,
        isActive: (p) => p === '/invoices',
      },
      {
        label: 'Акты списания',
        icon: FileX2,
        href: '/writeoffs',
        adminOnly: false,
        isActive: (p) => p === '/writeoffs',
      },
      {
        label: 'Инвентаризация',
        icon: ClipboardList,
        href: '/admin?tab=inventory',
        adminOnly: false,
        isActive: (p, s) => p === '/admin' && s.includes('tab=inventory'),
      },
    ],
  },
  {
    label: 'СПРАВОЧНИКИ',
    items: [
      {
        label: 'Маппинг',
        icon: ArrowLeftRight,
        href: '/admin?tab=mapping',
        adminOnly: false,
        isActive: (p, s) => p === '/admin' && s.includes('tab=mapping'),
      },
      {
        label: 'Склады',
        icon: Warehouse,
        href: '/admin?tab=warehouses',
        adminOnly: false,
        isActive: (p, s) => p === '/admin' && s.includes('tab=warehouses'),
      },
      {
        label: 'Рестораны',
        icon: Store,
        href: '/admin?tab=restaurants',
        adminOnly: false,
        isActive: (p, s) => p === '/admin' && s.includes('tab=restaurants'),
      },
      {
        label: 'Поставщики',
        icon: Truck,
        href: '/admin?tab=suppliers',
        adminOnly: false,
        isActive: (p, s) => p === '/admin' && s.includes('tab=suppliers'),
      },
    ],
  },
  {
    label: 'КОНТРОЛЬ',
    items: [
      {
        label: 'Ошибки распознавания',
        icon: AlertCircle,
        href: '/admin?tab=errors',
        adminOnly: true,
        isActive: (p, s) => p === '/admin' && s.includes('tab=errors'),
      },
      {
        label: 'История загрузок',
        icon: History,
        href: '/admin?tab=history',
        adminOnly: true,
        isActive: (p, s) => p === '/admin' && s.includes('tab=history'),
      },
      {
        label: 'iiko Sync',
        icon: RefreshCw,
        href: '/admin?tab=sync',
        adminOnly: true,
        isActive: (p, s) => p === '/admin' && s.includes('tab=sync'),
      },
    ],
  },
  {
    label: 'НАСТРОЙКИ',
    items: [
      {
        label: 'Интеграции',
        icon: Plug,
        href: '/admin?tab=integrations',
        adminOnly: true,
        isActive: (p, s) => p === '/admin' && s.includes('tab=integrations'),
      },
      {
        label: 'Пользователи',
        icon: Users,
        href: '/admin?tab=users',
        adminOnly: true,
        isActive: (p, s) => p === '/admin' && s.includes('tab=users'),
      },
      {
        label: 'Клиенты',
        icon: Building2,
        href: '/admin?tab=clients',
        adminOnly: true,
        isActive: (p, s) => p === '/admin' && s.includes('tab=clients'),
      },
    ],
  },
]

function getPageTitle(pathname: string, search: string): string {
  const map: Record<string, string> = {
    '/dashboard': 'Обзор',
    '/invoices': 'Накладные',
    '/writeoffs': 'Акты списания',
  }
  if (map[pathname]) return map[pathname]
  if (pathname === '/admin') {
    const tab = new URLSearchParams(search).get('tab') ?? ''
    const tabLabels: Record<string, string> = {
      mapping: 'Маппинг', warehouses: 'Склады', restaurants: 'Рестораны',
      suppliers: 'Поставщики', products: 'Товары', users: 'Пользователи',
      containers: 'Кейсовки', sync: 'iiko Sync', errors: 'Ошибки распознавания',
      history: 'История загрузок', integrations: 'Интеграции', clients: 'Клиенты',
    }
    return tabLabels[tab] ?? 'Управление'
  }
  return 'RestOn'
}

export default function CoLayout({
  children,
  me,
  onLogout,
}: {
  children: React.ReactNode
  me: { name: string; role: string; tenant_name?: string; iiko_connected?: boolean } | null
  onLogout: () => void
}) {
  const navigate = useNavigate()
  const { pathname, search } = useLocation()
  const isAdmin = me?.role === 'admin'
  const [mobileOpen, setMobileOpen] = useState(false)

  const handleNav = (href: string) => {
    navigate(href)
    setMobileOpen(false)
  }

  const pageTitle = getPageTitle(pathname, search)

  const getInitials = (name: string) =>
    name.split(' ').map(p => p[0]).join('').toUpperCase().slice(0, 2)

  return (
    <div className="min-h-screen flex bg-brand-bg">

      {/* ── Mobile top bar ── */}
      <div className="md:hidden fixed top-0 inset-x-0 h-14 z-30 bg-white border-b border-brand-border flex items-center px-4 gap-3 shadow-sm">
        <button
          onClick={() => setMobileOpen(true)}
          className="p-2 rounded-lg hover:bg-brand-bg transition-colors"
        >
          <Menu size={20} className="text-brand-dark" />
        </button>
        <div className="flex items-center gap-2">
          <img src="/brand/icon-light.svg" alt="" className="w-7 h-7" />
          <span className="font-bold text-brand-dark text-sm">RestOn</span>
        </div>
        {me && (
          <div className="ml-auto flex items-center gap-2">
            <span className="text-xs text-brand-muted">{me.name}</span>
            <div className="w-7 h-7 rounded-full bg-brand-navy flex items-center justify-center">
              <span className="text-white text-xs font-semibold">{getInitials(me.name)}</span>
            </div>
          </div>
        )}
      </div>

      {/* ── Mobile backdrop ── */}
      {mobileOpen && (
        <div
          className="md:hidden fixed inset-0 z-30 bg-black/50 backdrop-blur-sm"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* ── Sidebar ── */}
      <aside className={`
        fixed inset-y-0 left-0 z-40 w-64 bg-[#0F2D3D] flex flex-col shrink-0
        transform transition-transform duration-200 ease-in-out
        ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}
        md:translate-x-0
      `}>

        {/* Logo + workspace */}
        <div className="px-4 pt-5 pb-4">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-2">
              <img src="/brand/icon-dark.svg" alt="RestOn" className="w-9 h-9" />
              <span className="text-white font-bold text-lg tracking-tight">RestOn</span>
            </div>
            <button
              onClick={() => setMobileOpen(false)}
              className="md:hidden p-1 rounded-lg text-white/40 hover:text-white transition-colors"
            >
              <X size={16} />
            </button>
          </div>

          {/* Workspace switcher */}
          <button className="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-white/[0.08] hover:bg-white/[0.12] border border-white/10 transition-colors group">
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-6 h-6 rounded-md bg-brand-green/80 flex items-center justify-center shrink-0">
                <span className="text-white text-xs font-bold">CO</span>
              </div>
              <span className="text-white/90 text-sm font-medium truncate">{me?.tenant_name || me?.name || 'RestOn'}</span>
            </div>
            <ChevronDown size={14} className="text-white/40 group-hover:text-white/60 transition-colors shrink-0" />
          </button>

          {/* iiko status */}
          <div className="flex items-center gap-2 mt-3 px-1">
            <Wifi size={12} className={me?.iiko_connected ? 'text-brand-green' : 'text-white/30'} />
            <span className="text-xs text-white/45">
              {me?.iiko_connected ? 'iiko подключен' : 'iiko не подключён'}
            </span>
          </div>
        </div>

        <div className="h-px bg-white/10 mx-4" />

        {/* Navigation */}
        <nav className="flex-1 px-3 py-3 overflow-y-auto space-y-4 no-scrollbar">
          {NAV_GROUPS.map(group => {
            const visibleItems = group.items.filter(i => !i.adminOnly || isAdmin)
            if (visibleItems.length === 0) return null
            return (
              <div key={group.label}>
                <p className="px-3 mb-1.5 text-[10px] font-semibold text-white/30 tracking-widest uppercase">
                  {group.label}
                </p>
                <div className="space-y-0.5">
                  {visibleItems.map(item => {
                    const Icon = item.icon
                    const active = item.isActive(pathname, search)
                    return (
                      <button
                        key={item.href}
                        onClick={() => handleNav(item.href)}
                        className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all text-left ${
                          active ? 'nav-active' : 'nav-inactive'
                        }`}
                      >
                        <Icon size={15} className="shrink-0" />
                        <span className="truncate flex-1">{item.label}</span>
                        {item.label === 'Интеграции' && !me?.iiko_connected && (
                          <span className="w-1.5 h-1.5 rounded-full bg-red-500 shrink-0" />
                        )}
                      </button>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </nav>

        <div className="h-px bg-white/10 mx-4" />

        {/* User block */}
        {me && (
          <div className="px-4 py-4">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-white/15 flex items-center justify-center shrink-0">
                <span className="text-white text-xs font-semibold">{getInitials(me.name)}</span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate">{me.name}</p>
                <p className="text-xs text-white/40">{isAdmin ? 'Администратор' : 'Пользователь'}</p>
              </div>
              <button
                onClick={onLogout}
                className="p-1.5 rounded-lg text-white/30 hover:text-white/70 hover:bg-white/10 transition-colors"
                title="Выйти"
              >
                <LogOut size={15} />
              </button>
            </div>
          </div>
        )}
      </aside>

      {/* ── Main content area ── */}
      <div className="flex-1 md:ml-64 min-h-screen flex flex-col">

        {/* Topbar */}
        <header className="hidden md:flex sticky top-0 z-20 h-14 bg-white border-b border-brand-border items-center px-6 gap-4 shrink-0 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
          <h1 className="text-base font-semibold text-brand-dark">{pageTitle}</h1>
          <div className="flex items-center gap-2 ml-auto">
            <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border ${
              me?.iiko_connected ? 'bg-emerald-50 border-emerald-200' : 'bg-gray-50 border-gray-200'
            }`}>
              <div className={`w-1.5 h-1.5 rounded-full ${
                me?.iiko_connected ? 'bg-emerald-500 animate-pulse' : 'bg-gray-400'
              }`} />
              <span className={`text-xs font-medium ${
                me?.iiko_connected ? 'text-emerald-700' : 'text-gray-500'
              }`}>
                {me?.iiko_connected ? 'iiko подключен' : 'iiko не подключён'}
              </span>
            </div>
            {me && (
              <div className="flex items-center gap-2 pl-3 border-l border-brand-border">
                <div className="w-7 h-7 rounded-full bg-brand-navy flex items-center justify-center">
                  <span className="text-white text-xs font-semibold">{getInitials(me.name)}</span>
                </div>
                <span className="text-sm text-brand-dark font-medium">{me.name}</span>
                <button
                  onClick={onLogout}
                  className="p-1.5 rounded-lg text-brand-muted hover:text-red-600 hover:bg-red-50 transition-colors"
                  title="Выйти"
                >
                  <LogOut size={14} />
                </button>
              </div>
            )}
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 pt-14 md:pt-0">
          {children}
        </main>
      </div>
    </div>
  )
}
