import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import coApi from '../../api/coClient'
import CoLayout from './CoLayout'
import {
  FileText, TrendingUp, Store, Clock, Upload, ScanLine,
  CheckCircle2, Send, Eye, ArrowRight, Loader2, CloudUpload,
} from 'lucide-react'

interface SavedInvoice {
  id: number
  restaurant_id: number
  warehouse_name: string | null
  supplier_name: string | null
  invoice_date: string | null
  document_number: string | null
  uploaded_at: string
  status: string
  items_count: number
  total_sum_vat: number | null
}

const STATUS_CHIP: Record<string, { label: string; cls: string }> = {
  recognized:   { label: 'Распознано',        cls: 'badge-ok'   },
  pending:      { label: 'Ожидает проверки',  cls: 'badge-warn' },
  error:        { label: 'Ошибка',            cls: 'badge-over' },
  sent_to_iiko: { label: 'Отправлено в iiko', cls: 'badge-blue' },
  draft:        { label: 'Черновик',          cls: 'badge-muted'},
}

function fmt(n: number | null | undefined): string {
  if (n == null) return '—'
  return new Intl.NumberFormat('ru-KZ', { maximumFractionDigits: 0 }).format(n)
}

function fmtDate(s: string | null): string {
  if (!s) return '—'
  return new Date(s).toLocaleDateString('ru-KZ', { day: '2-digit', month: '2-digit', year: '2-digit' })
}

