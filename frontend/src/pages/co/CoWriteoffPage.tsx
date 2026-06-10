import { useState, useEffect, useCallback, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import {
  FileX2, Loader2, RefreshCw, Send, Plus, Trash2,
  ChevronDown, ChevronRight, CheckCircle2, AlertCircle, X, Save, Package,
} from 'lucide-react'
import coApi from '../../api/coClient'
import CoLayout from './CoLayout'

// ── Types ─────────────────────────────────────────────────────────────────────

interface LoadRow {
  restaurant_id: number
  restaurant_name: string
  warehouse_id: number
  warehouse_name: string
  warehouse_iiko_id: string | null
  warehouse_type: string | null
  product_id: number
  product_name: string
  product_num: string
  amount: number
  resigned_sum: number
  inventory_datetime: string | null
  writeoff_datetime: string | null
  account_id: number | null
  account_name: string | null
  account_iiko_id: string | null
}

interface WriteoffAct {
  id: number
  restaurant_name: string
  warehouse_name: string | null
  act_date: string
  inventory_datetime: string | null
  writeoff_datetime: string | null
  total_sum: number | null
  comment: string | null
  status: string
  items_count: number
  posted_at: string | null
  created_at: string
}

interface Account { id: number; account_iiko_id: string; name: string }
interface WarehouseType { id: number; name: string; account_id: number | null; account_name: string | null; account_iiko_id: string | null }

function errMsg(e: unknown): string {
  const d = (e as any)?.response?.data
  return d?.detail ?? d?.message ?? String(e)
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function CoWriteoffPage() {
  const navigate = useNavigate()
  const [me, setMe] = useState<{ name: string; role: string } | null>(null)
  const [tab, setTab] = useState<'act' | 'settings'>('act')

  useEffect(() => {
    coApi.get('/auth/me').then(r => setMe(r.data)).catch(() => navigate('/login'))
  }, [navigate])

  const handleLogout = () => {
    localStorage.removeItem('co_access_token')
    localStorage.removeItem('co_refresh_token')
    navigate('/login')
  }

  return (
    <CoLayout me={me} onLogout={handleLogout}>
      <div className="max-w-6xl mx-auto px-4 py-6 space-y-4">
        <div className="flex items-center gap-3">
          <FileX2 size={22} className="text-brand-dark" />
          <h1 className="text-xl font-bold text-brand-dark">Акт Списания</h1>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-brand-bg border border-brand-border rounded-xl p-1 w-fit">
          {([['act', 'Создать акт'], ['settings', 'Настройки']] as const).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                tab === key ? 'bg-white shadow-sm text-brand-dark' : 'text-brand-muted hover:text-brand-dark'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === 'act' ? <ActTab /> : <SettingsTab />}
      </div>
    </CoLayout>
  )
}

// ── Inline sync button ────────────────────────────────────────────────────────

function SyncProductsButton({ onSynced }: { onSynced: () => void }) {
  const [syncing, setSyncing] = useState(false)
  const [result, setResult] = useState<string | null>(null)

  const sync = async () => {
    setSyncing(true)
    setResult(null)
    try {
      const { data } = await coApi.post('/writeoffs/settings/sync-products')
      const errCount = data.errors?.length ?? 0
      setResult(errCount > 0
        ? `+${data.added} новых, ${data.updated} обновлено (ошибки: ${data.errors.map((e: any) => e.restaurant).join(', ')})`
        : `+${data.added} новых, всего ${data.total} товаров`)
      onSynced()
    } catch { setResult('Ошибка синхронизации') }
    finally { setSyncing(false) }
  }

  return (
    <div className="flex items-center gap-2">
      <button onClick={sync} disabled={syncing} className="btn-secondary text-xs">
        {syncing ? <Loader2 size={13} className="animate-spin" /> : <Package size={13} />}
        Синх. товары
      </button>
      {result && <span className="text-xs text-brand-muted">{result}</span>}
    </div>
  )
}

// ── Act Tab ───────────────────────────────────────────────────────────────────

const MONTHS_SHORT = ['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек']

function monthRange(ym: string): { date_from: string; date_to: string } {
  const [y, m] = ym.split('-').map(Number)
  const last = new Date(y, m, 0).getDate()
  return {
    date_from: `${ym}-01`,
    date_to: `${ym}-${String(last).padStart(2, '0')}`,
  }
}

function MonthPicker({ value, onChange }: { value: string; onChange: (ym: string) => void }) {
  const [y, m] = value.split('-').map(Number)

  const setYear = (dy: number) => onChange(`${y + dy}-${String(m).padStart(2, '0')}`)
  const setMonth = (mi: number) => onChange(`${y}-${String(mi + 1).padStart(2, '0')}`)

  return (
    <div className="bg-white border border-brand-border rounded-xl p-3 w-64 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <button onClick={() => setYear(-1)} className="p-1 rounded hover:bg-brand-bg text-brand-muted hover:text-brand-dark transition-colors">
          <ChevronRight size={16} className="rotate-180" />
        </button>
        <span className="font-bold text-brand-dark text-sm">{y}</span>
        <button onClick={() => setYear(1)} className="p-1 rounded hover:bg-brand-bg text-brand-muted hover:text-brand-dark transition-colors">
          <ChevronRight size={16} />
        </button>
      </div>
      <div className="grid grid-cols-4 gap-1">
        {MONTHS_SHORT.map((name, i) => {
          const active = i + 1 === m
          return (
            <button
              key={i}
              onClick={() => setMonth(i)}
              className={`py-1.5 rounded-lg text-xs font-medium transition-colors ${
                active
                  ? 'bg-brand-yellow text-brand-dark'
                  : 'hover:bg-brand-bg text-brand-muted hover:text-brand-dark'
              }`}
            >
              {name}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function ActTab() {
  const nowYM = new Date().toISOString().slice(0, 7)
  const [month, setMonth] = useState(nowYM)
  const [loading, setLoading] = useState(false)
  const [rows, setRows] = useState<LoadRow[] | null>(null)
  const [errors, setErrors] = useState<{ restaurant_name: string; error: string }[]>([])
  const [amounts, setAmounts] = useState<Record<string, number>>({})
  const [comment, setComment] = useState('')
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null)
  const [acts, setActs] = useState<WriteoffAct[]>([])
  const [actsLoading, setActsLoading] = useState(true)
  const [posting, setPosting] = useState<number | null>(null)
  const [clearing, setClearing] = useState(false)

  const showToast = (msg: string, ok = true) => {
    setToast({ msg, ok })
    setTimeout(() => setToast(null), 3500)
  }

  const loadActs = useCallback(async () => {
    setActsLoading(true)
    try {
      const { data } = await coApi.get('/writeoffs/')
      setActs(data)
    } catch { /* ignore */ }
    finally { setActsLoading(false) }
  }, [])

  useEffect(() => { loadActs() }, [loadActs])

  const load = async () => {
    setLoading(true)
    setRows(null)
    setErrors([])
    setAmounts({})
    try {
      const { date_from, date_to } = monthRange(month)
      const { data } = await coApi.get('/writeoffs/load', { params: { date_from, date_to } })
      setRows(data.rows)
      setErrors(data.errors || [])
      const init: Record<string, number> = {}
      for (const r of data.rows) {
        init[`${r.restaurant_id}_${r.product_id}`] = r.amount
      }
      setAmounts(init)
    } catch (e) {
      showToast(errMsg(e), false)
    } finally {
      setLoading(false)
    }
  }

  const save = async () => {
    if (!rows?.length) return
    setSaving(true)
    try {
      const items = rows
        .map(r => ({
          restaurant_id: r.restaurant_id,
          warehouse_id: r.warehouse_id,
          product_id: r.product_id,
          amount: amounts[`${r.restaurant_id}_${r.product_id}`] ?? r.amount,
          resigned_sum: r.resigned_sum,
          inventory_datetime: r.inventory_datetime,
          writeoff_datetime: r.writeoff_datetime,
        }))
        .filter(i => i.amount > 0)

      if (!items.length) {
        showToast('Нет позиций для создания акта', false)
        return
      }

      const { date_to } = monthRange(month)
      const { data } = await coApi.post('/writeoffs/', { act_date: date_to, comment: comment || null, items })

      const skippedCount = data.skipped?.length ?? 0
      if (skippedCount > 0) {
        showToast(`Создано актов: ${data.created_act_ids.length}. Пропущено: ${skippedCount}`, true)
      } else {
        showToast(`Создано актов: ${data.created_act_ids.length}`)
      }
      setRows(null)
      loadActs()
    } catch (e) {
      showToast(errMsg(e), false)
    } finally {
      setSaving(false)
    }
  }

  const postToIiko = async (actId: number) => {
    setPosting(actId)
    try {
      const { data } = await coApi.post(`/writeoffs/${actId}/post-to-iiko`)
      if (data.errors?.length) {
        const closed = data.errors.some((e: any) => e.period_closed)
        showToast(
          closed
            ? 'Период закрыт в iiko — обратитесь к администратору'
            : `Ошибки: ${data.errors.map((e: any) => e.error).join('; ')}`,
          false,
        )
      } else {
        showToast(`Отправлено в iiko: ${data.docs_sent} документ(а)`)
      }
      loadActs()
    } catch (e) {
      showToast(errMsg(e), false)
    } finally {
      setPosting(null)
    }
  }

  const clearHistory = async () => {
    if (!confirm('Очистить всю историю актов списания? Это действие нельзя отменить.')) return
    setClearing(true)
    try {
      await coApi.delete('/writeoffs/history')
      showToast('История очищена')
      loadActs()
    } catch (e) {
      showToast(errMsg(e), false)
    } finally {
      setClearing(false)
    }
  }

  // Group rows by restaurant + warehouse + writeoff_datetime (одна инвентаризация = один акт)
  const byRestaurant = rows
    ? rows.reduce((acc, r) => {
        const key = `${r.restaurant_id}_${r.warehouse_id}_${r.writeoff_datetime ?? ''}`
        if (!acc[key]) acc[key] = {
          name: r.restaurant_name,
          warehouseName: r.warehouse_name,
          warehouseType: r.warehouse_type,
          inventoryDatetime: r.inventory_datetime,
          writeoffDatetime: r.writeoff_datetime,
          rows: [],
        }
        acc[key].rows.push(r)
        return acc
      }, {} as Record<string, { name: string; warehouseName: string; warehouseType: string | null; inventoryDatetime: string | null; writeoffDatetime: string | null; rows: LoadRow[] }>)
    : {}

  return (
    <div className="space-y-6">
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-2.5 rounded-xl shadow-lg text-sm font-medium flex items-center gap-2 ${toast.ok ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'}`}>
          {toast.ok ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}
          {toast.msg}
        </div>
      )}

      {/* Load panel */}
      <div className="card p-4 space-y-3">
        <p className="text-sm font-medium text-brand-dark">Загрузить инвентаризацию из iiko</p>
        <div className="flex flex-wrap items-start gap-4">
          <div className="space-y-1">
            <label className="block text-xs text-brand-muted">Период</label>
            <MonthPicker value={month} onChange={v => { setMonth(v); setRows(null) }} />
          </div>
          <div className="flex flex-col gap-3 flex-1 min-w-[200px] pt-5">
            <div>
              <label className="block text-xs text-brand-muted mb-1">Комментарий</label>
              <input
                value={comment}
                onChange={e => setComment(e.target.value)}
                placeholder="Необязательно"
                className="input w-full"
              />
            </div>
            <div className="flex gap-2 flex-wrap">
              <button onClick={load} disabled={loading} className="btn-primary">
                {loading ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                Загрузить
              </button>
              <SyncProductsButton onSynced={() => {}} />
            </div>
          </div>
        </div>

        {errors.length > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 space-y-1.5">
            {errors.map((e: any, i) => (
              <div key={i}>
                <p className="text-xs text-amber-800">
                  <span className="font-semibold">{e.restaurant_name}:</span> {e.error}
                </p>
                {e.missing_sum > 0 && (
                  <p className="text-xs text-red-600 font-medium mt-0.5">
                    ⚠ Эти товары не войдут в акт и сумму — синхронизируйте продукты в Админке
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Loaded data */}
      {rows !== null && (
        <div className="space-y-3">
          {rows.length === 0 ? (
            <div className="card p-8 text-center text-brand-muted text-sm">Дефицита нет — всё в норме</div>
          ) : (
            <>
              {Object.entries(byRestaurant).map(([key, { name, warehouseName, warehouseType, inventoryDatetime, writeoffDatetime, rows: rrows }]) => (
                <RestaurantDeficitTable
                  key={key}
                  restaurantName={name}
                  warehouseName={warehouseName}
                  warehouseType={warehouseType}
                  inventoryDatetime={inventoryDatetime}
                  writeoffDatetime={writeoffDatetime}
                  rows={rrows}
                  amounts={amounts}
                  onAmountChange={(k, val) => setAmounts(prev => ({ ...prev, [k]: val }))}
                />
              ))}

              <div className="flex justify-end">
                <button onClick={save} disabled={saving} className="btn-primary">
                  {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                  Создать акт(ы) списания
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {/* Acts history */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-brand-dark">История актов</h2>
          {acts.length > 0 && (
            <button
              onClick={clearHistory}
              disabled={clearing}
              className="flex items-center gap-1 text-xs text-brand-muted hover:text-red-600 transition-colors"
            >
              {clearing ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
              Очистить историю
            </button>
          )}
        </div>
        {actsLoading ? (
          <div className="flex items-center gap-2 text-brand-muted text-sm">
            <Loader2 size={14} className="animate-spin" /> Загрузка...
          </div>
        ) : acts.length === 0 ? (
          <div className="card p-6 text-center text-brand-muted text-sm">Актов ещё нет</div>
        ) : (
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-brand-bg">
                <tr className="border-b border-brand-border text-brand-muted text-xs">
                  <th className="text-left px-4 py-2.5 font-medium">Дата</th>
                  <th className="text-left px-4 py-2.5 font-medium">Ресторан</th>
                  <th className="text-left px-4 py-2.5 font-medium hidden sm:table-cell">Склад</th>
                  <th className="text-left px-4 py-2.5 font-medium hidden sm:table-cell">Позиций</th>
                  <th className="text-right px-4 py-2.5 font-medium hidden md:table-cell">Сумма</th>
                  <th className="text-left px-4 py-2.5 font-medium">Статус</th>
                  <th className="px-4 py-2.5"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-brand-border">
                {acts.map(a => (
                  <tr key={a.id} className="hover:bg-brand-bg/50">
                    <td className="px-4 py-2.5 text-brand-dark font-medium whitespace-nowrap">
                      {a.writeoff_datetime
                        ? fmtDt(a.writeoff_datetime)   // есть точное время
                        : fmtDate(a.act_date)}          // только дата
                    </td>
                    <td className="px-4 py-2.5 text-brand-dark">{a.restaurant_name}</td>
                    <td className="px-4 py-2.5 text-brand-muted hidden sm:table-cell">{a.warehouse_name ?? '—'}</td>
                    <td className="px-4 py-2.5 text-brand-muted hidden sm:table-cell">{a.items_count}</td>
                    <td className="px-4 py-2.5 text-right hidden md:table-cell">
                      {a.total_sum != null
                        ? <span className="text-sm font-medium text-brand-dark">{a.total_sum.toLocaleString('ru-RU', { maximumFractionDigits: 0 })} ₸</span>
                        : <span className="text-brand-muted text-xs">—</span>}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                        a.status === 'posted'
                          ? 'bg-green-50 text-green-700'
                          : 'bg-brand-bg text-brand-muted border border-brand-border'
                      }`}>
                        {a.status === 'posted' ? 'Отправлен' : 'Черновик'}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      {a.status !== 'posted' && (
                        <button
                          onClick={() => postToIiko(a.id)}
                          disabled={posting === a.id}
                          className="flex items-center gap-1 text-xs text-brand-muted hover:text-brand-dark transition-colors"
                        >
                          {posting === a.id
                            ? <Loader2 size={13} className="animate-spin" />
                            : <Send size={13} />}
                          В iiko
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Restaurant Deficit Table ──────────────────────────────────────────────────

function fmtDt(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('ru-RU')
}

function RestaurantDeficitTable({
  restaurantName, warehouseName, warehouseType,
  inventoryDatetime, writeoffDatetime,
  rows, amounts, onAmountChange,
}: {
  restaurantName: string
  warehouseName: string
  warehouseType: string | null
  inventoryDatetime: string | null
  writeoffDatetime: string | null
  rows: LoadRow[]
  amounts: Record<string, number>
  onAmountChange: (key: string, val: number) => void
}) {
  const [open, setOpen] = useState(true)
  const totalQty = rows.reduce((s, r) => s + (amounts[`${r.restaurant_id}_${r.product_id}`] ?? r.amount), 0)
  const totalSum = rows.reduce((s, r) => s + r.resigned_sum, 0)

  return (
    <div className="card overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-brand-bg border-b border-brand-border hover:bg-brand-bg/70 transition-colors"
      >
        <div className="flex items-center gap-2 flex-wrap">
          {open ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
          <span className="font-semibold text-brand-dark">{restaurantName}</span>
          <span className="text-xs bg-brand-yellow/20 border border-brand-yellow/50 rounded px-1.5 py-0.5 text-brand-dark">
            {warehouseName}{warehouseType ? ` · ${warehouseType}` : ''}
          </span>
          <span className="text-xs text-brand-muted">{rows.length} поз.</span>
        </div>
        <span className="text-xs text-brand-muted shrink-0">
          {totalQty.toLocaleString('ru-RU', { maximumFractionDigits: 3 })} · {totalSum.toLocaleString('ru-RU', { maximumFractionDigits: 0 })} ₸
        </span>
      </button>

      {/* Даты инвентаризации и списания */}
      {open && inventoryDatetime && (
        <div className="px-4 py-2 border-b border-brand-border bg-white flex flex-wrap gap-4 text-xs text-brand-muted">
          <span>
            Инвентаризация: <span className="font-medium text-brand-dark">
              {writeoffDatetime ? fmtDt(inventoryDatetime) : fmtDate(inventoryDatetime)}
            </span>
          </span>
          {writeoffDatetime && (
            <span>Дата акта (−2ч): <span className="font-medium text-green-700">{fmtDt(writeoffDatetime)}</span></span>
          )}
          {!writeoffDatetime && (
            <span className="text-brand-muted/60 italic">Время не определено — iiko вернул только дату</span>
          )}
        </div>
      )}

      {open && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-brand-border text-brand-muted text-xs bg-white">
                <th className="text-left px-4 py-2 font-medium">Товар</th>
                <th className="text-left px-4 py-2 font-medium hidden sm:table-cell">Счёт</th>
                <th className="text-right px-4 py-2 font-medium hidden md:table-cell">Сумма</th>
                <th className="text-right px-4 py-2 font-medium">Количество</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-brand-border">
              {rows.map(r => {
                const key = `${r.restaurant_id}_${r.product_id}`
                return (
                  <tr key={key} className="hover:bg-brand-bg/30">
                    <td className="px-4 py-2">
                      <div className="text-brand-dark">{r.product_name}</div>
                      <div className="text-xs text-brand-muted font-mono">{r.product_num}</div>
                    </td>
                    <td className="px-4 py-2 hidden sm:table-cell">
                      {r.account_name
                        ? <span className="text-xs text-brand-muted">{r.account_name}</span>
                        : <span className="text-xs text-amber-600">Нет счёта — назначьте тип складу</span>}
                    </td>
                    <td className="px-4 py-2 text-right hidden md:table-cell">
                      <span className="text-xs text-brand-muted">
                        {r.resigned_sum > 0 ? r.resigned_sum.toLocaleString('ru-RU', { maximumFractionDigits: 0 }) + ' ₸' : '—'}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right">
                      <input
                        type="number"
                        step="0.001"
                        min="0"
                        value={amounts[key] ?? r.amount}
                        onChange={e => onAmountChange(key, parseFloat(e.target.value) || 0)}
                        className="input w-24 text-right text-sm py-1 px-2"
                      />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Settings Tab ──────────────────────────────────────────────────────────────

function SettingsTab() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [warehouseTypes, setWarehouseTypes] = useState<WarehouseType[]>([])
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null)

  const showToast = (msg: string, ok = true) => {
    setToast({ msg, ok })
    setTimeout(() => setToast(null), 3500)
  }

  const reload = useCallback(async () => {
    setLoading(true)
    try {
      const [accRes, typRes] = await Promise.all([
        coApi.get('/writeoffs/settings/accounts'),
        coApi.get('/writeoffs/settings/warehouse-types'),
      ])
      setAccounts(accRes.data)
      setWarehouseTypes(typRes.data)
    } catch (e) { showToast(errMsg(e), false) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { reload() }, [reload])

  if (loading) return <div className="flex items-center gap-2 text-brand-muted text-sm"><Loader2 size={14} className="animate-spin" /> Загрузка...</div>

  return (
    <div className="space-y-6">
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-2.5 rounded-xl shadow-lg text-sm font-medium flex items-center gap-2 ${toast.ok ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'}`}>
          {toast.ok ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}
          {toast.msg}
        </div>
      )}

      <ProductsSyncSection showToast={showToast} />
      <PresetSection showToast={showToast} />
      <AccountsSection accounts={accounts} onReload={reload} showToast={showToast} />
      <WarehouseTypesSection accounts={accounts} warehouseTypes={warehouseTypes} onReload={reload} showToast={showToast} />
    </div>
  )
}

// ── Products Sync Section ─────────────────────────────────────────────────────

function ProductsSyncSection({ showToast }: { showToast: (m: string, ok?: boolean) => void }) {
  const [info, setInfo] = useState<{ total: number } | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [loading, setLoading] = useState(true)

  const loadInfo = async () => {
    try {
      const { data } = await coApi.get('/writeoffs/settings/products')
      setInfo({ total: data.total })
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }

  useEffect(() => { loadInfo() }, [])

  const sync = async () => {
    setSyncing(true)
    try {
      const { data } = await coApi.post('/writeoffs/settings/sync-products')
      const errCount = data.errors?.length ?? 0
      if (errCount > 0) {
        showToast(
          `Синхронизировано: +${data.added} новых, ${data.updated} обновлено. Всего: ${data.total}. Ошибки: ${data.errors.map((e: any) => e.restaurant).join(', ')}`,
          false,
        )
      } else {
        showToast(`Синхронизировано: +${data.added} новых, ${data.updated} обновлено. Всего: ${data.total}`)
      }
      setInfo({ total: data.total })
    } catch (e) { showToast(errMsg(e), false) }
    finally { setSyncing(false) }
  }

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Package size={18} className="text-brand-dark shrink-0" />
          <div>
            <h2 className="text-base font-semibold text-brand-dark">Товары</h2>
            <p className="text-xs text-brand-muted mt-0.5">
              {loading ? 'Загрузка...' : `${info?.total ?? 0} товаров в базе · Синхронизируйте перед созданием акта`}
            </p>
          </div>
        </div>
        <button onClick={sync} disabled={syncing} className="btn-primary text-xs shrink-0">
          {syncing ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
          {syncing ? 'Синхронизация...' : 'Синхронизировать из iiko'}
        </button>
      </div>
    </div>
  )
}

// ── Preset Section ────────────────────────────────────────────────────────────

function PresetSection({ showToast }: { showToast: (m: string, ok?: boolean) => void }) {
  const [presetId, setPresetId] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [activating, setActivating] = useState(false)
  const [columns, setColumns] = useState<string[] | null>(null)

  useEffect(() => {
    coApi.get('/writeoffs/settings/preset')
      .then(r => setPresetId(r.data.preset_id || ''))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const save = async () => {
    if (!presetId.trim()) return
    setSaving(true)
    try {
      await coApi.post('/writeoffs/settings/preset', { preset_id: presetId.trim() })
      showToast('UUID пресета сохранён')
    } catch (e) { showToast(errMsg(e), false) }
    finally { setSaving(false) }
  }

  const activate = async () => {
    setActivating(true)
    setColumns(null)
    try {
      const { data } = await coApi.post('/writeoffs/settings/preset/activate')
      setColumns(data.columns)
      showToast(data.message ?? `Пресет активен — ${data.sample_rows} строк за сегодня`)
    } catch (e) { showToast(errMsg(e), false) }
    finally { setActivating(false) }
  }

  return (
    <div className="card p-4 space-y-3">
      <h2 className="text-base font-semibold text-brand-dark">Пресет инвентаризации</h2>
      <p className="text-xs text-brand-muted">Один UUID пресета для всех ресторанов CO. Найдите его в iiko Office → Отчёты → OLAP.</p>

      {loading ? (
        <div className="flex items-center gap-2 text-brand-muted text-sm"><Loader2 size={13} className="animate-spin" /> Загрузка...</div>
      ) : (
        <div className="space-y-3">
          <div className="flex gap-2">
            <input
              value={presetId}
              onChange={e => { setPresetId(e.target.value); setColumns(null) }}
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              className="input flex-1 font-mono text-xs"
            />
            <button onClick={save} disabled={saving || !presetId.trim()} className="btn-secondary text-xs shrink-0">
              {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />} Сохранить
            </button>
            <button onClick={activate} disabled={activating || !presetId.trim()} className="btn-primary text-xs shrink-0">
              {activating ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />} Активировать
            </button>
          </div>

          {columns !== null && (
            <div className="bg-brand-bg border border-brand-border rounded-lg p-3">
              <p className="text-xs font-medium text-brand-dark mb-2">Колонки пресета ({columns.length}):</p>
              <div className="flex flex-wrap gap-1">
                {columns.map(c => (
                  <span key={c} className={`text-xs font-mono px-2 py-0.5 rounded border ${
                    c === 'Product.Num' || c === 'Amount'
                      ? 'bg-green-50 border-green-300 text-green-700 font-semibold'
                      : 'bg-white border-brand-border text-brand-muted'
                  }`}>{c}</span>
                ))}
              </div>
              {columns.includes('Product.Num') && columns.includes('Amount')
                ? <p className="text-xs text-green-700 mt-2 font-medium">✓ Пресет содержит нужные колонки Product.Num и Amount</p>
                : <p className="text-xs text-red-600 mt-2 font-medium">⚠ Пресет должен содержать колонки Product.Num и Amount</p>}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Accounts Section ──────────────────────────────────────────────────────────

function AccountsSection({
  accounts, onReload, showToast,
}: {
  accounts: Account[]
  onReload: () => void
  showToast: (m: string, ok?: boolean) => void
}) {
  const [syncing, setSyncing] = useState(false)
  const [accSearch, setAccSearch] = useState('')

  const sync = async () => {
    setSyncing(true)
    try {
      const { data } = await coApi.post('/writeoffs/settings/sync-accounts')
      showToast(`Синхронизировано: +${data.added} новых, ${data.updated} обновлено. Всего: ${data.total}`)
      onReload()
    } catch (e) { showToast(errMsg(e), false) }
    finally { setSyncing(false) }
  }

  const del = async (id: number) => {
    if (!confirm('Удалить счёт?')) return
    try {
      await coApi.delete(`/writeoffs/settings/accounts/${id}`)
      showToast('Удалено')
      onReload()
    } catch (e) { showToast(errMsg(e), false) }
  }

  const filtered = accSearch
    ? accounts.filter(a => a.name.toLowerCase().includes(accSearch.toLowerCase()))
    : accounts

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold text-brand-dark">Счета списания</h2>
          <p className="text-xs text-brand-muted mt-0.5">Синхронизируются из iiko · {accounts.length} шт.</p>
        </div>
        <button onClick={sync} disabled={syncing} className="btn-primary text-xs">
          {syncing ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
          Синхронизировать из iiko
        </button>
      </div>

      {accounts.length === 0 ? (
        <div className="card p-6 text-center text-brand-muted text-sm">
          Нет счетов. Нажмите "Синхронизировать из iiko".
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="px-4 py-2.5 border-b border-brand-border bg-brand-bg">
            <input
              value={accSearch}
              onChange={e => setAccSearch(e.target.value)}
              placeholder="Поиск по названию..."
              className="input text-xs py-1 w-full sm:w-64"
            />
          </div>
          <div className="max-h-64 overflow-y-auto">
            <table className="w-full text-sm">
              <tbody className="divide-y divide-brand-border">
                {filtered.map(a => (
                  <tr key={a.id} className="hover:bg-brand-bg/50">
                    <td className="px-4 py-2 text-brand-dark">{a.name}</td>
                    <td className="px-4 py-2 font-mono text-xs text-brand-muted hidden sm:table-cell">{a.account_iiko_id}</td>
                    <td className="px-4 py-2 w-8">
                      <button onClick={() => del(a.id)} className="p-1 hover:bg-red-50 rounded text-brand-muted hover:text-red-600 transition-colors">
                        <Trash2 size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr><td colSpan={3} className="px-4 py-4 text-center text-brand-muted text-xs">Ничего не найдено</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Account Search Dropdown ───────────────────────────────────────────────────

function AccountSearch({
  accounts, value, onChange,
}: {
  accounts: Account[]
  value: string
  onChange: (id: string) => void
}) {
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [rect, setRect] = useState<DOMRect | null>(null)
  const triggerRef = useRef<HTMLDivElement>(null)
  const selected = accounts.find(a => String(a.id) === value)
  const filtered = q
    ? accounts.filter(a => a.name.toLowerCase().includes(q.toLowerCase()))
    : accounts

  const handleOpen = () => {
    if (triggerRef.current) setRect(triggerRef.current.getBoundingClientRect())
    setOpen(o => !o)
  }

  // Пересчитываем позицию при скролле/ресайзе пока открыт
  useEffect(() => {
    if (!open) return
    const update = () => {
      if (triggerRef.current) setRect(triggerRef.current.getBoundingClientRect())
    }
    window.addEventListener('scroll', update, true)
    window.addEventListener('resize', update)
    return () => { window.removeEventListener('scroll', update, true); window.removeEventListener('resize', update) }
  }, [open])

  const dropdownStyle = rect ? {
    position: 'fixed' as const,
    top: rect.bottom + 4,
    left: rect.left,
    width: rect.width,
    zIndex: 9999,
  } : {}

  return (
    <div className="relative" ref={triggerRef}>
      <div
        className="input cursor-pointer flex items-center justify-between gap-2 min-h-[38px]"
        onClick={handleOpen}
      >
        <span className={selected ? 'text-brand-dark truncate' : 'text-brand-muted'}>
          {selected ? selected.name : '— без счёта —'}
        </span>
        <ChevronDown size={14} className={`shrink-0 text-brand-muted transition-transform ${open ? 'rotate-180' : ''}`} />
      </div>

      {open && rect && createPortal(
        <>
          <div className="fixed inset-0 z-[9998]" onClick={() => { setOpen(false); setQ('') }} />
          <div style={dropdownStyle} className="bg-white border border-brand-border rounded-xl shadow-xl overflow-hidden">
            <div className="p-2 border-b border-brand-border">
              <input
                autoFocus
                value={q}
                onChange={e => setQ(e.target.value)}
                placeholder="Поиск счёта..."
                className="input text-xs py-1 w-full"
                onClick={e => e.stopPropagation()}
              />
            </div>
            <div className="max-h-52 overflow-y-auto">
              <button
                onClick={() => { onChange(''); setOpen(false); setQ('') }}
                className="w-full text-left px-3 py-2 text-xs text-brand-muted hover:bg-brand-bg transition-colors"
              >
                — без счёта —
              </button>
              {filtered.map(a => (
                <button
                  key={a.id}
                  onClick={() => { onChange(String(a.id)); setOpen(false); setQ('') }}
                  className={`w-full text-left px-3 py-2 text-xs hover:bg-brand-bg transition-colors ${String(a.id) === value ? 'bg-brand-yellow/10 font-semibold text-brand-dark' : 'text-brand-dark'}`}
                >
                  {a.name}
                </button>
              ))}
              {filtered.length === 0 && (
                <p className="px-3 py-3 text-xs text-brand-muted text-center">Ничего не найдено</p>
              )}
            </div>
          </div>
        </>,
        document.body,
      )}
    </div>
  )
}

// ── Warehouse Types Section ───────────────────────────────────────────────────

function WarehouseTypesSection({
  accounts, warehouseTypes, onReload, showToast,
}: {
  accounts: Account[]
  warehouseTypes: WarehouseType[]
  onReload: () => void
  showToast: (m: string, ok?: boolean) => void
}) {
  const [newName, setNewName] = useState('')
  const [newAccId, setNewAccId] = useState('')
  const [adding, setAdding] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)
  const [editName, setEditName] = useState('')
  const [editAccId, setEditAccId] = useState('')
  const [saving, setSaving] = useState(false)

  const create = async () => {
    if (!newName.trim()) return
    setAdding(true)
    try {
      await coApi.post('/writeoffs/settings/warehouse-types', {
        name: newName.trim(),
        account_id: newAccId ? parseInt(newAccId) : null,
      })
      showToast('Тип склада создан')
      setNewName('')
      setNewAccId('')
      onReload()
    } catch (e) { showToast(errMsg(e), false) }
    finally { setAdding(false) }
  }

  const startEdit = (t: WarehouseType) => {
    setEditId(t.id)
    setEditName(t.name)
    setEditAccId(t.account_id ? String(t.account_id) : '')
  }

  const update = async () => {
    if (editId === null) return
    setSaving(true)
    try {
      await coApi.patch(`/writeoffs/settings/warehouse-types/${editId}`, {
        name: editName.trim(),
        account_id: editAccId ? parseInt(editAccId) : 0,
      })
      showToast('Сохранено')
      setEditId(null)
      onReload()
    } catch (e) { showToast(errMsg(e), false) }
    finally { setSaving(false) }
  }

  const del = async (id: number) => {
    if (!confirm('Удалить тип склада?')) return
    try {
      await coApi.delete(`/writeoffs/settings/warehouse-types/${id}`)
      showToast('Удалено')
      onReload()
    } catch (e) { showToast(errMsg(e), false) }
  }

  return (
    <div className="space-y-3">
      <div>
        <h2 className="text-base font-semibold text-brand-dark">Типы складов → Счёт</h2>
        <p className="text-xs text-brand-muted mt-0.5">
          Каждый тип склада привязывается к счёту списания. Затем назначьте тип конкретным складам в Админке → Склады.
        </p>
      </div>

      {/* New type form */}
      <div className="card p-4">
        <p className="text-xs font-medium text-brand-muted mb-3">Новый тип склада</p>
        <div className="flex flex-wrap gap-2 items-end">
          <div className="flex-1 min-w-[140px]">
            <label className="block text-xs text-brand-muted mb-1">Название (напр. Хозка)</label>
            <input
              value={newName}
              onChange={e => setNewName(e.target.value)}
              placeholder="Хозка, Бар, Кухня..."
              className="input w-full"
              onKeyDown={e => e.key === 'Enter' && create()}
            />
          </div>
          <div className="flex-1 min-w-[200px]">
            <label className="block text-xs text-brand-muted mb-1">Счёт списания</label>
            <AccountSearch accounts={accounts} value={newAccId} onChange={setNewAccId} />
          </div>
          <button onClick={create} disabled={adding || !newName.trim()} className="btn-primary text-xs shrink-0">
            {adding ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
            Добавить
          </button>
        </div>
      </div>

      {warehouseTypes.length === 0 ? (
        <div className="card p-6 text-center text-brand-muted text-sm">Нет типов складов. Добавьте выше.</div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-brand-bg border-b border-brand-border">
              <tr className="text-brand-muted text-xs">
                <th className="text-left px-4 py-2.5 font-medium">Тип склада</th>
                <th className="text-left px-4 py-2.5 font-medium">Счёт списания</th>
                <th className="px-4 py-2.5 w-24"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-brand-border">
              {warehouseTypes.map(t => (
                <tr key={t.id} className="hover:bg-brand-bg/30">
                  {editId === t.id ? (
                    <>
                      <td className="px-4 py-2">
                        <input
                          value={editName}
                          onChange={e => setEditName(e.target.value)}
                          className="input text-sm py-1 w-full"
                        />
                      </td>
                      <td className="px-4 py-2">
                        <AccountSearch accounts={accounts} value={editAccId} onChange={setEditAccId} />
                      </td>
                      <td className="px-4 py-2">
                        <div className="flex gap-1">
                          <button onClick={update} disabled={saving} className="btn-primary text-xs py-1 px-2">
                            {saving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
                          </button>
                          <button onClick={() => setEditId(null)} className="btn-secondary text-xs py-1 px-2">
                            <X size={12} />
                          </button>
                        </div>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="px-4 py-2.5 font-medium text-brand-dark">{t.name}</td>
                      <td className="px-4 py-2.5">
                        {t.account_name
                          ? <span className="text-xs bg-brand-yellow/20 border border-brand-yellow/50 rounded px-2 py-0.5 text-brand-dark">{t.account_name}</span>
                          : <span className="text-xs text-red-500">Без счёта</span>}
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="flex gap-1 justify-end">
                          <button onClick={() => startEdit(t)} className="text-xs text-brand-muted hover:text-brand-dark px-2 py-1 rounded hover:bg-brand-bg transition-colors">Изменить</button>
                          <button onClick={() => del(t.id)} className="p-1.5 hover:bg-red-50 rounded text-brand-muted hover:text-red-600 transition-colors">
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

