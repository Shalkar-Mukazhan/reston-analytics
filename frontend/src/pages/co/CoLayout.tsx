import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  Coffee, FileText, ArrowLeftRight, Warehouse, Store,
  Package, Truck, Box, Users, LogOut, Menu, X, FileX2,
} from 'lucide-react'

interface NavItem {
  label: string
  icon: any
  href: string
  adminOnly: boolean
  isActive: (pathname: string, search: string) => boolean
}

const NAV: NavItem[] = [
  {
    label: 'Накладные',
    icon: FileText,
    href: '/co/invoices',
    adminOnly: false,
    isActive: (p) => p === '/co/invoices',
  },
  {
    label: 'Акт Списания',
    icon: FileX2,
    href: '/co/writeoffs',
    adminOnly: false,
    isActive: (p) => p === '/co/writeoffs',
  },
  {
    label: 'Маппинг',
    icon: ArrowLeftRight,
    href: '/co/admin?tab=mapping',
    adminOnly: false,
    isActive: (p, s) => p === '/co/admin' && s.includes('tab=mapping'),
  },
  {
    label: 'Склады',
    icon: Warehouse,
    href: '/co/admin?tab=warehouses',
    adminOnly: false,
    isActive: (p, s) => p === '/co/admin' && s.includes('tab=warehouses'),
  },
  {
    label: 'Рестораны',
    icon: Store,
    href: '/co/admin?tab=restaurants',
    adminOnly: false,
    isActive: (p, s) => p === '/co/admin' && s.includes('tab=restaurants'),
  },
  {
    label: 'Товары',
    icon: Package,
    href: '/co/admin?tab=products',
    adminOnly: true,
    isActive: (p, s) => p === '/co/admin' && s.includes('tab=products'),
  },
  {
    label: 'Поставщики',
    icon: Truck,
    href: '/co/admin?tab=suppliers',
    adminOnly: false,
    isActive: (p, s) => p === '/co/admin' && s.includes('tab=suppliers'),
  },
  {
    label: 'Кейсовки',
    icon: Box,
    href: '/co/admin?tab=containers',
    adminOnly: true,
    isActive: (p, s) => p === '/co/admin' && s.includes('tab=containers'),
  },
  {
    label: 'Пользователи',
    icon: Users,
    href: '/co/admin?tab=users',
    adminOnly: true,
    isActive: (p, s) => p === '/co/admin' && s.includes('tab=users'),
  },
]

export default function CoLayout({
  children,
  me,
  onLogout,
}: {
  children: React.ReactNode
  me: { name: string; role: string } | null
  onLogout: () => void
}) {
  const navigate = useNavigate()
  const { pathname, search } = useLocation()
  const isAdmin = me?.role === 'admin'
  const items = NAV.filter(i => !i.adminOnly || isAdmin)
  const [mobileOpen, setMobileOpen] = useState(false)

  const handleNav = (href: string) => {
    navigate(href)
    setMobileOpen(false)
  }

  return (
    <div className="min-h-screen flex bg-brand-bg">

      {/* Mobile top bar */}
      <div className="md:hidden fixed top-0 inset-x-0 h-14 z-30 bg-white border-b border-brand-border flex items-center px-4 gap-3 shrink-0">
        <button
          onClick={() => setMobileOpen(true)}
          className="p-2 rounded-lg hover:bg-brand-bg transition-colors"
          aria-label="Открыть меню"
        >
          <Menu size={20} className="text-brand-dark" />
        </button>
        <Coffee size={18} className="text-brand-dark shrink-0" />
        <span className="font-bold text-brand-dark text-sm">Coffee Original</span>
        {me && (
          <span className="ml-auto text-xs text-brand-muted truncate max-w-[120px]">{me.name}</span>
        )}
      </div>

      {/* Mobile backdrop */}
      {mobileOpen && (
        <div
          className="md:hidden fixed inset-0 z-30 bg-black/40 backdrop-blur-sm"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed inset-y-0 left-0 z-40 w-64 md:w-52 bg-white border-r border-brand-border flex flex-col shrink-0
        transform transition-transform duration-200 ease-in-out
        ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}
        md:translate-x-0
      `}>
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-4 py-4 border-b border-brand-border">
          <Coffee size={18} className="text-brand-dark shrink-0" />
          <span className="font-bold text-brand-dark text-sm">Coffee Original</span>
          <button
            onClick={() => setMobileOpen(false)}
            className="md:hidden ml-auto p-1 rounded-lg hover:bg-brand-bg transition-colors"
            aria-label="Закрыть меню"
          >
            <X size={16} className="text-brand-muted" />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
          {items.map(item => {
            const Icon = item.icon
            const active = item.isActive(pathname, search)
            return (
              <button
                key={item.href}
                onClick={() => handleNav(item.href)}
                className={`w-full flex items-center gap-2.5 px-3 py-2.5 md:py-2 rounded-lg text-sm transition-colors text-left ${
                  active
                    ? 'bg-brand-yellow/25 text-brand-dark font-semibold'
                    : 'text-brand-muted hover:bg-brand-bg hover:text-brand-dark'
                }`}
              >
                <Icon size={16} className="shrink-0" />
                {item.label}
              </button>
            )
          })}
        </nav>

        {/* User block */}
        {me && (
          <div className="px-4 py-3 border-t border-brand-border bg-brand-bg/60">
            <p className="text-xs font-semibold text-brand-dark truncate">{me.name}</p>
            <p className="text-xs text-brand-muted capitalize">{isAdmin ? 'Администратор' : 'Пользователь'}</p>
            <button
              onClick={onLogout}
              className="flex items-center gap-1.5 text-xs text-brand-muted hover:text-red-600 mt-2 transition-colors"
            >
              <LogOut size={12} /> Выйти
            </button>
          </div>
        )}
      </aside>

      {/* Main */}
      <main className="flex-1 md:ml-52 min-h-screen pt-14 md:pt-0">
        {children}
      </main>
    </div>
  )
}