export default function CoDashboardPage() {
  const navigate = useNavigate()
  const [me, setMe] = useState<{ name: string; role: string } | null>(null)
  const [invoices, setInvoices] = useState<SavedInvoice[]>([])
  const [restaurants, setRestaurants] = useState<{ id: number; name: string }[]>([])
  const [loading, setLoading] = useState(true)
  const [dragging, setDragging] = useState(false)


  useEffect(() => {
    Promise.all([
      coApi.get('/auth/me'),
      coApi.get('/invoices/'),
      coApi.get('/admin/restaurants').catch(() => ({ data: [] })),
    ]).then(([meRes, invRes, restRes]) => {
      setMe(meRes.data)
      setInvoices(invRes.data)
      setRestaurants(restRes.data)
    }).catch(() => navigate('/login'))
      .finally(() => setLoading(false))
  }, [])

  const logout = () => {
    localStorage.removeItem('co_access_token')
    localStorage.removeItem('co_refresh_token')
    navigate('/login')
  }

  const pendingCount = invoices.filter(i => i.status === 'pending').length
  const totalSum = invoices.reduce((a, i) => a + (i.total_sum_vat ?? 0), 0)
  const recent = invoices.slice(0, 10)

  const getRestName = (id: number) =>
    restaurants.find(r => r.id === id)?.name ?? `#${id}`

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    navigate('/invoices')
  }

  const kpis = [
    {
      icon: FileText,
      label: 'Накладных всего',
      value: invoices.length.toString(),
      sub: `${recent.length} последних`,
      color: 'text-brand-navy',
      bg: 'bg-[#0F2D3D]/[0.08]',
    },
    {
      icon: TrendingUp,
      label: 'Общая сумма',
      value: `₸${fmt(totalSum)}`,
      sub: 'По всем документам',
      color: 'text-brand-green',
      bg: 'bg-brand-green/10',
    },
    {
      icon: Store,
      label: 'Ресторанов',
      value: restaurants.length.toString(),
      sub: 'Активных в системе',
      color: 'text-violet-600',
      bg: 'bg-violet-50',
    },
    {
      icon: Clock,
      label: 'Ожидает проверки',
      value: pendingCount.toString(),
      sub: pendingCount > 0 ? 'Требует внимания' : 'Всё обработано',
      color: pendingCount > 0 ? 'text-amber-600' : 'text-emerald-600',
      bg: pendingCount > 0 ? 'bg-amber-50' : 'bg-emerald-50',
    },
  ]

  if (loading) {
    return (
      <CoLayout me={me} onLogout={logout}>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 size={24} className="animate-spin text-brand-muted" />
        </div>
      </CoLayout>
    )
  }

  return (
    <CoLayout me={me} onLogout={logout}>
      <div className="p-5 sm:p-6 space-y-6 max-w-[1400px]">

        {/* KPI cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {kpis.map(kpi => {
            const Icon = kpi.icon
            return (
              <div key={kpi.label} className="card p-5">
                <div className={`w-10 h-10 rounded-xl ${kpi.bg} flex items-center justify-center mb-4`}>
                  <Icon size={18} className={kpi.color} />
                </div>
                <div className="text-2xl font-bold text-brand-dark mb-0.5">{kpi.value}</div>
                <div className="text-sm font-medium text-brand-dark mb-0.5">{kpi.label}</div>
                <div className="text-xs text-brand-muted">{kpi.sub}</div>
              </div>
            )
          })}
        </div>

        {/* Smart Upload + table row */}
        <div className="grid lg:grid-cols-[380px_1fr] gap-4">

          {/* Smart Upload card */}
          <div className="card p-5 flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-brand-dark">Smart Upload</h2>
              <button
                onClick={() => navigate('/invoices')}
                className="text-xs text-brand-green hover:underline flex items-center gap-1"
              >
                Все накладные <ArrowRight size={12} />
              </button>
            </div>

            {/* Pipeline steps */}
            <div className="flex items-center gap-1 mb-5">
              {[
                { icon: CloudUpload, label: 'Фото / PDF' },
                { icon: ScanLine, label: 'Распознавание' },
                { icon: CheckCircle2, label: 'Проверка' },
                { icon: Send, label: 'iiko' },
              ].map((step, i) => {
                const Icon = step.icon
                return (
                  <div key={step.label} className="flex items-center gap-1 flex-1 min-w-0">
                    <div className="flex flex-col items-center flex-1 min-w-0">
                      <div className="w-8 h-8 rounded-lg bg-[#0F2D3D]/[0.08] flex items-center justify-center mb-1">
                        <Icon size={14} className="text-brand-navy" />
                      </div>
                      <span className="text-[10px] text-brand-muted text-center leading-tight truncate w-full px-0.5">
                        {step.label}
                      </span>
                    </div>
                    {i < 3 && (
                      <ArrowRight size={12} className="text-brand-border shrink-0 -mt-3" />
                    )}
                  </div>
                )
              })}
            </div>

            {/* Drop zone */}
            <div
              onDragOver={e => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleFileDrop}
              onClick={() => navigate('/invoices')}
              className={`flex-1 min-h-[140px] rounded-xl border-2 border-dashed flex flex-col items-center justify-center gap-2 cursor-pointer transition-all ${
                dragging
                  ? 'border-brand-green bg-brand-green/5'
                  : 'border-brand-border hover:border-brand-green/50 hover:bg-brand-green/[0.03]'
              }`}
            >
              <div className="w-10 h-10 rounded-full bg-brand-bg flex items-center justify-center">
                <Upload size={18} className="text-brand-muted" />
              </div>
              <div className="text-center">
                <p className="text-sm font-medium text-brand-dark">Перетащите файл сюда</p>
                <p className="text-xs text-brand-muted mt-0.5">JPG, PNG или PDF · до 20 MB</p>
              </div>
            </div>

            <button
              onClick={() => navigate('/invoices')}
              className="mt-3 w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-brand-green text-white text-sm font-semibold
                         hover:brightness-95 active:scale-[0.99] transition-all"
            >
              <Upload size={15} />
              Загрузить файл
            </button>
          </div>

          {/* Recent documents table */}
          <div className="card overflow-hidden flex flex-col">
            <div className="flex items-center justify-between px-5 py-4 border-b border-brand-border">
              <h2 className="text-sm font-semibold text-brand-dark">Последние документы</h2>
              <button
                onClick={() => navigate('/invoices')}
                className="text-xs text-brand-green hover:underline flex items-center gap-1"
              >
                Все <ArrowRight size={12} />
              </button>
            </div>

            {recent.length === 0 ? (
              <div className="flex-1 flex items-center justify-center py-16 text-brand-muted text-sm">
                Нет документов
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-brand-bg border-b border-brand-border text-brand-muted text-xs">
                      <th className="text-left px-4 py-3 font-medium">№</th>
                      <th className="text-left px-4 py-3 font-medium">Вх. номер</th>
                      <th className="text-left px-4 py-3 font-medium">Ресторан</th>
                      <th className="text-left px-4 py-3 font-medium">Склад</th>
                      <th className="text-left px-4 py-3 font-medium">Поставщик</th>
                      <th className="text-left px-4 py-3 font-medium">Дата</th>
                      <th className="text-right px-4 py-3 font-medium">Сумма</th>
                      <th className="text-left px-4 py-3 font-medium">Статус</th>
                      <th className="px-4 py-3" />
                    </tr>
                  </thead>
                  <tbody>
                    {recent.map((inv, idx) => {
                      const chip = STATUS_CHIP[inv.status] ?? { label: inv.status, cls: 'badge-muted' }
                      return (
                        <tr key={inv.id} className="border-b border-brand-border hover:bg-brand-bg/60 transition-colors">
                          <td className="px-4 py-3 text-brand-muted font-mono text-xs">{idx + 1}</td>
                          <td className="px-4 py-3 text-brand-dark font-medium">
                            {inv.document_number ?? <span className="text-brand-muted">—</span>}
                          </td>
                          <td className="px-4 py-3 text-brand-muted text-xs">{getRestName(inv.restaurant_id)}</td>
                          <td className="px-4 py-3 text-brand-muted text-xs">{inv.warehouse_name ?? '—'}</td>
                          <td className="px-4 py-3 text-brand-muted text-xs max-w-[120px] truncate">
                            {inv.supplier_name ?? '—'}
                          </td>
                          <td className="px-4 py-3 text-brand-muted text-xs whitespace-nowrap">
                            {fmtDate(inv.invoice_date ?? inv.uploaded_at)}
                          </td>
                          <td className="px-4 py-3 text-right text-brand-dark text-xs font-medium whitespace-nowrap">
                            {inv.total_sum_vat ? `₸${fmt(inv.total_sum_vat)}` : '—'}
                          </td>
                          <td className="px-4 py-3">
                            <span className={chip.cls}>{chip.label}</span>
                          </td>
                          <td className="px-4 py-3">
                            <button
                              onClick={() => navigate('/invoices')}
                              className="p-1.5 rounded-lg text-brand-muted hover:text-brand-navy hover:bg-brand-bg transition-colors"
                              title="Открыть"
                            >
                              <Eye size={14} />
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

      </div>
    </CoLayout>
  )
}
