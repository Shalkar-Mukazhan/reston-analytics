import { useEffect, useState } from "react"
import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ReferenceLine, ResponsiveContainer,
} from "recharts"
import {
  TrendingDown, BarChart3, AlertTriangle,
  CheckCircle2, Loader2, Store, RefreshCw,
} from "lucide-react"
import api from "../api/client"
import { useAuth } from "../hooks/useAuth"
import { cn } from "../lib/utils"

// ── Types ────────────────────────────────────────────────────────────────────
interface MonthPoint {
  month: number
  month_name: string
  period: string
  has_data: boolean
  revenue_sum: number
  shortage_sum: number
  complete_waste_sum: number
  shortage_pct: number
  writeoff_pct: number
  waste_pct: number
  over_limit_count: number
  to_writeoff_qty: number
  waste_limit: number
}

interface YearlyData {
  year: number
  restaurant_id: number | null
  totals: {
    revenue_sum: number
    shortage_sum: number
    complete_waste_sum: number
    avg_waste_pct: number
    months_with_data: number
  }
  months: MonthPoint[]
}

interface Restaurant {
  id: number
  name: string
  code: string
}

// ── Helpers ──────────────────────────────────────────────────────────────────
const WASTE_LIMIT = 0.3
const COLORS = {
  shortage: "#ef4444",
  writeoff: "#3b82f6",
  waste: "#f59e0b",
  limit: "#9ca3af",
}

function fmt(n: number, d = 2) {
  return n.toLocaleString("ru-RU", { minimumFractionDigits: d, maximumFractionDigits: d })
}

function fmtMoney(n: number) {
  if (n >= 1_000_000) return `${fmt(n / 1_000_000, 1)} млн ₸`
  if (n >= 1_000) return `${fmt(n / 1_000, 0)} тыс ₸`
  return `${fmt(n, 0)} ₸`
}

// ── Custom tooltips ──────────────────────────────────────────────────────────
function PctTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-brand-border rounded-xl shadow-lg p-3 text-xs min-w-[170px]">
      <p className="font-semibold text-brand-dark mb-2">{label}</p>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex justify-between gap-4 py-0.5">
          <span style={{ color: p.color }}>{p.name}</span>
          <span className="font-mono font-medium">{fmt(p.value)}%</span>
        </div>
      ))}
    </div>
  )
}

function SumTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-brand-border rounded-xl shadow-lg p-3 text-xs min-w-[190px]">
      <p className="font-semibold text-brand-dark mb-2">{label}</p>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex justify-between gap-4 py-0.5">
          <span style={{ color: p.fill }}>{p.name}</span>
          <span className="font-mono font-medium">{fmtMoney(p.value)}</span>
        </div>
      ))}
    </div>
  )
}

// ── KPI card ─────────────────────────────────────────────────────────────────
function KpiCard({ label, value, sub, color = "default", icon }: {
  label: string; value: string; sub?: string
  color?: "red" | "green" | "blue" | "default"; icon?: React.ReactNode
}) {
  const textColor = { red: "text-brand-red", green: "text-green-600", blue: "text-blue-600", default: "text-brand-dark" }[color]
  return (
    <div className="card p-5 flex items-start gap-4">
      {icon && <div className="mt-0.5 flex-shrink-0">{icon}</div>}
      <div className="min-w-0">
        <p className="text-brand-muted text-xs uppercase tracking-wide mb-1">{label}</p>
        <p className={cn("text-2xl font-bold", textColor)}>{value}</p>
        {sub && <p className="text-brand-muted text-xs mt-1">{sub}</p>}
      </div>
    </div>
  )
}

