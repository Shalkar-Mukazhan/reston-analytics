import { useEffect, useRef, useState } from "react"
import api from "../api/client"
import type { Restaurant, Report } from "../types"
import { useAuth } from "../hooks/useAuth"
import {
  FileText, Download, RefreshCw, Play, ChevronRight,
  Loader2, AlertCircle, CheckCircle2, Clock, X, Send,
} from "lucide-react"
import { cn, formatDate } from "../lib/utils"

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

function ItemStatusBadge({ status }: { status: string }) {
  if (status === "ok") return <span className="badge-ok">В норме</span>
  if (status === "over_limit") return <span className="badge-over">Сверх нормы</span>
  if (status === "no_rate") return <span className="badge-warn">Нет нормы</span>
  if (status === "no_writeoff_needed") return <span className="badge-muted">Без списания</span>
  return <span className="badge-muted">{status}</span>
}

// ── Items modal ───────────────────────────────────────────────────────────────

function ItemsModal({ report, onClose }: { report: ReportWithRestaurant; onClose: () => void }) {
  const [items, setItems] = useState<ReportItem[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<string>("all")
  const [posting, setPosting] = useState(false)
  const [postResult, setPostResult] = useState<{ ok?: string; error?: string } | null>(null)

  useEffect(() => {
    api.get(`/reports/${report.id}/items`).then((res) => {
      setItems(res.data)
      setLoading(false)
    })
  }, [report.id])

  // Все позиции, отсортированные по инвентаризации (минус сначала)
  const allSorted = [...items].sort((a, b) => (a.inventory_qty ?? 0) - (b.inventory_qty ?? 0))
  // Только с минусом — для вкладок "Сверх нормы" и "Проблемные"
  const withMinus = allSorted.filter((i) => i.inventory_qty < 0)

  const filtered =
    filter === "all"        ? allSorted :
    filter === "over_limit" ? withMinus.filter((i) => i.status === "over_limit") :
    filter === "problems"   ? withMinus.filter((i) => i.status === "no_rate" || i.status === "needs_check") :
    filter === "to_writeoff"? items.filter((i) => (i.rate_pct ?? 0) === 100 && (i.to_writeoff_qty ?? 0) > 0) :
    allSorted

  const overCount = withMinus.filter((i) => i.status === "over_limit").length
  const problemsCount = withMinus.filter((i) => i.status === "no_rate" || i.status === "needs_check").length
  const toWriteoffCount = items.filter((i) => (i.rate_pct ?? 0) === 100 && (i.to_writeoff_qty ?? 0) > 0).length

  const postWriteoff = async () => {
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
              Позиции отчёта #{report.id}
            </h2>
            <p className="text-brand-muted text-sm mt-0.5">
              {report.restaurant_name ?? `Ресторан #${report.restaurant_id}`} · {report.period}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-brand-muted">
              <span className="text-brand-red font-semibold">{overCount}</span> сверх нормы ·{" "}
              <span className="text-brand-yellow font-semibold">{toWriteoffCount}</span> к списанию
            </span>
            {toWriteoffCount > 0 && (
              <button
                className="btn-primary text-xs py-1.5 px-3"
                onClick={postWriteoff}
                disabled={posting}
              >
                {posting ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
                {posting ? "Отправляем..." : `К списанию (${toWriteoffCount})`}
              </button>
            )}
            <button onClick={onClose} className="p-2 rounded-lg hover:bg-brand-bg transition-colors">
              <X size={18} className="text-brand-muted" />
            </button>
          </div>
        </div>

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

        {/* Filter tabs */}
        <div className="flex gap-1 px-6 pt-3">
          {[
            { key: "all",         label: "Все",          count: allSorted.length },
            { key: "over_limit",  label: "Сверх нормы",  count: overCount },
            { key: "problems",    label: "Проблемные",   count: problemsCount },
            { key: "to_writeoff", label: "К списанию",   count: toWriteoffCount },
          ].map(({ key, label, count }) => (
            <button
              key={key}
              onClick={() => setFilter(key)}
              className={cn(
                "px-3 py-1.5 text-xs font-medium rounded-lg transition-colors",
                filter === key
                  ? "bg-brand-yellow text-brand-dark"
                  : "text-brand-muted hover:bg-brand-bg"
              )}
            >
              {label}
              <span className="ml-1.5 text-brand-muted/70">{count}</span>
            </button>
          ))}
        </div>

        {/* Table */}
        <div className="flex-1 overflow-auto px-6 pb-6 mt-3">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 size={24} className="animate-spin text-brand-muted" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-20 text-brand-muted text-sm">Нет позиций</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-brand-border">
                  {["Код", "Наименование", "Группа", "Ед.", "Реализация", "Норма %", "Допустимо", "Уже списано", "Списано %", "Инвент.", "К списанию", "Статус"].map((h) => (
                    <th key={h} className="text-left py-2 px-3 text-brand-muted font-medium text-xs uppercase tracking-wide whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => (
                  <tr key={item.id} className={cn(
                    "border-b border-brand-border/50 hover:bg-brand-bg/60 transition-colors",
                    item.is_over_limit && "bg-red-50/50"
                  )}>
                    <td className="py-2 px-3 text-xs text-brand-muted font-mono">{item.product_num ?? "—"}</td>
                    <td className="py-2 px-3 font-medium text-brand-dark max-w-[180px] truncate">{item.product_name ?? "—"}</td>
                    <td className="py-2 px-3 text-brand-muted text-xs">{item.group ?? "—"}</td>
                    <td className="py-2 px-3 text-brand-muted text-xs">{item.unit_type ?? ""}</td>
                    <td className="py-2 px-3 text-right tabular-nums text-sm">{item.sales_qty.toLocaleString("ru-RU", { maximumFractionDigits: 3 })}</td>
                    <td className="py-2 px-3 text-right tabular-nums text-sm text-brand-muted">
                      {item.rate_pct != null ? `${item.rate_pct}%` : "—"}
                    </td>
                    <td className="py-2 px-3 text-right tabular-nums text-sm">{item.allowed_qty.toLocaleString("ru-RU", { maximumFractionDigits: 3 })}</td>
                    <td className={cn("py-2 px-3 text-right tabular-nums text-sm font-medium", item.is_over_limit ? "text-brand-red" : "")}>
                      {item.writeoff_qty.toLocaleString("ru-RU", { maximumFractionDigits: 3 })}
                    </td>
                    <td className={cn("py-2 px-3 text-right tabular-nums text-sm font-medium", item.is_over_limit ? "text-brand-red" : "text-green-600")}>
                      {item.written_off_pct != null ? `${item.written_off_pct.toFixed(1)}%` : "—"}
                    </td>
                    <td className="py-2 px-3 text-right tabular-nums text-sm">{item.inventory_qty.toLocaleString("ru-RU", { maximumFractionDigits: 3 })}</td>
                    <td className="py-2 px-3 text-right tabular-nums text-sm text-brand-yellow font-semibold">
                      {item.to_writeoff_qty != null && item.to_writeoff_qty > 0 ? item.to_writeoff_qty.toLocaleString("ru-RU", { maximumFractionDigits: 3 }) : "—"}
                    </td>
                    <td className="py-2 px-3">
                      <ItemStatusBadge status={item.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function ReportsPage() {
  const { user } = useAuth()
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

  const restaurantName = (id: number) =>
    restaurants.find((r) => r.id === id)?.name ?? `#${id}`

  return (
    <div className="p-6 max-w-6xl mx-auto">
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
        <div className="flex items-center justify-between px-5 py-4 border-b border-brand-border">
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
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-brand-border">
                  {["#", "Ресторан", "Период", "Статус", "Создан", ""].map((h) => (
                    <th key={h} className="text-left py-3 px-5 text-brand-muted font-medium text-xs uppercase tracking-wide whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {reports.map((r) => (
                  <tr key={r.id} className="border-b border-brand-border/50 hover:bg-brand-bg/60 transition-colors">
                    <td className="py-3 px-5 text-brand-muted font-mono text-xs">{r.id}</td>
                    <td className="py-3 px-5 font-medium text-brand-dark">{restaurantName(r.restaurant_id)}</td>
                    <td className="py-3 px-5 text-brand-dark">{r.period}</td>
                    <td className="py-3 px-5">
                      <StatusBadge status={r.status} />
                    </td>
                    <td className="py-3 px-5 text-brand-muted text-xs whitespace-nowrap">
                      {new Date(r.created_at).toLocaleString("ru-RU")}
                    </td>
                    <td className="py-3 px-5">
                      <div className="flex items-center gap-2 justify-end">
                        {r.status === "ready" && (
                          <>
                            <button
                              className="btn-secondary text-xs py-1 px-2.5"
                              onClick={() => setSelectedReport({ ...r, restaurant_name: restaurantName(r.restaurant_id) })}
                            >
                              <ChevronRight size={13} />
                              Просмотр
                            </button>
                            <button
                              className="btn-secondary text-xs py-1 px-2.5"
                              onClick={() => download(r.id)}
                            >
                              <Download size={13} />
                              Excel
                            </button>
                          </>
                        )}
                        {(r.status === "error") && (
                          <span className="text-xs text-brand-red">Ошибка генерации</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Items modal */}
      {selectedReport && (
        <ItemsModal report={selectedReport} onClose={() => setSelectedReport(null)} />
      )}
    </div>
  )
}
