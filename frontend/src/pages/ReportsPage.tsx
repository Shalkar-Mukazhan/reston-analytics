import { useEffect, useRef, useState } from "react"
import api from "../api/client"
import type { Restaurant, Report } from "../types"
import {
  FileText, Download, RefreshCw, Play, ChevronRight,
  Loader2, AlertCircle, CheckCircle2, Clock, X, Send, Trash2,
} from "lucide-react"
import { cn } from "../lib/utils"

function fmtPeriod(period: string): string {
  const wMatch = period.match(/^(\d{4}-\d{2})-W(\d+)$/)
  if (wMatch) return `${wMatch[1]} неделя ${wMatch[2]}`
  if (/^\d{4}-\d{2}$/.test(period)) return `${period} месяц`
  return period
}

// ── Types ────────────────────────────────────────────────────────────────────

interface ReportItem {
  id: number
  product_num: string | null
  product_name: string | null
  group: string | null
  unit_type: string | null
  rate_pct: number | null
  sales_qty: number
  writeoff_qty: number
  inventory_qty: number
  allowed_qty: number
  to_writeoff_qty: number | null
  written_off_pct: number | null
  is_over_limit: boolean
  status: string
  comment: string | null
}

interface ReportWithRestaurant extends Report {
  restaurant_name?: string
  date_from?: string
  date_to?: string
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const STATUS_LABEL: Record<string, string> = {
  pending: "В очереди",
  in_progress: "Генерируется...",
  ready: "Готов",
  error: "Ошибка",
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    pending: "badge-warn",
    in_progress: "badge-warn",
    ready: "badge-ok",
    error: "badge-over",
  }
  const icons: Record<string, React.ReactNode> = {
    pending: <Clock size={11} />,
    in_progress: <Loader2 size={11} className="animate-spin" />,
    ready: <CheckCircle2 size={11} />,
    error: <AlertCircle size={11} />,
  }
  return (
    <span className={cn("badge-muted", map[status] ?? "badge-muted", "inline-flex items-center gap-1")}>
      {icons[status]}
      {STATUS_LABEL[status] ?? status}
    </span>
  )
}

// ── Items modal ───────────────────────────────────────────────────────────────


