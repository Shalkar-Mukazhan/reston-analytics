import { useEffect, useRef, useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import api from "../api/client"
import { useAuth } from "../hooks/useAuth"
import {
  TrendingUp, TrendingDown, Store,
  AlertTriangle, CheckCircle2, RefreshCw, Loader2,
  BarChart3, ChevronLeft, ChevronRight,
} from "lucide-react"
import { cn } from "../lib/utils"
import {
  PieChart, Pie, Cell, Tooltip as ReTooltip, ResponsiveContainer,
} from "recharts"

interface SparkPoint { period: string; waste_pct: number }

interface RestaurantMetric {
  restaurant_id: number
  restaurant_name: string
  period: string
  revenue_sum: number
  shortage_sum: number
  complete_waste_sum: number
  shortage_pct: number
  writeoff_pct: number
  waste_pct: number
  to_writeoff_qty: number
  over_limit_count: number
  updated_at: string
  prev_month_waste_pct: number | null
  delta_waste_pct: number | null
  sparkline: SparkPoint[]
}

interface TopProduct {
  product_name: string
  total_to_writeoff: number
  restaurant_count: number
}

interface Summary {
  restaurants_count: number
  restaurants_with_data: number
  total_revenue: number
  total_shortage: number
  total_writeoff: number
  avg_waste_pct: number
  total_to_writeoff_qty: number
  total_over_limit: number
}

interface RecentReport {
  id: number
  restaurant_name: string
  period: string
  status: string
  created_at: string
}

interface DashboardData {
  summary: Summary
  restaurants: RestaurantMetric[]
  top_products: TopProduct[]
  recent_reports: RecentReport[]
  current_month: string
  is_current: boolean
  using_weeks: boolean
  available_weeks: string[]
  selected_week: string | null
}

interface ChannelStat {
  channel: string
  sales_sum: number
  gc: number
  avg_check: number
  pct: number
  mop_gc: number | null
  mop_pct: number | null
  mop_sales: number | null
  mop_avg_check: number | null
}

interface HourStat {
  hour: string
  sales_sum: number
  gc: number
  avg_check: number
}

interface HourlySalesData {
  date: string
  by_channel: ChannelStat[]
  by_hour: HourStat[]
  totals: { sales_sum: number; gc: number; avg_check: number }
}

const WASTE_LIMIT = 0.3

function fmt(n: number, decimals = 2) {
  return n.toLocaleString("ru-RU", { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

function fmtMoney(n: number) {
  if (n >= 1_000_000) return `${fmt(n / 1_000_000, 1)} млн ₸`
  if (n >= 1_000) return `${fmt(n / 1_000, 0)} тыс ₸`
  return `${fmt(n)} ₸`
}

function fmtMoneyFull(n: number) {
  return `${n.toLocaleString("ru-RU", { minimumFractionDigits: 0, maximumFractionDigits: 0 })} ₸`
}

function WasteBadge({ pct }: { pct: number }) {
  const ok = pct <= WASTE_LIMIT
  return (
    <span className={cn(
      "inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold",
      ok ? "bg-green-100 text-green-700" : "bg-red-100 text-brand-red"
    )}>
      {ok ? <CheckCircle2 size={11} /> : <AlertTriangle size={11} />}
      {fmt(pct)}%
    </span>
  )
}

// ── Мини-спарклайн ────────────────────────────────────────────────────────────
function MiniSparkline({ data }: { data: SparkPoint[] }) {
  const vals = data.map(d => d.waste_pct)
  if (!vals.length || vals.every(v => v === 0)) return <span className="text-brand-muted text-xs">—</span>

  const W = 56, H = 22, pad = 2
  const maxV = Math.max(...vals, WASTE_LIMIT) || 1
  const pts = vals.map((v, i) => {
    const x = pad + (i / Math.max(vals.length - 1, 1)) * (W - pad * 2)
    const y = H - pad - (v / maxV) * (H - pad * 2)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(" ")
  const limitY = H - pad - (WASTE_LIMIT / maxV) * (H - pad * 2)
  const hasExcess = vals.some(v => v > WASTE_LIMIT)

  return (
    <svg width={W} height={H} className="overflow-visible">
      <line x1={pad} y1={limitY} x2={W - pad} y2={limitY} stroke="#d1d5db" strokeDasharray="2,2" strokeWidth={1} />
      <polyline points={pts} fill="none"
        stroke={hasExcess ? "#ef4444" : "#22c55e"}
        strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

// ── Дельта месяц к месяцу ─────────────────────────────────────────────────────
function DeltaBadge({ delta }: { delta: number | null }) {
  if (delta === null) return <span className="text-brand-muted text-xs">—</span>
  const up = delta > 0
  return (
    <span className={cn("inline-flex items-center gap-0.5 text-xs font-medium tabular-nums",
      up ? "text-brand-red" : "text-green-600")}>
      {up ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
      {up ? "+" : ""}{fmt(delta)}%
    </span>
  )
}

const CHANNEL_COLORS: Record<string, string> = {
  DLV: "#3b82f6",
  DT: "#f59e0b",
  FC: "#22c55e",
  Cafe: "#10b981",
  Kiosk: "#a855f7",
}
const DEFAULT_COLOR = "#9ca3af"

function todayStr() {
  return new Date().toISOString().split("T")[0]
}

function HourlySalesSection({ restaurantId }: { restaurantId: number }) {
  const [date, setDate] = useState(todayStr())
  const [data, setData] = useState<HourlySalesData | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    api.get(`/dashboard/hourly-sales?restaurant_id=${restaurantId}&date=${date}`)
      .then(r => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [restaurantId, date])

  function shiftDate(days: number) {
    const d = new Date(date)
    d.setDate(d.getDate() + days)
    const s = d.toISOString().split("T")[0]
    if (s <= todayStr()) setDate(s)
  }

  const hasData = data && (data.by_channel.length > 0 || data.by_hour.length > 0)

  return (
    <div className="space-y-4">
      {/* Заголовок + выбор даты */}
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-brand-dark">Продажи за день</h2>
        <div className="flex items-center gap-2">
          <button onClick={() => shiftDate(-1)} className="p-1.5 rounded-lg border border-brand-border hover:bg-brand-bg transition-colors">
            <ChevronLeft size={14} />
          </button>
          <input
            type="date"
            value={date}
            max={todayStr()}
            onChange={e => setDate(e.target.value)}
            className="h-8 px-2 rounded-lg border border-brand-border bg-white text-sm text-brand-dark focus:outline-none focus:ring-2 focus:ring-brand-yellow/40"
          />
          <button
            onClick={() => shiftDate(1)}
            disabled={date >= todayStr()}
            className="p-1.5 rounded-lg border border-brand-border hover:bg-brand-bg transition-colors disabled:opacity-30"
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="card flex items-center justify-center py-16">
          <Loader2 size={24} className="animate-spin text-brand-muted" />
        </div>
      ) : !hasData ? (
        <div className="card flex items-center justify-center py-12 text-brand-muted text-sm">
          Нет данных за выбранную дату
        </div>
      ) : (
        <>
          {/* Итоги */}
          <div className="grid grid-cols-3 gap-3">
            <div className="card p-4 text-center">
              <p className="text-brand-muted text-xs uppercase tracking-wide mb-1">Продажи</p>
              <p className="text-xl font-bold text-brand-dark">{fmtMoneyFull(data!.totals.sales_sum)}</p>
            </div>
            <div className="card p-4 text-center">
              <p className="text-brand-muted text-xs uppercase tracking-wide mb-1">Чеков (GC)</p>
              <p className="text-xl font-bold text-brand-dark">{data!.totals.gc.toLocaleString("ru-RU")}</p>
            </div>
            <div className="card p-4 text-center">
              <p className="text-brand-muted text-xs uppercase tracking-wide mb-1">Ср. чек</p>
              <p className="text-xl font-bold text-brand-dark">{data!.totals.avg_check.toLocaleString("ru-RU")} ₸</p>
            </div>
          </div>

          {/* Pie + таблица */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {/* Pie chart — каналы */}
            <div className="card p-5">
              <h3 className="font-medium text-brand-dark text-sm mb-1">% продаж по каналам</h3>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={data!.by_channel}
                    dataKey="sales_sum"
                    nameKey="channel"
                    cx="50%"
                    cy="50%"
                    innerRadius={52}
                    outerRadius={82}
                    paddingAngle={2}
                    label={false}
                  >
                    {data!.by_channel.map((entry) => (
                      <Cell key={entry.channel} fill={CHANNEL_COLORS[entry.channel] ?? DEFAULT_COLOR} />
                    ))}
                  </Pie>
                  <ReTooltip
                    formatter={(value: number, name: string, props: any) => {
                      const p = props.payload
                      return [
                        <span key="v">
                          {(value / 1000).toFixed(0)} тыс ₸ &nbsp;·&nbsp; {p?.pct}% &nbsp;·&nbsp; ср. чек {(p?.avg_check ?? 0).toLocaleString("ru-RU")} ₸
                        </span>,
                        name,
                      ]
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>

              {/* Таблица каналов */}
              <table className="w-full text-xs mt-1">
                <thead>
                  <tr className="border-b border-brand-border/40">
                    <th className="text-left py-1.5 text-brand-muted font-medium">Канал</th>
                    <th className="text-right py-1.5 text-brand-muted font-medium">Продажи</th>
                    <th className="text-right py-1.5 text-brand-muted font-medium">Чеков</th>
                    <th className="text-right py-1.5 text-brand-muted font-medium">Ср. чек</th>
                    <th className="text-right py-1.5 text-brand-muted font-medium">%</th>
                  </tr>
                </thead>
                <tbody>
                  {data!.by_channel.map(ch => (
                    <>
                      <tr key={ch.channel} className="border-b border-brand-border/20">
                        <td className="py-1.5">
                          <span className="flex items-center gap-1.5">
                            <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: CHANNEL_COLORS[ch.channel] ?? DEFAULT_COLOR }} />
                            <span className="font-medium text-brand-dark">{ch.channel}</span>
                          </span>
                        </td>
                        <td className="py-1.5 text-right tabular-nums text-brand-dark">{fmtMoneyFull(ch.sales_sum)}</td>
                        <td className="py-1.5 text-right tabular-nums text-brand-muted">{ch.gc}</td>
                        <td className="py-1.5 text-right tabular-nums text-brand-muted">{ch.avg_check.toLocaleString("ru-RU")} ₸</td>
                        <td className="py-1.5 text-right tabular-nums font-semibold" style={{ color: CHANNEL_COLORS[ch.channel] ?? DEFAULT_COLOR }}>{ch.pct}%</td>
                      </tr>
                      {ch.channel === "FC" && ch.mop_gc != null && ch.mop_gc > 0 && (
                        <tr key="mop" className="border-b border-brand-border/10 bg-brand-bg/30">
                          <td className="py-1 pl-6 text-xs text-brand-muted">└ MOP (мобильное)</td>
                          <td className="py-1 text-right tabular-nums text-xs text-brand-muted">
                            {ch.mop_sales ? fmtMoneyFull(ch.mop_sales) : "—"}
                          </td>
                          <td className="py-1 text-right tabular-nums text-xs text-brand-muted">{ch.mop_gc}</td>
                          <td className="py-1 text-right tabular-nums text-xs text-brand-muted">
                            {ch.mop_avg_check ? `${ch.mop_avg_check.toLocaleString("ru-RU")} ₸` : "—"}
                          </td>
                          <td className="py-1 text-right tabular-nums text-xs font-semibold text-blue-500">{ch.mop_pct}%</td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Почасовая таблица */}
            <div className="card overflow-hidden">
              <div className="px-5 py-3.5 border-b border-brand-border">
                <h3 className="font-medium text-brand-dark text-sm">Почасовые продажи</h3>
              </div>
              <div className="overflow-y-auto max-h-[360px]">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-white z-10">
                    <tr className="border-b border-brand-border bg-brand-bg/70">
                      <th className="text-left py-2 px-4 text-brand-muted font-medium text-xs uppercase tracking-wide">Час</th>
                      <th className="text-right py-2 px-4 text-brand-muted font-medium text-xs uppercase tracking-wide">Продажи</th>
                      <th className="text-right py-2 px-4 text-brand-muted font-medium text-xs uppercase tracking-wide">Чеков</th>
                      <th className="text-right py-2 px-4 text-brand-muted font-medium text-xs uppercase tracking-wide">Ср. чек</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data!.by_hour.map(h => (
                      <tr key={h.hour} className="border-b border-brand-border/30 hover:bg-brand-bg/50 transition-colors">
                        <td className="py-2 px-4 font-mono font-semibold text-brand-dark">{h.hour}:00</td>
                        <td className="py-2 px-4 text-right tabular-nums text-brand-dark">{fmtMoneyFull(h.sales_sum)}</td>
                        <td className="py-2 px-4 text-right tabular-nums text-brand-muted">{h.gc}</td>
                        <td className="py-2 px-4 text-right tabular-nums text-brand-muted">{h.avg_check.toLocaleString("ru-RU")} ₸</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="sticky bottom-0 bg-white border-t-2 border-brand-border">
                    <tr>
                      <td className="py-2 px-4 font-semibold text-brand-dark text-xs">Итого</td>
                      <td className="py-2 px-4 text-right tabular-nums font-semibold text-brand-dark">{fmtMoneyFull(data!.totals.sales_sum)}</td>
                      <td className="py-2 px-4 text-right tabular-nums font-semibold text-brand-dark">{data!.totals.gc}</td>
                      <td className="py-2 px-4 text-right tabular-nums font-semibold text-brand-dark">{data!.totals.avg_check.toLocaleString("ru-RU")} ₸</td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// ── Вид для store — один ресторан крупно ──────────────────────────────────────
function StoreDashboard({ m, reports: _reports, refreshing }: { m: RestaurantMetric; reports: RecentReport[]; refreshing: boolean }) {
  const ok = m.waste_pct <= WASTE_LIMIT

  return (
    <div className="space-y-6">
      {/* Название */}
      <div className={cn(
        "rounded-2xl p-6 text-white",
        ok ? "bg-gradient-to-r from-green-500 to-green-600" : "bg-gradient-to-r from-red-500 to-red-600"
      )}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-white/70 text-sm mb-1">{m.restaurant_name}</p>
            <p className="text-4xl font-bold">{fmt(m.waste_pct)}%</p>
            <p className="text-white/80 text-sm mt-1 flex items-center gap-2">
              Waste State • период {m.period}
              {refreshing && <span className="inline-flex items-center gap-1 text-white/60 text-xs"><Loader2 size={11} className="animate-spin" /> обновляем...</span>}
            </p>
          </div>
          <div className="text-right">
            {ok
              ? <><CheckCircle2 size={48} className="text-white/80 ml-auto mb-1" /><p className="text-white/80 text-sm">В норме ≤{WASTE_LIMIT}%</p></>
              : <><AlertTriangle size={48} className="text-white/80 ml-auto mb-1" /><p className="text-white/80 text-sm">Превышение!</p></>
            }
          </div>
        </div>
      </div>

      {/* 3 метрики */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="card p-5">
          <p className="text-brand-muted text-xs uppercase tracking-wide mb-2">% Недостачи</p>
          <p className={cn("text-3xl font-bold", m.shortage_pct > 0 ? "text-brand-red" : "text-brand-dark")}>
            {fmt(m.shortage_pct)}%
          </p>
          <p className="text-brand-muted text-xs mt-1">{fmtMoney(m.shortage_sum)}</p>
        </div>
        <div className="card p-5">
          <p className="text-brand-muted text-xs uppercase tracking-wide mb-2">Complete Waste %</p>
          <p className="text-3xl font-bold text-brand-dark">{fmt(m.writeoff_pct)}%</p>
          <p className="text-brand-muted text-xs mt-1">{fmtMoney(m.complete_waste_sum)}</p>
        </div>
        <div className="card p-5">
          <p className="text-brand-muted text-xs uppercase tracking-wide mb-2">Выручка (без НДС)</p>
          <p className="text-3xl font-bold text-brand-dark">{fmtMoney(m.revenue_sum)}</p>
          <p className="text-brand-muted text-xs mt-1">реализация</p>
        </div>
      </div>

      {/* Почасовые продажи */}
      <HourlySalesSection restaurantId={m.restaurant_id} />

    </div>
  )
}

// ── Вид для co/admin — все рестораны ─────────────────────────────────────────
function AdminDashboard({ data, onRefreshRestaurant, onRefreshAll, refreshingId, refreshingAll }: {
  data: DashboardData
  onRefreshRestaurant: (restaurantId: number) => void
  onRefreshAll: () => void
  refreshingId: number | null
  refreshingAll: boolean
})
 {
  const s = data.summary

  return (
    <div className="space-y-6">
      {/* KPI карточки */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <div className="card p-5">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-brand-muted text-xs uppercase tracking-wide mb-1">Ресторанов</p>
              <p className="text-3xl font-bold text-brand-dark">{s.restaurants_count}</p>
              <p className="text-brand-muted text-xs mt-1">с данными: {s.restaurants_with_data}</p>
            </div>
            <div className="p-2.5 rounded-xl bg-brand-yellow/10">
              <Store size={20} className="text-brand-yellow" />
            </div>
          </div>
        </div>

        <div className="card p-5">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-brand-muted text-xs uppercase tracking-wide mb-1">Выручка без НДС (итого)</p>
              <p className="text-2xl font-bold text-brand-dark">{fmtMoney(s.total_revenue)}</p>
              <p className="text-brand-muted text-xs mt-1">по последним отчётам</p>
            </div>
            <div className="p-2.5 rounded-xl bg-blue-50">
              <BarChart3 size={20} className="text-blue-500" />
            </div>
          </div>
        </div>

        <div className="card p-5">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-brand-muted text-xs uppercase tracking-wide mb-1">Средний Waste %</p>
              <p className={cn("text-3xl font-bold", s.avg_waste_pct > WASTE_LIMIT ? "text-brand-red" : "text-green-600")}>
                {fmt(s.avg_waste_pct)}%
              </p>
              <p className="text-brand-muted text-xs mt-1 flex items-center gap-1">
                {s.avg_waste_pct > WASTE_LIMIT
                  ? <><TrendingUp size={11} className="text-brand-red" /> Лимит {WASTE_LIMIT}%</>
                  : <><CheckCircle2 size={11} className="text-green-500" /> В норме</>
                }
              </p>
            </div>
            <div className={cn("p-2.5 rounded-xl", s.avg_waste_pct > WASTE_LIMIT ? "bg-red-50" : "bg-green-50")}>
              {s.avg_waste_pct > WASTE_LIMIT
                ? <TrendingUp size={20} className="text-brand-red" />
                : <TrendingDown size={20} className="text-green-500" />
              }
            </div>
          </div>
        </div>

        <div className="card p-5">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-brand-muted text-xs uppercase tracking-wide mb-1">Сверх нормы</p>
              <p className="text-3xl font-bold text-brand-red">{s.total_over_limit}</p>
              <p className="text-brand-muted text-xs mt-1">позиций по всем ресторанам</p>
            </div>
            <div className="p-2.5 rounded-xl bg-red-50">
              <AlertTriangle size={20} className="text-brand-red" />
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Таблица ресторанов */}
        <div className="card xl:col-span-2">
          <div className="px-5 py-4 border-b border-brand-border flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-brand-dark flex items-center gap-2">
                <Store size={16} className="text-brand-yellow" />
                Метрики по ресторанам
                {refreshingAll && <span className="inline-flex items-center gap-1 text-brand-muted text-xs font-normal"><Loader2 size={11} className="animate-spin" />обновляем...</span>}
              </h2>
              <p className="text-xs text-brand-muted mt-0.5">Данные из IIKO · сортировка по Waste %</p>
            </div>
            <button
              className="btn-secondary text-xs py-1.5 px-3"
              onClick={onRefreshAll}
              disabled={refreshingAll}
            >
              {refreshingAll ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
              Обновить все
            </button>
          </div>

          {data.restaurants.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-brand-muted">
              <BarChart3 size={36} className="text-brand-border mb-3" />
              <p className="text-sm">Нет данных</p>
              <p className="text-xs mt-1">Сгенерируйте отчёты в разделе «Отчёты»</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-brand-border">
                    {["Ресторан", "Waste %", "vs пред. мес.", "Тренд", "Сверх нормы", "К спис.", ""].map(h => (
                      <th key={h} className="text-left py-2.5 px-4 text-brand-muted font-medium text-xs uppercase tracking-wide whitespace-nowrap">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.restaurants.map((r) => (
                    <tr key={r.restaurant_id} className={cn(
                      "border-b border-brand-border/50 hover:bg-brand-bg/60 transition-colors",
                      r.waste_pct > WASTE_LIMIT && "bg-red-50/40"
                    )}>
                      <td className="py-3 px-4">
                        <p className="font-medium text-brand-dark max-w-[140px] truncate">{r.restaurant_name}</p>
                        <p className="text-brand-muted text-xs font-mono mt-0.5">{r.period}</p>
                      </td>
                      <td className="py-3 px-4"><WasteBadge pct={r.waste_pct} /></td>
                      <td className="py-3 px-4"><DeltaBadge delta={r.delta_waste_pct ?? null} /></td>
                      <td className="py-3 px-4"><MiniSparkline data={r.sparkline ?? []} /></td>
                      <td className="py-3 px-4 tabular-nums text-xs font-medium">
                        {r.over_limit_count > 0
                          ? <span className="text-brand-red">{r.over_limit_count}</span>
                          : <span className="text-brand-muted">—</span>
                        }
                      </td>
                      <td className="py-3 px-4 tabular-nums text-xs">
                        {r.to_writeoff_qty > 0
                          ? <span className="text-brand-yellow font-semibold">{Math.round(r.to_writeoff_qty)}</span>
                          : <span className="text-brand-muted">—</span>
                        }
                      </td>
                      <td className="py-3 px-4">
                        <button
                          className="btn-secondary text-xs py-1 px-2"
                          onClick={() => onRefreshRestaurant(r.restaurant_id)}
                          disabled={refreshingId === r.restaurant_id}
                          title="Обновить метрики из IIKO"
                        >
                          {refreshingId === r.restaurant_id
                            ? <Loader2 size={11} className="animate-spin" />
                            : <RefreshCw size={11} />}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Топ проблемных продуктов */}
        <div className="card">
          <div className="px-5 py-4 border-b border-brand-border">
            <h2 className="font-semibold text-brand-dark flex items-center gap-2">
              <AlertTriangle size={16} className="text-brand-red" />
              Топ проблемных позиций
            </h2>
            <p className="text-xs text-brand-muted mt-0.5">Сверх нормы · к списанию за период</p>
          </div>
          {!data.top_products?.length ? (
            <div className="flex flex-col items-center justify-center py-12 text-brand-muted">
              <CheckCircle2 size={28} className="text-green-400 mb-2" />
              <p className="text-sm">Нет превышений</p>
            </div>
          ) : (
            <div className="divide-y divide-brand-border/40">
              {data.top_products.map((p, i) => (
                <div key={p.product_name} className="flex items-center justify-between px-5 py-3 hover:bg-brand-bg/60 transition-colors">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-brand-muted text-xs font-mono w-4 flex-shrink-0">{i + 1}</span>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-brand-dark truncate max-w-[160px]">{p.product_name}</p>
                      <p className="text-xs text-brand-muted">{p.restaurant_count} рест.</p>
                    </div>
                  </div>
                  <span className="text-sm font-bold text-brand-red flex-shrink-0 ml-2">
                    {Math.round(p.total_to_writeoff)} шт
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>
    </div>
  )
}

function monthLabel(ym: string) {
  const [y, m] = ym.split("-")
  const names = ["Январь","Февраль","Март","Апрель","Май","Июнь",
                  "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"]
  return `${names[parseInt(m) - 1]} ${y}`
}

function prevMonth(ym: string) {
  const [y, m] = ym.split("-").map(Number)
  const d = new Date(y, m - 2, 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`
}

function nextMonth(ym: string) {
  const [y, m] = ym.split("-").map(Number)
  const d = new Date(y, m, 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`
}

function currentYM() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`
}

function weekLabel(w: string) {
  // "2026-03-W2" → "Неделя 2"
  const match = w.match(/-W(\d+)$/)
  return match ? `Неделя ${match[1]}` : w
}

// ── Главная страница ───────────────────────────────────────────────────────────
export default function DashboardPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [month, setMonth] = useState(currentYM)
  const [selectedWeek, setSelectedWeek] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [refreshingId, setRefreshingId] = useState<number | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const { data, isLoading: loading, refetch } = useQuery<DashboardData>({
    queryKey: ["dashboard", month, selectedWeek],
    queryFn: async () => {
      const params = new URLSearchParams({ month })
      if (selectedWeek) params.set("week", selectedWeek)
      const res = await api.get(`/dashboard/?${params}`)
      return res.data
    },
    staleTime: 2 * 60 * 1000,
  })

  // Синхронизируем selectedWeek если сервер вернул другой
  const prevWeekFromApi = useRef<string | null | undefined>(undefined)
  useEffect(() => {
    if (data?.selected_week !== undefined && data.selected_week !== prevWeekFromApi.current) {
      prevWeekFromApi.current = data.selected_week ?? null
      setSelectedWeek(data.selected_week ?? null)
    }
  }, [data?.selected_week])

  const stopPolling = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }

  // Polling: каждые 3 сек, макс 5 попыток (~15 сек), потом останавливается
  const startPolling = (_ym: string, _wk?: string | null, prevCount = 0) => {
    stopPolling()
    let attempts = 0
    const maxAttempts = 5
    pollRef.current = setInterval(async () => {
      const result = await refetch()
      const newCount = result.data?.restaurants?.length ?? 0
      attempts++
      if (newCount > prevCount || attempts >= maxAttempts) {
        stopPolling()
        setRefreshing(false)
        setRefreshingId(null)
      }
    }, 3000)
  }

  // Обновить метрики одного ресторана
  const refreshOne = async (restaurantId: number, period: string) => {
    setRefreshingId(restaurantId)
    setRefreshing(true)
    try {
      await api.post("/dashboard/refresh-metrics", { restaurant_id: restaurantId, period })
      startPolling(period.slice(0, 7))
    } catch {
      setRefreshing(false)
      setRefreshingId(null)
    }
  }

  // Обновить метрики всех ресторанов (CO/admin) — или одного (store)
  const refreshAll = async (ym: string, restaurantId?: number) => {
    setRefreshing(true)
    const currentCount = data?.restaurants?.length ?? 0
    try {
      if (restaurantId) {
        await api.post("/dashboard/refresh-metrics", { restaurant_id: restaurantId, period: ym })
      } else {
        await api.post(`/dashboard/refresh-metrics-all?period=${ym}`)
      }
      startPolling(ym, selectedWeek, currentCount)
    } catch {
      setRefreshing(false)
    }
  }

  useEffect(() => {
    return () => stopPolling()
  }, [month])

  const isStore = user?.role === "store"
  const isCurrent = month === currentYM()
  const myMetric = isStore && data ? data.restaurants[0] : null
  // restaurant_id для store берём из профиля пользователя (не из метрик — там может не быть данных)
  const storeRestaurantId = isStore ? user?.restaurants?.[0]?.id : undefined

  // Авто-запуск при смене месяца или первой загрузке
  // refreshedForMonth гарантирует один запуск на месяц (не зацикливается)
  const refreshedForMonth = useRef<string | null>(null)
  useEffect(() => {
    if (!data || refreshedForMonth.current === month) return
    if (isStore && !storeRestaurantId) return
    refreshedForMonth.current = month
    if (isStore) {
      refreshAll(month, storeRestaurantId)
    } else {
      refreshAll(month)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, month])

  const handleWeekSelect = (wk: string) => {
    setSelectedWeek(wk)
  }

  const handleMonthChange = (ym: string) => {
    setMonth(ym)
    setSelectedWeek(null)
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-brand-dark">
            {isStore ? myMetric?.restaurant_name ?? "Дашборд" : "Дашборд"}
          </h1>
          <p className="text-brand-muted mt-1 text-sm">
            {new Date().toLocaleDateString("ru-RU", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Переключатель месяца */}
          <div className="flex items-center gap-1 bg-white border border-brand-border rounded-lg px-1 py-1">
            <button
              className="p-1.5 rounded hover:bg-brand-bg transition-colors text-brand-muted"
              onClick={() => handleMonthChange(prevMonth(month))}
            >
              <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M15 18l-6-6 6-6"/></svg>
            </button>
            <span className="text-sm font-medium text-brand-dark px-2 min-w-[110px] text-center">
              {monthLabel(month)}
              {isCurrent && <span className="ml-1 text-xs text-brand-yellow font-normal">(тек.)</span>}
            </span>
            <button
              className="p-1.5 rounded hover:bg-brand-bg transition-colors text-brand-muted disabled:opacity-30"
              onClick={() => handleMonthChange(nextMonth(month))}
              disabled={isCurrent}
            >
              <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M9 18l6-6-6-6"/></svg>
            </button>
          </div>
          <button
            className="btn-secondary text-xs py-1.5 px-3"
            onClick={() => isStore ? refreshAll(month, storeRestaurantId) : refreshAll(month)}
            disabled={loading || refreshing}
          >
            <RefreshCw size={13} className={(loading || refreshing) ? "animate-spin" : ""} />
            {refreshing ? "Загружаем..." : "Обновить"}
          </button>
        </div>
      </div>

      {/* Переключатель недель — только для текущего месяца без месячного отчёта */}
      {data?.using_weeks && data.available_weeks.length > 0 && (
        <div className="flex items-center gap-2 mb-5">
          <span className="text-xs text-brand-muted">Неделя:</span>
          <div className="flex gap-1">
            {data.available_weeks.map(wk => (
              <button
                key={wk}
                onClick={() => handleWeekSelect(wk)}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors",
                  data.selected_week === wk
                    ? "bg-brand-yellow text-white border-brand-yellow"
                    : "bg-white text-brand-muted border-brand-border hover:border-brand-yellow hover:text-brand-dark"
                )}
              >
                {weekLabel(wk)}
              </button>
            ))}
          </div>
          <span className="text-xs text-brand-muted ml-2">
            (месячный отчёт ещё не создан)
          </span>
        </div>
      )}

      {loading && !data ? (
        <div className="flex items-center justify-center py-32">
          <Loader2 size={28} className="animate-spin text-brand-muted" />
        </div>
      ) : !data ? null : isStore ? (
        myMetric
          ? <StoreDashboard m={myMetric} reports={data.recent_reports} refreshing={refreshing} />
          : (
            <div className="flex flex-col items-center justify-center py-32 text-brand-muted">
              <BarChart3 size={48} className="text-brand-border mb-4" />
              <p className="text-lg font-medium">Нет данных за {monthLabel(month)}</p>
              <p className="text-sm mt-1">
                {isCurrent
                  ? "Сгенерируйте недельный или месячный отчёт в разделе «Отчёты»"
                  : "Нет месячного отчёта за этот период"
                }
              </p>
            </div>
          )
      ) : (
        <AdminDashboard
          data={data}
          onRefreshRestaurant={(id) => refreshOne(id, month)}
          onRefreshAll={() => refreshAll(month)}
          refreshingId={refreshingId}
          refreshingAll={refreshing}
        />
      )}
    </div>
  )
}
