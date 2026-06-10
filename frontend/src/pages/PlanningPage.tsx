import { useEffect, useRef, useState } from "react"
import {
  Target, TrendingUp, RefreshCw, Loader2,
  CheckCircle2, AlertTriangle,
} from "lucide-react"
import api from "../api/client"
import { useAuth } from "../hooks/useAuth"
import { cn } from "../lib/utils"

interface DayRow {
  date: string
  weekday: string
  is_today: boolean
  is_future: boolean
  is_holiday: boolean
  is_manual: boolean
  gc_plan: number | null
  sales_plan: number | null
  av_check_plan: number | null
  gc_fact: number | null
  sales_fact: number | null
  av_check_fact: number | null
  pct_done: number | null
}

interface PlanningData {
  month: string
  restaurant_name: string
  target: { gc_target: number | null; sales_target: number | null }
  fact_totals: { sales_sum: number; gc_sum: number; av_check: number }
  plan_totals: { sales_sum: number }
  pct_of_target: number | null
  days: DayRow[]
  has_facts: boolean
  has_plans: boolean
}

interface Restaurant { id: number; name: string; code: string }

const MONTHS_RU = [
  "Январь","Февраль","Март","Апрель","Май","Июнь",
  "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь",
]
const MONTHS_RU_GENITIVE = [
  "января","февраля","марта","апреля","мая","июня",
  "июля","августа","сентября","октября","ноября","декабря",
]

function monthLabel(ym: string) {
  const [y, m] = ym.split("-").map(Number)
  return `${MONTHS_RU[m - 1]} ${y}`
}

function fmt(n: number, d = 0) {
  return n.toLocaleString("ru-RU", { minimumFractionDigits: d, maximumFractionDigits: d })
}
// Полная сумма: 4 556 588 ₸
function fmtFull(n: number) {
  return fmt(Math.round(n)) + " ₸"
}
// Краткая только для итоговых карточек: 4.6 млн ₸
function fmtMoney(n: number) {
  if (n >= 1_000_000) return `${fmt(n / 1_000_000, 1)} млн ₸`
  if (n >= 1_000) return `${fmt(n / 1_000, 1)} тыс ₸`
  return `${fmt(n)} ₸`
}
function currentMonth() { return new Date().toISOString().slice(0, 7) }
function todayStr() { return new Date().toISOString().slice(0, 10) }

// Генерируем список месяцев: 3 назад, текущий, 3 вперёд
function buildMonthsList(): string[] {
  const result: string[] = []
  const now = new Date()
  for (let i = -3; i <= 3; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() + i, 1)
    result.push(d.toISOString().slice(0, 7))
  }
  return result.sort((a, b) => b.localeCompare(a)) // новые сверху
}