// ── Месячная таблица ─────────────────────────────────────────────────────────
function MonthTable({ months }: { months: MonthPoint[] }) {
  return (
    <div className="card overflow-hidden">
      <div className="px-5 py-4 border-b border-brand-border">
        <h2 className="font-semibold text-brand-dark">Детализация по месяцам</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-brand-border bg-brand-bg/50">
              {["Месяц", "Выручка (без НДС)", "Stat Lost сумма", "Stat Lost %", "Complete Waste сумма", "Complete Waste %", "Waste %", "Сверх нормы"].map(h => (
                <th key={h} className="text-left py-2.5 px-4 text-brand-muted font-medium text-xs uppercase tracking-wide whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {months.map((m) => (
              <tr key={m.month} className={cn(
                "border-b border-brand-border/40 transition-colors",
                !m.has_data ? "opacity-35"
                  : m.waste_pct > WASTE_LIMIT ? "bg-red-50/40 hover:bg-red-50/60"
                  : "hover:bg-brand-bg/60"
              )}>
                <td className="py-2.5 px-4 font-medium text-brand-dark">{m.month_name}</td>
                <td className="py-2.5 px-4 tabular-nums text-xs text-brand-muted">{m.has_data ? fmtMoney(m.revenue_sum) : "—"}</td>
                <td className="py-2.5 px-4 tabular-nums text-xs text-brand-red">{m.has_data ? fmtMoney(m.shortage_sum) : "—"}</td>
                <td className="py-2.5 px-4 tabular-nums text-xs font-medium text-brand-red">{m.has_data ? `${fmt(m.shortage_pct)}%` : "—"}</td>
                <td className="py-2.5 px-4 tabular-nums text-xs text-blue-600">{m.has_data ? fmtMoney(m.complete_waste_sum) : "—"}</td>
                <td className="py-2.5 px-4 tabular-nums text-xs text-blue-600">{m.has_data ? `${fmt(m.writeoff_pct)}%` : "—"}</td>
                <td className="py-2.5 px-4">
                  {m.has_data ? (
                    <span className={cn(
                      "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold",
                      m.waste_pct > WASTE_LIMIT ? "bg-red-100 text-brand-red" : "bg-green-100 text-green-700"
                    )}>
                      {m.waste_pct > WASTE_LIMIT ? <AlertTriangle size={10} /> : <CheckCircle2 size={10} />}
                      {fmt(m.waste_pct)}%
                    </span>
                  ) : "—"}
                </td>
                <td className="py-2.5 px-4 tabular-nums text-xs">
                  {m.has_data && m.over_limit_count > 0
                    ? <span className="text-brand-red font-medium">{m.over_limit_count}</span>
                    : <span className="text-brand-muted">—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Главная страница ──────────────────────────────────────────────────────────
export default function AnalyticsPage() {
  const { user } = useAuth()
  const isCoOrAdmin = user?.role === "co" || user?.role === "admin"

  const [data, setData] = useState<YearlyData | null>(null)
  const [loading, setLoading] = useState(true)
  const [restaurants, setRestaurants] = useState<Restaurant[]>([])
  const [year, setYear] = useState(new Date().getFullYear())
  const [restaurantId, setRestaurantId] = useState<number | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [syncMsg, setSyncMsg] = useState<{ type: "success" | "error"; text: string } | null>(null)

  useEffect(() => {
    if (isCoOrAdmin) {
      api.get("/analytics/restaurants").then(res => setRestaurants(res.data))
    }
  }, [isCoOrAdmin])

  const load = async (y: number, rid: number | null) => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ year: String(y) })
      if (rid) params.set("restaurant_id", String(rid))

      const yearRes = await api.get(`/analytics/yearly?${params}`)
      setData(yearRes.data)
    } finally {
      setLoading(false)
    }
  }

  const syncFromIiko = async () => {
    if (!restaurantId) {
      setSyncMsg({ type: "error", text: "Выберите конкретный ресторан для синхронизации из IIKO" })
      return
    }
    setSyncing(true); setSyncMsg(null)
    try {
      const params = new URLSearchParams({ restaurant_id: String(restaurantId), year: String(year) })
      const { data: d } = await api.post(`/analytics/sync-iiko?${params}`)
      // Async: получили task_id — теперь поллим статус
      if (d.task_id) {
        setSyncMsg({ type: "success", text: "Синхронизация запущена, загружаем данные из IIKO..." })
        const taskId = d.task_id
        let attempts = 0
        const maxAttempts = 40  // макс 2 минуты (40 × 3сек)
        const poll = setInterval(async () => {
          attempts++
          try {
            const { data: st } = await api.get(`/analytics/task-status/${taskId}`)
            if (st.status === "done") {
              clearInterval(poll)
              setSyncing(false)
              const res = st.result || {}
              const synced = res.synced ?? 0
              const errors = res.errors?.length ?? 0
              setSyncMsg({ type: "success", text: `Синхронизировано ${synced} месяцев${errors > 0 ? ` (ошибок: ${errors})` : ""}` })
              await load(year, restaurantId)
            } else if (st.status === "failure" || attempts >= maxAttempts) {
              clearInterval(poll)
              setSyncing(false)
              setSyncMsg({ type: "error", text: "Ошибка синхронизации или таймаут" })
            }
          } catch { /* сеть — продолжаем */ }
        }, 3000)
      }
    } catch (e: any) {
      setSyncMsg({ type: "error", text: e.response?.data?.detail || e.message })
      setSyncing(false)
    }
  }

  useEffect(() => { load(year, restaurantId) }, [year, restaurantId])

  const years = Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - i)
  const chartMonths = data?.months ?? []

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">

      {/* ── Заголовок ── */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-brand-dark">Аналитика</h1>
          <p className="text-brand-muted mt-0.5 text-sm">Динамика показателей по месяцам · данные из IIKO напрямую</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {isCoOrAdmin && restaurants.length > 0 && (
            <select
              value={restaurantId ?? ""}
              onChange={e => setRestaurantId(e.target.value ? Number(e.target.value) : null)}
              className="h-9 px-3 rounded-lg border border-brand-border bg-white text-sm text-brand-dark focus:outline-none focus:ring-2 focus:ring-brand-yellow/40"
            >
              <option value="">Все рестораны</option>
              {restaurants.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
          )}
          <select
            value={year}
            onChange={e => setYear(Number(e.target.value))}
            className="h-9 px-3 rounded-lg border border-brand-border bg-white text-sm text-brand-dark focus:outline-none focus:ring-2 focus:ring-brand-yellow/40"
          >
            {years.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
          {isCoOrAdmin && (
            <button
              className="h-9 px-3 rounded-lg border border-brand-border bg-white text-sm text-brand-dark flex items-center gap-2 hover:border-brand-yellow transition-colors disabled:opacity-50"
              onClick={syncFromIiko}
              disabled={syncing}
              title="Загрузить данные напрямую из IIKO (нужно выбрать ресторан)"
            >
              {syncing ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} className="text-brand-yellow" />}
              Обновить из IIKO
            </button>
          )}
        </div>
      </div>

      {syncMsg && (
        <div className={`flex items-center gap-2 p-3 rounded-lg text-sm ${
          syncMsg.type === "success"
            ? "bg-green-50 border border-green-100 text-green-700"
            : "bg-red-50 border border-red-100 text-red-700"
        }`}>
          {syncMsg.type === "success" ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}
          {syncMsg.text}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-40">
          <Loader2 size={28} className="animate-spin text-brand-muted" />
        </div>
      ) : !data ? null : (
        <>
          {/* ── KPI Cards ── */}
          <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
            <KpiCard
              label="Выручка за год (без НДС)"
              value={fmtMoney(data.totals.revenue_sum)}
              sub={`${data.totals.months_with_data} мес. с данными`}
              icon={<div className="p-2 rounded-xl bg-green-50"><BarChart3 size={18} className="text-green-600" /></div>}
            />
            <KpiCard
              label="Stat Lost (сумма)"
              value={fmtMoney(data.totals.shortage_sum)}
              sub="Недостача по инвентаризации"
              color="red"
              icon={<div className="p-2 rounded-xl bg-red-50"><TrendingDown size={18} className="text-brand-red" /></div>}
            />
            <KpiCard
              label="Complete Waste (сумма)"
              value={fmtMoney(data.totals.complete_waste_sum)}
              sub="Полное списание"
              color="blue"
              icon={<div className="p-2 rounded-xl bg-blue-50"><Store size={18} className="text-blue-600" /></div>}
            />
            <KpiCard
              label="Avg Waste %"
              value={`${fmt(data.totals.avg_waste_pct)}%`}
              sub={data.totals.avg_waste_pct > WASTE_LIMIT ? `Превышение! Лимит ${WASTE_LIMIT}%` : `В норме ≤ ${WASTE_LIMIT}%`}
              color={data.totals.avg_waste_pct > WASTE_LIMIT ? "red" : "green"}
              icon={
                <div className={cn("p-2 rounded-xl", data.totals.avg_waste_pct > WASTE_LIMIT ? "bg-red-50" : "bg-green-50")}>
                  {data.totals.avg_waste_pct > WASTE_LIMIT
                    ? <AlertTriangle size={18} className="text-brand-red" />
                    : <CheckCircle2 size={18} className="text-green-600" />}
                </div>
              }
            />
          </div>

          {/* ── График % ── */}
          <div className="card p-5">
            <div className="mb-4">
              <h2 className="font-semibold text-brand-dark">Динамика показателей, %</h2>
              <p className="text-xs text-brand-muted mt-0.5">Stat Lost %, Complete Waste %, Waste State % по месяцам · лимит {WASTE_LIMIT}%</p>
            </div>
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={chartMonths} margin={{ top: 8, right: 40, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="month_name" tick={{ fontSize: 12, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
                <YAxis tickFormatter={v => `${v}%`} tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} width={45} />
                <Tooltip content={<PctTooltip />} />
                <Legend wrapperStyle={{ fontSize: 12, paddingTop: 12 }} />
                <ReferenceLine
                  y={WASTE_LIMIT} stroke={COLORS.limit} strokeDasharray="5 3" strokeWidth={1.5}
                  label={{ value: `Лимит ${WASTE_LIMIT}%`, position: "insideTopRight", fontSize: 11, fill: "#9ca3af" }}
                />
                <Line type="monotone" dataKey="shortage_pct" name="Stat Lost %" stroke={COLORS.shortage} strokeWidth={2}
                  dot={(props: any) => props.payload.has_data
                    ? <circle key={props.key} cx={props.cx} cy={props.cy} r={4} fill={COLORS.shortage} stroke="white" strokeWidth={1.5} />
                    : <g key={props.key} />}
                  activeDot={{ r: 6 }} connectNulls={false}
                />
                <Line type="monotone" dataKey="writeoff_pct" name="Complete Waste %" stroke={COLORS.writeoff} strokeWidth={2}
                  dot={(props: any) => props.payload.has_data
                    ? <circle key={props.key} cx={props.cx} cy={props.cy} r={4} fill={COLORS.writeoff} stroke="white" strokeWidth={1.5} />
                    : <g key={props.key} />}
                  activeDot={{ r: 6 }} connectNulls={false}
                />
                <Line type="monotone" dataKey="waste_pct" name="Waste State %" stroke={COLORS.waste} strokeWidth={2.5}
                  dot={(props: any) => props.payload.has_data
                    ? <circle key={props.key} cx={props.cx} cy={props.cy} r={5} fill={COLORS.waste} stroke="white" strokeWidth={1.5} />
                    : <g key={props.key} />}
                  activeDot={{ r: 7 }} connectNulls={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* ── График суммы ── */}
          <div className="card p-5">
            <div className="mb-4">
              <h2 className="font-semibold text-brand-dark">Суммы потерь по месяцам</h2>
              <p className="text-xs text-brand-muted mt-0.5">Stat Lost и Complete Waste в тенге</p>
            </div>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={chartMonths} margin={{ top: 8, right: 20, left: 0, bottom: 0 }} barGap={4}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
                <XAxis dataKey="month_name" tick={{ fontSize: 12, fill: "#9ca3af" }} axisLine={false} tickLine={false} />
                <YAxis
                  tickFormatter={v => v >= 1_000_000 ? `${(v / 1_000_000).toFixed(1)}M` : v >= 1000 ? `${(v / 1000).toFixed(0)}K` : String(v)}
                  tick={{ fontSize: 11, fill: "#9ca3af" }} axisLine={false} tickLine={false} width={50}
                />
                <Tooltip content={<SumTooltip />} />
                <Legend wrapperStyle={{ fontSize: 12, paddingTop: 12 }} />
                <Bar dataKey="shortage_sum" name="Stat Lost" fill={COLORS.shortage} radius={[4, 4, 0, 0]} maxBarSize={36} />
                <Bar dataKey="complete_waste_sum" name="Complete Waste" fill={COLORS.writeoff} radius={[4, 4, 0, 0]} maxBarSize={36} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* ── Таблица по месяцам ── */}
          <MonthTable months={data.months} />

        </>
      )}
    </div>
  )
}