function ItemsModal({ report, onClose, onPosted }: { report: ReportWithRestaurant; onClose: () => void; onPosted: (id: number) => void }) {
  const [items, setItems] = useState<ReportItem[]>([])
  const [loading, setLoading] = useState(true)
  const [posting, setPosting] = useState(false)
  const [postResult, setPostResult] = useState<{ ok?: string; error?: string } | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)

  useEffect(() => {
    api.get(`/reports/${report.id}/items`).then((res) => {
      setItems(res.data)
      setLoading(false)
    })
  }, [report.id])

  const overCount      = items.filter((i) => i.status === "over_limit").length
  const toWriteoffItems = items.filter((i) => (i.rate_pct ?? 0) === 100 && (i.to_writeoff_qty ?? 0) > 0)
  const toWriteoffCount = toWriteoffItems.length
  const toWriteoffQty   = toWriteoffItems.reduce((s, i) => s + (i.to_writeoff_qty ?? 0), 0)
  const okCount        = items.filter((i) => i.status === "ok").length

  const postWriteoff = async () => {
    setConfirmOpen(false)
    setPosting(true)
    setPostResult(null)
    try {
      const res = await api.post(`/reports/${report.id}/post-writeoff`)
      const data = res.data
      const periodClosedErr = data.errors?.find((e: any) => e.period_closed)
      if (periodClosedErr) {
        setPostResult({ error: "Период закрыт в IIKO — списание за этот период недоступно. Обратитесь к администратору." })
      } else if (data.errors?.length > 0 && data.docs_sent === 0) {
        setPostResult({ error: data.errors[0]?.error || "Ошибка отправки" })
      } else {
        setPostResult({ ok: `Отправлено документов: ${data.docs_sent}${data.errors?.length ? `, ошибок: ${data.errors.length}` : ""}` })
        onPosted(report.id)
      }
    } catch (e: any) {
      setPostResult({ error: e.response?.data?.detail || e.message })
    } finally {
      setPosting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-5xl max-h-[90vh] flex flex-col">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-brand-border">
          <div>
            <h2 className="font-bold text-brand-dark text-lg">
              {report.restaurant_name ?? `Ресторан #${report.restaurant_id}`}
            </h2>
            <p className="text-brand-muted text-sm mt-0.5">{fmtPeriod(report.period)}</p>
          </div>
          <div className="flex items-center gap-2">
            {toWriteoffCount > 0 && (
              <button
                className="btn-primary text-xs py-1.5 px-3"
                onClick={() => setConfirmOpen(true)}
                disabled={posting || report.writeoff_posted}
                title={report.writeoff_posted ? "Списание уже отправлено" : undefined}
              >
                {posting ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
                {posting ? "Отправляем..." : "Отправить к списанию"}
              </button>
            )}
            <button onClick={onClose} className="p-2 rounded-lg hover:bg-brand-bg transition-colors">
              <X size={18} className="text-brand-muted" />
            </button>
          </div>
        </div>

        {/* Сводка */}
        {!loading && (
          <div className="grid grid-cols-4 gap-3 px-6 pt-4">
            <div className="rounded-xl border border-brand-border bg-brand-bg/50 p-3 text-center">
              <p className="text-2xl font-bold text-brand-dark">{items.length}</p>
              <p className="text-xs text-brand-muted mt-0.5">Всего позиций</p>
            </div>
            <div className={cn("rounded-xl border p-3 text-center", overCount > 0 ? "border-red-200 bg-red-50" : "border-brand-border bg-brand-bg/50")}>
              <p className={cn("text-2xl font-bold", overCount > 0 ? "text-brand-red" : "text-brand-muted")}>{overCount}</p>
              <p className="text-xs text-brand-muted mt-0.5">Сверх нормы</p>
            </div>
            <div className={cn("rounded-xl border p-3 text-center", toWriteoffCount > 0 ? "border-yellow-200 bg-yellow-50" : "border-brand-border bg-brand-bg/50")}>
              <p className={cn("text-2xl font-bold", toWriteoffCount > 0 ? "text-brand-yellow" : "text-brand-muted")}>{toWriteoffCount}</p>
              <p className="text-xs text-brand-muted mt-0.5">
                К списанию
                {toWriteoffCount > 0 && <span className="block font-semibold">{toWriteoffQty.toLocaleString("ru-RU", { maximumFractionDigits: 2 })} кг/шт</span>}
              </p>
            </div>
            <div className={cn("rounded-xl border p-3 text-center", okCount === items.length && items.length > 0 ? "border-green-200 bg-green-50" : "border-brand-border bg-brand-bg/50")}>
              <p className={cn("text-2xl font-bold", okCount === items.length && items.length > 0 ? "text-green-600" : "text-brand-muted")}>{okCount}</p>
              <p className="text-xs text-brand-muted mt-0.5">В норме</p>
            </div>
          </div>
        )}

        {/* Post result */}
        {postResult && (
          <div className={cn(
            "mx-6 mt-3 flex items-center gap-2 p-3 rounded-lg text-sm",
            postResult.ok ? "bg-green-50 border border-green-100 text-green-700" : "bg-red-50 border border-red-100 text-brand-red"
          )}>
            {postResult.ok ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
            {postResult.ok || postResult.error}
          </div>
        )}

        {/* Table */}
        <div className="flex-1 overflow-auto px-6 pb-6 mt-3">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 size={24} className="animate-spin text-brand-muted" />
            </div>
          ) : toWriteoffItems.length === 0 ? (
            <div className="text-center py-20 text-brand-muted text-sm">Нет позиций к списанию</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-brand-border bg-brand-bg/60 sticky top-0">
                  <th className="text-left py-2 px-3 text-brand-muted font-medium text-xs uppercase tracking-wide">Наименование</th>
                  <th className="text-left py-2 px-3 text-brand-muted font-medium text-xs uppercase tracking-wide">Группа</th>
                  <th className="text-right py-2 px-3 text-brand-muted font-medium text-xs uppercase tracking-wide whitespace-nowrap">К списанию</th>
                  <th className="text-right py-2 px-3 text-brand-muted font-medium text-xs uppercase tracking-wide whitespace-nowrap">Инвентаризация</th>
                </tr>
              </thead>
              <tbody>
                {toWriteoffItems.map((item) => (
                  <tr key={item.id} className="border-b border-brand-border/40 hover:bg-brand-bg/50 transition-colors">
                    <td className="py-2.5 px-3">
                      <p className="font-medium text-brand-dark max-w-[260px] truncate">{item.product_name ?? "—"}</p>
                      {item.unit_type && <p className="text-xs text-brand-muted">{item.unit_type}</p>}
                    </td>
                    <td className="py-2.5 px-3 text-brand-muted text-xs max-w-[140px] truncate">{item.group ?? "—"}</td>
                    <td className="py-2.5 px-3 text-right tabular-nums whitespace-nowrap">
                      <span className="font-bold text-brand-yellow">{item.to_writeoff_qty!.toLocaleString("ru-RU", { maximumFractionDigits: 3 })}</span>
                    </td>
                    <td className="py-2.5 px-3 text-right tabular-nums whitespace-nowrap">
                      <span className="font-semibold text-brand-red">{item.inventory_qty.toLocaleString("ru-RU", { maximumFractionDigits: 3 })}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Confirm диалог отправки в IIKO */}
      {confirmOpen && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6">
            <div className="flex items-start gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-brand-yellow/15 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Send size={18} className="text-brand-yellow" />
              </div>
              <div>
                <h3 className="font-bold text-brand-dark text-base">Отправить к списанию?</h3>
                <p className="text-brand-muted text-sm mt-1">
                  Будет создан акт списания по счетам на{" "}
                  <span className="font-semibold text-brand-dark">{toWriteoffCount} позиций</span>.
                  Документ появится в IIKO — не забудьте проверить и провести его.
                </p>
              </div>
            </div>
            <div className="text-xs text-brand-muted bg-brand-bg rounded-lg p-3 mb-5">
              Ресторан: <span className="font-medium text-brand-dark">{report.restaurant_name}</span><br />
              Период: <span className="font-medium text-brand-dark">{fmtPeriod(report.period)}</span>
            </div>
            <div className="flex gap-2">
              <button
                className="flex-1 px-4 py-2 rounded-lg border border-brand-border text-brand-muted text-sm font-medium hover:bg-brand-bg transition-colors"
                onClick={() => setConfirmOpen(false)}
              >
                Отмена
              </button>
              <button
                className="flex-1 btn-primary text-sm py-2"
                onClick={postWriteoff}
              >
                <Send size={14} />
                Да, отправить
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function ReportsPage() {
  const [restaurants, setRestaurants] = useState<Restaurant[]>([])
  const [reports, setReports] = useState<ReportWithRestaurant[]>([])
  const [restaurantId, setRestaurantId] = useState("")
  const [periodType, setPeriodType] = useState<"month" | "week">("month")
  const [year, setYear] = useState(() => new Date().getFullYear())
  const [month, setMonth] = useState(() => new Date().getMonth() + 1)
  const [week, setWeek] = useState(1)
  const [availableWeeks, setAvailableWeeks] = useState<{ week: number; label: string }[]>([])
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState("")
  const [loadingReports, setLoadingReports] = useState(true)
  const [selectedReport, setSelectedReport] = useState<ReportWithRestaurant | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<ReportWithRestaurant | null>(null)
  const [deleting, setDeleting] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    api.get("/auth/me").then((res) => {
      setRestaurants(res.data.restaurants)
      if (res.data.restaurants.length === 1) setRestaurantId(String(res.data.restaurants[0].id))
    })
    loadReports()
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  // Загружаем доступные недели при смене месяца/года
  useEffect(() => {
    if (periodType !== "week") return
    api.get(`/reports/weeks?year=${year}&month=${month}`).then((res) => {
      setAvailableWeeks(res.data)
      if (res.data.length > 0) setWeek(res.data[0].week)
    })
  }, [year, month, periodType])

  const loadReports = async () => {
    setLoadingReports(true)
    try {
      const res = await api.get("/reports/")
      const data: ReportWithRestaurant[] = res.data
      setReports(data)
      // Start polling if any report is in progress
      const hasPending = data.some((r) => r.status === "pending" || r.status === "in_progress")
      if (hasPending && !pollRef.current) {
        pollRef.current = setInterval(async () => {
          const r2 = await api.get("/reports/")
          setReports(r2.data)
          const stillPending = r2.data.some((r: Report) => r.status === "pending" || r.status === "in_progress")
          if (!stillPending && pollRef.current) {
            clearInterval(pollRef.current)
            pollRef.current = null
          }
        }, 3000)
      }
    } finally {
      setLoadingReports(false)
    }
  }

  const buildPeriod = () => {
    const mm = String(month).padStart(2, "0")
    if (periodType === "month") return `${year}-${mm}`
    return `${year}-${mm}-W${week}`
  }

  const generate = async () => {
    if (!restaurantId) return
    setGenerating(true)
    setError("")
    try {
      await api.post("/reports/generate", {
        restaurant_id: Number(restaurantId),
        period: buildPeriod(),
        period_type: periodType,
      })
      await loadReports()
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setGenerating(false)
    }
  }

  const download = async (reportId: number) => {
    const token = localStorage.getItem("access_token")
    const res = await fetch(`/api/reports/${reportId}/download`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) { setError("Ошибка скачивания файла"); return }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    const cd = res.headers.get("content-disposition") || ""
    const match = cd.match(/filename="?([^"]+)"?/)
    a.download = match?.[1] ?? `report_${reportId}.xlsx`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  const deleteReport = async (report: ReportWithRestaurant) => {
    setDeleting(true)
    try {
      await api.delete(`/reports/${report.id}`)
      await loadReports()
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setDeleting(false)
      setDeleteConfirm(null)
    }
  }

  const restaurantName = (id: number) =>
    restaurants.find((r) => r.id === id)?.name ?? `#${id}`

  return (
    <div className="p-4 sm:p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-brand-dark">Отчёты</h1>
        <p className="text-brand-muted text-sm mt-1">Генерация и просмотр отчётов по списаниям</p>
      </div>

      {/* Generate card */}
      <div className="card p-5 mb-6">
        <h2 className="font-semibold text-brand-dark mb-4 flex items-center gap-2">
          <Play size={16} className="text-brand-yellow" />
          Сгенерировать отчёт
        </h2>
        <div className="flex flex-wrap gap-3 items-end">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-brand-muted uppercase tracking-wide">Ресторан</label>
            <select
              className="input min-w-[220px]"
              value={restaurantId}
              onChange={(e) => setRestaurantId(e.target.value)}
            >
              <option value="">Выберите ресторан</option>
              {restaurants.map((r) => (
                <option key={r.id} value={r.id}>{r.name}</option>
              ))}
            </select>
          </div>
          {/* Тип периода */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-brand-muted uppercase tracking-wide">Тип периода</label>
            <div className="flex rounded-lg border border-brand-border overflow-hidden bg-white">
              {(["month", "week"] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setPeriodType(t)}
                  className={cn(
                    "px-4 py-2 text-sm font-medium transition-colors",
                    periodType === t ? "bg-brand-yellow text-brand-dark" : "text-brand-muted hover:bg-brand-bg"
                  )}
                >
                  {t === "month" ? "Месяц" : "Неделя"}
                </button>
              ))}
            </div>
          </div>

          {/* Год */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-brand-muted uppercase tracking-wide">Год</label>
            <select className="input w-24" value={year} onChange={(e) => setYear(Number(e.target.value))}>
              {[2024, 2025, 2026].map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>

          {/* Месяц */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-brand-muted uppercase tracking-wide">Месяц</label>
            <select className="input w-32" value={month} onChange={(e) => setMonth(Number(e.target.value))}>
              {["Январь","Февраль","Март","Апрель","Май","Июнь","Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"].map((name, i) => (
                <option key={i+1} value={i+1}>{name}</option>
              ))}
            </select>
          </div>

          {/* Неделя (только для week) */}
          {periodType === "week" && (
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-brand-muted uppercase tracking-wide">Неделя</label>
              <select className="input" value={week} onChange={(e) => setWeek(Number(e.target.value))}>
                {availableWeeks.length > 0
                  ? availableWeeks.map((w) => (
                      <option key={w.week} value={w.week}>{w.label}</option>
                    ))
                  : [1,2,3,4].map((w) => (
                      <option key={w} value={w}>{w}-я</option>
                    ))
                }
              </select>
            </div>
          )}
          <button
            className="btn-primary"
            onClick={generate}
            disabled={generating || !restaurantId || !year || !month}
          >
            {generating ? (
              <>
                <Loader2 size={15} className="animate-spin" />
                Запускаем...
              </>
            ) : (
              <>
                <Play size={15} />
                Сгенерировать
              </>
            )}
          </button>
        </div>
        {error && (
          <div className="mt-3 flex items-center gap-2 p-3 rounded-lg bg-red-50 border border-red-100">
            <AlertCircle size={15} className="text-brand-red flex-shrink-0" />
            <span className="text-brand-red text-sm">{error}</span>
          </div>
        )}
      </div>

      {/* Reports list */}
      <div className="card">
        <div className="flex items-center justify-between px-4 sm:px-5 py-4 border-b border-brand-border">
          <h2 className="font-semibold text-brand-dark flex items-center gap-2">
            <FileText size={16} className="text-brand-yellow" />
            История отчётов
          </h2>
          <button
            className="btn-secondary text-xs py-1.5 px-3"
            onClick={loadReports}
            disabled={loadingReports}
          >
            <RefreshCw size={13} className={loadingReports ? "animate-spin" : ""} />
            Обновить
          </button>
        </div>

        {loadingReports && reports.length === 0 ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 size={24} className="animate-spin text-brand-muted" />
          </div>
        ) : reports.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-brand-muted">
            <FileText size={40} className="text-brand-border mb-3" />
            <p className="text-sm">Отчётов пока нет</p>
            <p className="text-xs mt-1">Сгенерируйте первый отчёт выше</p>
          </div>
        ) : (
          <>
            {/* Desktop: таблица */}
            <div className="hidden sm:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-brand-border">
                    {["Ресторан", "Период", "Статус", "Создан", ""].map((h) => (
                      <th key={h} className="text-left py-3 px-5 text-brand-muted font-medium text-xs uppercase tracking-wide whitespace-nowrap">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {reports.map((r) => (
                    <tr
                      key={r.id}
                      className={cn(
                        "border-b border-brand-border/50 transition-colors",
                        r.status === "ready" ? "hover:bg-brand-bg/60 cursor-pointer" : ""
                      )}
                      onClick={() => {
                        if (r.status === "ready") setSelectedReport({ ...r, restaurant_name: restaurantName(r.restaurant_id) })
                      }}
                    >
                      <td className="py-3 px-5 font-medium text-brand-dark">{restaurantName(r.restaurant_id)}</td>
                      <td className="py-3 px-5 text-brand-dark">{fmtPeriod(r.period)}</td>
                      <td className="py-3 px-5"><StatusBadge status={r.status} /></td>
                      <td className="py-3 px-5 text-brand-muted text-xs whitespace-nowrap">
                        {new Date(r.created_at).toLocaleString("ru-RU")}
                      </td>
                      <td className="py-3 px-5">
                        <div className="flex items-center gap-2 justify-end" onClick={(e) => e.stopPropagation()}>
                          {r.status === "ready" && (
                            <button className="btn-secondary text-xs py-1 px-2.5" onClick={() => download(r.id)}>
                              <Download size={13} />Excel
                            </button>
                          )}
                          {r.status === "error" && (
                            <button className="text-xs text-brand-red hover:underline" onClick={() => generate()}>
                              Повторить
                            </button>
                          )}
                          <button
                            className="p-1.5 rounded-lg text-brand-muted hover:bg-red-50 hover:text-brand-red transition-colors"
                            onClick={() => setDeleteConfirm({ ...r, restaurant_name: restaurantName(r.restaurant_id) })}
                            title="Удалить"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile: карточки */}
            <div className="sm:hidden divide-y divide-brand-border/40">
              {reports.map((r) => (
                <div
                  key={r.id}
                  className={cn(
                    "px-4 py-3.5 transition-colors",
                    r.status === "ready" ? "cursor-pointer active:bg-brand-bg/60" : ""
                  )}
                  onClick={() => {
                    if (r.status === "ready") setSelectedReport({ ...r, restaurant_name: restaurantName(r.restaurant_id) })
                  }}
                >
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div className="min-w-0">
                      <p className="font-semibold text-brand-dark text-sm truncate">{restaurantName(r.restaurant_id)}</p>
                      <p className="text-brand-muted text-xs mt-0.5">{fmtPeriod(r.period)}</p>
                    </div>
                    <StatusBadge status={r.status} />
                  </div>
                  <div className="flex items-center justify-between">
                    <p className="text-brand-muted text-xs">
                      {new Date(r.created_at).toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
                    </p>
                    <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                      {r.status === "ready" && (
                        <button
                          className="flex items-center gap-1 text-xs font-medium text-brand-dark border border-brand-border rounded-lg px-2.5 py-1.5 hover:bg-brand-bg transition-colors"
                          onClick={() => download(r.id)}
                        >
                          <Download size={12} />Excel
                        </button>
                      )}
                      {r.status === "ready" && (
                        <button
                          className="flex items-center gap-1 text-xs font-medium text-brand-dark border border-brand-border rounded-lg px-2.5 py-1.5 hover:bg-brand-bg transition-colors"
                          onClick={() => setSelectedReport({ ...r, restaurant_name: restaurantName(r.restaurant_id) })}
                        >
                          <ChevronRight size={12} />Открыть
                        </button>
                      )}
                      {r.status === "error" && (
                        <button className="text-xs text-brand-red font-medium" onClick={() => generate()}>
                          Повторить
                        </button>
                      )}
                      <button
                        className="p-1.5 rounded-lg text-brand-muted hover:bg-red-50 hover:text-brand-red transition-colors"
                        onClick={() => setDeleteConfirm({ ...r, restaurant_name: restaurantName(r.restaurant_id) })}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Items modal */}
      {selectedReport && (
        <ItemsModal
          report={selectedReport}
          onClose={() => setSelectedReport(null)}
          onPosted={(id) => {
            setReports((prev) => prev.map((r) => r.id === id ? { ...r, writeoff_posted: true } : r))
            setSelectedReport((prev) => prev ? { ...prev, writeoff_posted: true } : prev)
          }}
        />
      )}

      {/* Delete confirm modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-6">
            <div className="flex items-start gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-50 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Trash2 size={18} className="text-brand-red" />
              </div>
              <div>
                <h3 className="font-bold text-brand-dark text-base">Удалить отчёт?</h3>
                <p className="text-brand-muted text-sm mt-1">
                  Отчёт будет удалён безвозвратно. Восстановить данные будет невозможно.
                </p>
              </div>
            </div>
            <div className="text-xs text-brand-muted bg-brand-bg rounded-lg p-3 mb-5">
              Ресторан: <span className="font-medium text-brand-dark">{deleteConfirm.restaurant_name}</span><br />
              Период: <span className="font-medium text-brand-dark">{fmtPeriod(deleteConfirm.period)}</span>
            </div>
            <div className="flex gap-2">
              <button
                className="flex-1 px-4 py-2 rounded-lg border border-brand-border text-brand-muted text-sm font-medium hover:bg-brand-bg transition-colors"
                onClick={() => setDeleteConfirm(null)}
                disabled={deleting}
              >
                Отмена
              </button>
              <button
                className="flex-1 px-4 py-2 rounded-lg bg-brand-red text-white text-sm font-medium hover:bg-red-700 transition-colors flex items-center justify-center gap-1.5 disabled:opacity-60"
                onClick={() => deleteReport(deleteConfirm)}
                disabled={deleting}
              >
                {deleting ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                {deleting ? "Удаляем..." : "Удалить"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