// ── Редактируемая ячейка ──────────────────────────────────────────────────────
function EditableCell({
  value, onSave, disabled, isManual = false, isInt = false, fullFormat = false,
}: {
  value: number | null
  onSave: (v: number) => Promise<void>
  disabled?: boolean
  isManual?: boolean
  isInt?: boolean
  fullFormat?: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [input, setInput] = useState("")
  const [saving, setSaving] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  function start() {
    if (disabled) return
    setInput(value != null ? String(Math.round(value)) : "")
    setEditing(true)
    setTimeout(() => inputRef.current?.select(), 30)
  }

  async function commit() {
    const raw = input.replace(/\s/g, "").replace(",", ".")
    const n = isInt ? parseInt(raw, 10) : parseFloat(raw)
    if (!isNaN(n) && n > 0 && n !== value) {
      setSaving(true)
      try { await onSave(n) } finally { setSaving(false) }
    }
    setEditing(false)
  }

  function onKey(e: React.KeyboardEvent) {
    if (e.key === "Enter") commit()
    if (e.key === "Escape") setEditing(false)
  }

  if (editing) {
    return (
      <input
        ref={inputRef}
        value={input}
        onChange={e => setInput(e.target.value)}
        onBlur={commit}
        onKeyDown={onKey}
        style={{ width: "120px" }}
        className="h-6 px-1.5 rounded border border-brand-yellow bg-brand-yellow/5 text-xs text-brand-dark tabular-nums focus:outline-none"
        autoFocus
      />
    )
  }

  const displayVal = value != null
    ? isInt ? fmt(value) : fullFormat ? fmtFull(value) : fmtMoney(value)
    : null

  return (
    <button
      onClick={start}
      disabled={disabled}
      className={cn(
        "text-left tabular-nums text-xs whitespace-nowrap",
        !disabled && "hover:text-brand-yellow cursor-pointer transition-colors",
        disabled && "cursor-default",
        saving && "opacity-50",
      )}
      title={disabled ? undefined : "Нажмите для редактирования"}
    >
      {saving ? (
        <Loader2 size={12} className="animate-spin inline" />
      ) : displayVal != null ? (
        <span className="flex items-center gap-1">
          {displayVal}
          {isManual && <span className="text-[10px] text-brand-yellow font-bold">✎</span>}
        </span>
      ) : (
        <span className="text-brand-muted">—</span>
      )}
    </button>
  )
}

// ── Главная страница ──────────────────────────────────────────────────────────
export default function PlanningPage() {
  const { user } = useAuth()
  const isCoOrAdmin = user?.role === "co" || user?.role === "admin"

  const [restaurants, setRestaurants] = useState<Restaurant[]>([])
  const [restaurantId, setRestaurantId] = useState<number | null>(null)
  const [month, setMonth] = useState(currentMonth())
  const [data, setData] = useState<PlanningData | null>(null)
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null)

  const months = buildMonthsList()

  useEffect(() => {
    if (isCoOrAdmin) {
      api.get("/analytics/restaurants").then(r => {
        setRestaurants(r.data)
        if (r.data.length > 0 && !restaurantId) setRestaurantId(r.data[0].id)
      })
    } else {
      const myRest = (user as any)?.restaurants?.[0]
      if (myRest) setRestaurantId(myRest.id)
    }
  }, [isCoOrAdmin])

  const load = async () => {
    if (!restaurantId) return
    setLoading(true)
    try {
      const { data: d } = await api.get(`/planning/?restaurant_id=${restaurantId}&month=${month}`)
      setData(d)
    } catch { setData(null) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [restaurantId, month])

  async function syncHistory() {
    if (!restaurantId) return
    setSyncing(true); setMsg(null)
    try {
      const { data: d } = await api.post(`/planning/sync-history?restaurant_id=${restaurantId}&months=3`)
      setMsg({ type: "ok", text: `Загружено ${d.facts_saved} дней · сгенерировано ${d.plans_generated} планов` })
      await load()
    } catch (e: any) {
      setMsg({ type: "err", text: e.response?.data?.detail || "Ошибка синхронизации" })
    } finally { setSyncing(false) }
  }

  async function regeneratePlans() {
    if (!restaurantId) return
    setSyncing(true); setMsg(null)
    try {
      const { data: d } = await api.post(`/planning/generate-plans?restaurant_id=${restaurantId}`)
      setMsg({ type: "ok", text: `Сгенерировано ${d.plans_generated} планов` })
      await load()
    } catch {
      setMsg({ type: "err", text: "Ошибка генерации" })
    } finally { setSyncing(false) }
  }

  // Сохранение одного дня — авто-пересчёт ср. чека
  async function saveDailyPlan(date: string, field: "sales_plan" | "gc_plan", value: number) {
    await api.put("/planning/daily-plan", {
      restaurant_id: restaurantId,
      date,
      [field]: value,
    })
    setData(prev => {
      if (!prev) return prev
      return {
        ...prev,
        days: prev.days.map(d => {
          if (d.date !== date) return d
          const updated = { ...d, [field]: value, is_manual: true }
          // Авто-пересчёт ср. чека плана
          if (updated.sales_plan && updated.gc_plan && updated.gc_plan > 0) {
            updated.av_check_plan = Math.round(updated.sales_plan / updated.gc_plan)
          }
          // Авто-пересчёт % выполнения
          if (updated.sales_plan && updated.sales_fact) {
            updated.pct_done = Math.round(updated.sales_fact / updated.sales_plan * 1000) / 10
          }
          return updated
        }),
      }
    })
  }

  const today = todayStr()
  const isFutureMonth = month > currentMonth()

  // Swipe left/right для смены месяца
  const touchStartX = useRef<number>(0)
  const handleTouchStart = (e: React.TouchEvent) => { touchStartX.current = e.touches[0].clientX }
  const handleTouchEnd = (e: React.TouchEvent) => {
    const diff = touchStartX.current - e.changedTouches[0].clientX
    if (Math.abs(diff) < 60) return
    const allMonths = buildMonthsList() // sorted newest first
    const idx = allMonths.indexOf(month)
    if (diff > 0 && idx > 0) setMonth(allMonths[idx - 1])      // swipe left = newer month
    else if (diff < 0 && idx < allMonths.length - 1) setMonth(allMonths[idx + 1]) // swipe right = older
  }

  return (
    <div className="p-4 sm:p-6 max-w-6xl mx-auto space-y-6"
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
    >

      {/* Заголовок */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-brand-dark">Планирование продаж</h1>
          <p className="text-brand-muted mt-0.5 text-xs sm:text-sm">
            Авто-план · взвешенное среднее 8 последних таких же дней
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {isCoOrAdmin && restaurants.length > 0 && (
            <select
              value={restaurantId ?? ""}
              onChange={e => setRestaurantId(Number(e.target.value))}
              className="h-9 px-3 rounded-lg border border-brand-border bg-white text-sm text-brand-dark focus:outline-none focus:ring-2 focus:ring-brand-yellow/40 flex-1 sm:flex-none"
            >
              {restaurants.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
          )}
          <select
            value={month}
            onChange={e => setMonth(e.target.value)}
            className="h-9 px-3 rounded-lg border border-brand-border bg-white text-sm text-brand-dark focus:outline-none focus:ring-2 focus:ring-brand-yellow/40"
          >
            {months.map(m => {
              const [y, mo] = m.split("-").map(Number)
              const isFuture = m > currentMonth()
              const isCurrent = m === currentMonth()
              return (
                <option key={m} value={m}>
                  {MONTHS_RU[mo - 1]} {y}{isFuture ? " ◆" : isCurrent ? " ●" : ""}
                </option>
              )
            })}
          </select>
          <button
            onClick={syncHistory}
            disabled={syncing}
            className="h-9 px-3 rounded-lg border border-brand-border bg-white text-sm flex items-center gap-2 hover:border-brand-yellow transition-colors disabled:opacity-50"
            title="Загрузить историю из IIKO (последние 3 месяца) и сгенерировать планы"
          >
            {syncing ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} className="text-brand-yellow" />}
            <span className="hidden sm:inline">Синхронизировать </span>IIKO
          </button>
          <button
            onClick={regeneratePlans}
            disabled={syncing}
            className="h-9 px-3 rounded-lg border border-brand-border bg-white text-sm flex items-center gap-2 hover:border-brand-yellow transition-colors disabled:opacity-50"
          >
            <Target size={14} className="text-brand-yellow" />
            <span className="hidden sm:inline">Пересчитать </span>Планы
          </button>
        </div>
      </div>

      {msg && (
        <div className={cn("flex items-center gap-2 p-3 rounded-lg text-sm",
          msg.type === "ok"
            ? "bg-green-50 border border-green-100 text-green-700"
            : "bg-red-50 border border-red-100 text-red-700"
        )}>
          {msg.type === "ok" ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}
          {msg.text}
        </div>
      )}

      {/* Подсказка для будущих месяцев */}
      {isFutureMonth && (
        <div className="flex items-start gap-3 p-4 rounded-xl bg-blue-50 border border-blue-100 text-sm text-blue-700">
          <Target size={16} className="flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium">Планирование на будущий месяц</p>
            <p className="text-xs mt-0.5 text-blue-600">
              Авто-планы сгенерированы на основе истории. Вы можете скорректировать любой день вручную — нажмите на ячейку.
            </p>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-40">
          <Loader2 size={28} className="animate-spin text-brand-muted" />
        </div>
      ) : !data ? null : (
        <>
          {/* Карточки сверху */}
          <div className="grid grid-cols-2 sm:grid-cols-2 gap-3 sm:gap-4">
            <div className="card p-3 sm:p-5">
              <div className="flex items-center gap-2 mb-2 sm:mb-3">
                <TrendingUp size={15} className="text-green-500 flex-shrink-0" />
                <h2 className="font-semibold text-brand-dark text-xs sm:text-sm leading-tight">Факт {monthLabel(month)}</h2>
              </div>
              <p className="text-lg sm:text-3xl font-bold text-brand-dark tabular-nums">{fmtMoney(data.fact_totals.sales_sum)}</p>
              <div className="flex gap-4 sm:gap-6 mt-1.5 sm:mt-2">
                <div>
                  <p className="text-brand-muted text-[10px] sm:text-xs">Чеков</p>
                  <p className="font-semibold text-brand-dark text-xs sm:text-sm">{fmt(data.fact_totals.gc_sum)}</p>
                </div>
                <div>
                  <p className="text-brand-muted text-[10px] sm:text-xs">Ср. чек</p>
                  <p className="font-semibold text-brand-dark text-xs sm:text-sm">{fmtMoney(data.fact_totals.av_check)}</p>
                </div>
              </div>
            </div>

            <div className="card p-3 sm:p-5">
              <div className="flex items-center gap-2 mb-2 sm:mb-3">
                <Target size={15} className="text-blue-500 flex-shrink-0" />
                <h2 className="font-semibold text-brand-dark text-xs sm:text-sm leading-tight">Авто-план {monthLabel(month)}</h2>
              </div>
              {data.has_plans ? (
                <>
                  <p className="text-lg sm:text-3xl font-bold text-brand-dark tabular-nums">{fmtMoney(data.plan_totals.sales_sum)}</p>
                  <p className="text-brand-muted text-[10px] sm:text-xs mt-1.5 sm:mt-2">Сумма по дням</p>
                </>
              ) : (
                <div className="text-brand-muted text-xs sm:text-sm pt-2">
                  <p>Нет данных.</p>
                  <p className="text-[10px] sm:text-xs mt-1">Синхронизируйте IIKO.</p>
                </div>
              )}
            </div>
          </div>

          {/* Таблица по дням */}
          <div className="card overflow-hidden">
            <div className="px-4 sm:px-5 py-4 border-b border-brand-border flex items-center justify-between">
              <h2 className="font-semibold text-brand-dark">{monthLabel(month)}</h2>
              <p className="text-xs text-brand-muted hidden sm:block">Нажмите на ячейку плана чтобы изменить</p>
              <p className="text-xs text-brand-muted sm:hidden">Нажмите на план для изменения</p>
            </div>

            {/* Desktop: таблица */}
            <div className="hidden sm:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-brand-border bg-brand-bg/50">
                    <th className="text-left py-2.5 px-3 text-brand-muted font-medium text-xs uppercase tracking-wide">Дата</th>
                    <th className="text-left py-2.5 px-3 text-brand-muted font-medium text-xs uppercase tracking-wide">День</th>
                    <th className="text-left py-2.5 px-3 text-brand-muted font-medium text-xs uppercase tracking-wide whitespace-nowrap">План продажи</th>
                    <th className="text-left py-2.5 px-3 text-brand-muted font-medium text-xs uppercase tracking-wide whitespace-nowrap">Факт продажи</th>
                    <th className="text-left py-2.5 px-3 text-brand-muted font-medium text-xs uppercase tracking-wide">% Вып.</th>
                    <th className="text-left py-2.5 px-3 text-brand-muted font-medium text-xs uppercase tracking-wide">План GC</th>
                    <th className="text-left py-2.5 px-3 text-brand-muted font-medium text-xs uppercase tracking-wide">Факт GC</th>
                    <th className="text-left py-2.5 px-3 text-brand-muted font-medium text-xs uppercase tracking-wide whitespace-nowrap">Ср. чек план</th>
                    <th className="text-left py-2.5 px-3 text-brand-muted font-medium text-xs uppercase tracking-wide whitespace-nowrap">Ср. чек факт</th>
                  </tr>
                </thead>
                <tbody>
                  {data.days.map(d => {
                    const canEdit = d.date >= today
                    const avCheckPlan = d.av_check_plan ??
                      (d.sales_plan && d.gc_plan && d.gc_plan > 0
                        ? Math.round(d.sales_plan / d.gc_plan)
                        : null)
                    return (
                      <tr
                        key={d.date}
                        className={cn(
                          "border-b border-brand-border/30 transition-colors",
                          d.is_today ? "bg-brand-yellow/10" :
                          d.is_holiday ? "opacity-50" :
                          d.is_future ? "opacity-60" :
                          "hover:bg-brand-bg/50"
                        )}
                      >
                        <td className="py-2 px-3 text-brand-dark tabular-nums text-xs whitespace-nowrap">
                          {(() => {
                            const [, , dd] = d.date.split("-").map(Number)
                            const mo = parseInt(d.date.split("-")[1]) - 1
                            return `${dd} ${MONTHS_RU_GENITIVE[mo]}`
                          })()}
                          {d.is_today && <span className="ml-1.5 inline-block px-1.5 py-0.5 rounded bg-brand-yellow text-brand-dark text-[10px] font-bold leading-none">сегодня</span>}
                        </td>
                        <td className="py-2 px-3 text-brand-muted text-xs">{d.weekday}</td>
                        <td className="py-1.5 px-3 text-blue-600 w-[140px]">
                          <EditableCell value={d.sales_plan} disabled={!canEdit} isManual={d.is_manual} fullFormat onSave={v => saveDailyPlan(d.date, "sales_plan", v)} />
                        </td>
                        <td className="py-2 px-3 tabular-nums text-xs font-medium text-brand-dark">
                          {d.sales_fact != null ? fmtFull(d.sales_fact) : "—"}
                        </td>
                        <td className="py-2 px-3">
                          {d.pct_done != null ? (
                            <span className={cn(
                              "inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-xs font-semibold",
                              d.pct_done >= 100 ? "bg-green-100 text-green-700" : "bg-red-100 text-brand-red"
                            )}>
                              {d.pct_done >= 100 ? <CheckCircle2 size={10} /> : <AlertTriangle size={10} />}
                              {fmt(d.pct_done, 1)}%
                            </span>
                          ) : "—"}
                        </td>
                        <td className="py-1.5 px-3 text-blue-600 w-[80px]">
                          <EditableCell value={d.gc_plan} disabled={!canEdit} isManual={d.is_manual} isInt onSave={v => saveDailyPlan(d.date, "gc_plan", Math.round(v))} />
                        </td>
                        <td className="py-2 px-3 tabular-nums text-xs text-brand-dark">
                          {d.gc_fact != null ? fmt(d.gc_fact) : "—"}
                        </td>
                        <td className="py-2 px-3 tabular-nums text-xs text-blue-500">
                          {avCheckPlan != null ? fmtFull(avCheckPlan) : "—"}
                        </td>
                        <td className="py-2 px-3 tabular-nums text-xs text-brand-muted">
                          {d.av_check_fact != null ? fmtFull(d.av_check_fact) : "—"}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* Mobile: карточки на каждый день */}
            <div className="sm:hidden divide-y divide-brand-border/30">
              {data.days.map(d => {
                const canEdit = d.date >= today
                const avCheckPlan = d.av_check_plan ??
                  (d.sales_plan && d.gc_plan && d.gc_plan > 0
                    ? Math.round(d.sales_plan / d.gc_plan)
                    : null)
                const [, , dd] = d.date.split("-").map(Number)
                const mo = parseInt(d.date.split("-")[1]) - 1
                const dateLabel = `${dd} ${MONTHS_RU_GENITIVE[mo]}`

                return (
                  <div
                    key={d.date}
                    className={cn(
                      "px-4 py-3",
                      d.is_today ? "bg-brand-yellow/10" :
                      d.is_holiday ? "opacity-50" :
                      d.is_future ? "opacity-60" : ""
                    )}
                  >
                    {/* Строка 1: дата + день + % выполнения */}
                    <div className="flex items-center justify-between mb-2.5">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-brand-dark text-sm">{dateLabel}</span>
                        <span className="text-brand-muted text-xs">{d.weekday.slice(0, 2)}</span>
                        {d.is_today && (
                          <span className="px-1.5 py-0.5 rounded bg-brand-yellow text-brand-dark text-[10px] font-bold leading-none">сегодня</span>
                        )}
                      </div>
                      {d.pct_done != null && (
                        <span className={cn(
                          "inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-xs font-semibold",
                          d.pct_done >= 100 ? "bg-green-100 text-green-700" : "bg-red-100 text-brand-red"
                        )}>
                          {d.pct_done >= 100 ? <CheckCircle2 size={10} /> : <AlertTriangle size={10} />}
                          {fmt(d.pct_done, 1)}%
                        </span>
                      )}
                    </div>

                    {/* Строка 2: Продажи план | факт */}
                    <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                      <div>
                        <p className="text-[10px] text-brand-muted uppercase tracking-wide mb-0.5">План продажи</p>
                        <div className="text-blue-600 font-medium text-sm">
                          <EditableCell
                            value={d.sales_plan}
                            disabled={!canEdit}
                            isManual={d.is_manual}
                            fullFormat
                            onSave={v => saveDailyPlan(d.date, "sales_plan", v)}
                          />
                        </div>
                      </div>
                      <div>
                        <p className="text-[10px] text-brand-muted uppercase tracking-wide mb-0.5">Факт продажи</p>
                        <p className="text-sm font-medium text-brand-dark tabular-nums">
                          {d.sales_fact != null ? fmtFull(d.sales_fact) : "—"}
                        </p>
                      </div>

                      <div>
                        <p className="text-[10px] text-brand-muted uppercase tracking-wide mb-0.5">План GC</p>
                        <div className="text-blue-600 text-sm">
                          <EditableCell
                            value={d.gc_plan}
                            disabled={!canEdit}
                            isManual={d.is_manual}
                            isInt
                            onSave={v => saveDailyPlan(d.date, "gc_plan", Math.round(v))}
                          />
                        </div>
                      </div>
                      <div>
                        <p className="text-[10px] text-brand-muted uppercase tracking-wide mb-0.5">Факт GC</p>
                        <p className="text-sm text-brand-dark tabular-nums">
                          {d.gc_fact != null ? fmt(d.gc_fact) : "—"}
                        </p>
                      </div>

                      {(avCheckPlan != null || d.av_check_fact != null) && (
                        <>
                          <div>
                            <p className="text-[10px] text-brand-muted uppercase tracking-wide mb-0.5">Ср. чек план</p>
                            <p className="text-xs text-blue-500 tabular-nums">{avCheckPlan != null ? fmtFull(avCheckPlan) : "—"}</p>
                          </div>
                          <div>
                            <p className="text-[10px] text-brand-muted uppercase tracking-wide mb-0.5">Ср. чек факт</p>
                            <p className="text-xs text-brand-muted tabular-nums">{d.av_check_fact != null ? fmtFull(d.av_check_fact) : "—"}</p>
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
