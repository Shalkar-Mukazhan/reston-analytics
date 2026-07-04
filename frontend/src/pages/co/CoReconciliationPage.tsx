import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import coApi from '../../api/coClient'
import CoLayout from './CoLayout'
import {
  Upload, X, Loader2, AlertCircle, CheckCircle2, FileWarning, ScanSearch, Save, History, Trash2,
} from 'lucide-react'

interface Restaurant { id: number; name: string }
interface SupplierCandidate { id: number; name: string; bin: string | null }
interface RowResult {
  date: string | null
  description: string
  document_number: string | null
  debit: number | null
  credit: number | null
  status: 'matched' | 'matched_date_shift' | 'amount_mismatch' | 'missing_in_iiko' | 'payment' | 'info'
  matched_invoice: { iiko_document_number?: string; incoming_document_number?: string; date?: string; total: number } | null
}
interface ExtraInvoice {
  iiko_id: string
  document_number: string | null
  incoming_document_number: string | null
  date: string | null
  total: number
}
interface CheckResult {
  supplier_found: boolean
  candidates?: SupplierCandidate[]
  left_org?: { name: string | null; bin: string | null }
  right_org?: { name: string | null; bin: string | null }
  supplier?: { id: number; name: string; bin: string | null }
  period: { from: string | null; to: string | null }
  rows?: RowResult[]
  extra_invoices?: ExtraInvoice[]
  opening_balance?: { debit: number | null; credit: number | null } | null
  closing_balance?: { debit: number | null; credit: number | null } | null
  totals?: { credit_total: number; debit_total: number; iiko_invoices_total: number; delta: number }
  verdict?: 'ok' | 'discrepancy'
  warnings?: string[]
  source_filename?: string
}
interface SavedActSummary {
  id: number
  restaurant_id: number
  restaurant_name: string | null
  supplier_id: number
  supplier_name: string | null
  period_from: string
  period_to: string
  credit_total: number
  debit_total: number
  delta: number
  verdict: 'ok' | 'discrepancy'
  created_at: string
}

const money = (n: number | null | undefined) =>
  n == null ? '—' : n.toLocaleString('ru-RU', { minimumFractionDigits: 2 }) + ' ₸'

const fmtDate = (d: string | null) => {
  if (!d) return '—'
  const [y, m, day] = d.split('-')
  return `${day}.${m}.${y}`
}

const STATUS_LABEL: Record<string, string> = {
  matched: 'Совпадает',
  matched_date_shift: 'Совпадает (дата ±)',
  amount_mismatch: 'Сумма отличается',
  missing_in_iiko: 'Нет в iiko',
  payment: 'Оплата',
  info: '—',
}

function StatusBadge({ status }: { status: RowResult['status'] }) {
  const cls =
    status === 'matched' ? 'badge-ok'
    : status === 'matched_date_shift' ? 'badge-blue'
    : status === 'amount_mismatch' ? 'badge-over'
    : status === 'missing_in_iiko' ? 'badge-warn'
    : status === 'payment' ? 'badge-blue'
    : 'badge-muted'
  return <span className={cls}>{STATUS_LABEL[status]}</span>
}

export default function CoReconciliationPage() {
  const navigate = useNavigate()
  const [me, setMe] = useState<{ name: string; role: string } | null>(null)
  const [restaurants, setRestaurants] = useState<Restaurant[]>([])
  const [restaurantId, setRestaurantId] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<CheckResult | null>(null)
  const [savedActs, setSavedActs] = useState<SavedActSummary[]>([])
  const [savedActId, setSavedActId] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  const [viewingSaved, setViewingSaved] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const loadHistory = () => {
    coApi.get('/reconciliation/').then(r => setSavedActs(r.data)).catch(() => {})
  }

  useEffect(() => {
    coApi.get('/auth/me').then(r => {
      setMe(r.data)
      coApi.get('/admin/restaurants').then(res => {
        setRestaurants(res.data)
        if (res.data.length === 1) setRestaurantId(String(res.data[0].id))
      })
    }).catch(() => navigate('/login'))
    loadHistory()
  }, [])

  const runCheck = async (supplierId?: number) => {
    if (!file || !restaurantId) return
    setChecking(true); setError(''); setSavedActId(null); setViewingSaved(false)
    try {
      const form = new FormData()
      form.append('restaurant_id', restaurantId)
      form.append('file', file)
      if (supplierId) form.append('supplier_id', String(supplierId))
      const { data } = await coApi.post('/reconciliation/check', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResult(data)
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message)
    } finally { setChecking(false) }
  }

  const reset = () => {
    setFile(null); setResult(null); setError(''); setSavedActId(null); setViewingSaved(false)
    if (fileRef.current) fileRef.current.value = ''
    loadHistory()
  }

  const saveAct = async () => {
    if (!result || !result.supplier_found || !result.supplier) return
    setSaving(true)
    try {
      const { data } = await coApi.post('/reconciliation/save', {
        restaurant_id: Number(restaurantId),
        supplier_id: result.supplier.id,
        period_from: result.period.from,
        period_to: result.period.to,
        credit_total: result.totals?.credit_total ?? 0,
        debit_total: result.totals?.debit_total ?? 0,
        iiko_invoices_total: result.totals?.iiko_invoices_total ?? 0,
        delta: result.totals?.delta ?? 0,
        verdict: result.verdict ?? 'discrepancy',
        rows: result.rows ?? [],
        extra_invoices: result.extra_invoices ?? [],
        source_filename: result.source_filename ?? null,
      })
      setSavedActId(data.id)
      loadHistory()
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message)
    } finally { setSaving(false) }
  }

  const openSaved = async (id: number) => {
    setChecking(true); setError('')
    try {
      const { data } = await coApi.get(`/reconciliation/${id}`)
      setResult({ supplier_found: true, ...data })
      setRestaurantId(String(data.restaurant_id))
      setSavedActId(id)
      setViewingSaved(true)
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message)
    } finally { setChecking(false) }
  }

  const deleteSaved = async (id: number, opts?: { fromDetail?: boolean }) => {
    if (!confirm('Удалить акт сверки?')) return
    try {
      await coApi.delete(`/reconciliation/${id}`)
      setSavedActs(prev => prev.filter(a => a.id !== id))
      if (opts?.fromDetail) reset()
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message)
    }
  }

  return (
    <CoLayout me={me} onLogout={() => { localStorage.clear(); navigate('/login') }}>
      <div className="max-w-5xl mx-auto space-y-6">
        <div>
          <h1 className="text-xl font-semibold text-brand-dark">Акт сверки</h1>
          <p className="text-sm text-brand-muted mt-1">
            Загрузите акт сверки взаиморасчётов от поставщика (xls, xlsx или pdf) —
            система сверит его с вашими накладными в системе.
          </p>
        </div>

        {!result && (
          <div className="card p-6 space-y-4">
            <div>
              <label className="block text-sm font-medium text-brand-dark mb-1.5">Ресторан</label>
              <select
                className="w-full border border-brand-border rounded-lg px-3 py-2 text-sm bg-white"
                value={restaurantId}
                onChange={e => setRestaurantId(e.target.value)}
              >
                <option value="">Выберите ресторан</option>
                {restaurants.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-brand-dark mb-1.5">Файл акта сверки</label>
              {!file ? (
                <label className="flex flex-col items-center justify-center gap-2 border-2 border-dashed border-brand-border rounded-xl py-10 cursor-pointer hover:bg-brand-bg transition-colors">
                  <Upload size={28} className="text-brand-muted" />
                  <span className="text-sm text-brand-muted">Нажмите, чтобы выбрать файл (.xls, .xlsx, .pdf)</span>
                  <input
                    ref={fileRef}
                    type="file"
                    accept=".xls,.xlsx,.pdf"
                    className="hidden"
                    onChange={e => setFile(e.target.files?.[0] || null)}
                  />
                </label>
              ) : (
                <div className="flex items-center justify-between border border-brand-border rounded-lg px-3 py-2.5">
                  <span className="text-sm text-brand-dark truncate">{file.name}</span>
                  <button onClick={() => setFile(null)} className="text-brand-muted hover:text-brand-red">
                    <X size={16} />
                  </button>
                </div>
              )}
            </div>

            {error && (
              <div className="flex items-start gap-2 text-sm text-brand-red bg-red-50 border border-red-200 rounded-lg px-3 py-2.5">
                <AlertCircle size={16} className="mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              disabled={!file || !restaurantId || checking}
              onClick={() => runCheck()}
              className="w-full flex items-center justify-center gap-2 bg-brand-green text-white rounded-lg py-2.5 text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed hover:brightness-95 transition"
            >
              {checking ? <Loader2 size={16} className="animate-spin" /> : <ScanSearch size={16} />}
              {checking ? 'Сверяем…' : 'Сверить'}
            </button>
          </div>
        )}

        {!result && savedActs.length > 0 && (
          <div className="card p-5">
            <div className="flex items-center gap-2 font-medium text-brand-dark mb-3">
              <History size={16} className="text-brand-muted" />
              История сверок
            </div>
            <div className="space-y-2">
              {savedActs.map(a => (
                <div
                  key={a.id}
                  className="w-full border border-brand-border rounded-lg px-3 py-2.5 text-sm hover:bg-brand-bg transition-colors flex flex-wrap items-center justify-between gap-2"
                >
                  <button onClick={() => openSaved(a.id)} className="text-left flex-1 min-w-0">
                    <span className="text-brand-dark">
                      {a.restaurant_name} · {a.supplier_name} · {fmtDate(a.period_from)} — {fmtDate(a.period_to)}
                    </span>
                  </button>
                  <span className="flex items-center gap-2">
                    <span className="text-brand-muted">{money(a.credit_total)}</span>
                    {a.verdict === 'ok' ? <span className="badge-ok">Сходится</span> : <span className="badge-over">Расхождения</span>}
                    <button
                      onClick={() => deleteSaved(a.id)}
                      className="p-1.5 hover:bg-red-50 rounded text-brand-muted hover:text-red-600 transition-colors"
                    >
                      <Trash2 size={14} />
                    </button>
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {result && !result.supplier_found && (
          <div className="card p-6 space-y-4">
            <div className="flex items-start gap-2 text-sm text-brand-amber bg-amber-50 border border-amber-200 rounded-lg px-3 py-2.5">
              <FileWarning size={16} className="mt-0.5 shrink-0" />
              <span>
                Не удалось автоматически определить поставщика по БИН
                {result.left_org?.bin || result.right_org?.bin ? (
                  <> (найдены БИН в файле: {[result.left_org?.bin, result.right_org?.bin].filter(Boolean).join(', ')}, совпадения в справочнике нет)</>
                ) : null}. Выберите поставщика вручную:
              </span>
            </div>
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {(result.candidates || []).map(c => (
                <button
                  key={c.id}
                  onClick={() => runCheck(c.id)}
                  className="w-full text-left border border-brand-border rounded-lg px-3 py-2.5 text-sm hover:bg-brand-bg transition-colors flex justify-between"
                >
                  <span className="text-brand-dark">{c.name}</span>
                  <span className="text-brand-muted">{c.bin || '—'}</span>
                </button>
              ))}
            </div>
            <button onClick={reset} className="text-sm text-brand-muted hover:text-brand-dark">← Загрузить другой файл</button>
          </div>
        )}

        {result && result.supplier_found && (
          <div className="space-y-4">
            <div className="card p-5 flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-sm text-brand-muted">Поставщик</div>
                <div className="font-medium text-brand-dark">{result.supplier?.name}</div>
                <div className="text-xs text-brand-muted">БИН: {result.supplier?.bin || '—'}</div>
              </div>
              <div>
                <div className="text-sm text-brand-muted">Период</div>
                <div className="font-medium text-brand-dark">{fmtDate(result.period.from)} — {fmtDate(result.period.to)}</div>
              </div>
              <div>
                {result.verdict === 'ok' ? (
                  <span className="badge-ok text-sm px-3 py-1"><CheckCircle2 size={14} className="inline mr-1 -mt-0.5" />Сходится</span>
                ) : (
                  <span className="badge-over text-sm px-3 py-1"><AlertCircle size={14} className="inline mr-1 -mt-0.5" />Есть расхождения</span>
                )}
              </div>
              <div className="flex items-center gap-3">
                {!viewingSaved && (
                  savedActId ? (
                    <span className="flex items-center gap-1.5 text-sm text-brand-green">
                      <CheckCircle2 size={16} />Сохранено
                    </span>
                  ) : (
                    <button
                      onClick={saveAct}
                      disabled={saving}
                      className="flex items-center gap-1.5 text-sm font-medium bg-brand-navy text-white rounded-lg px-3 py-2 disabled:opacity-40 hover:brightness-110 transition"
                    >
                      {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                      Сохранить
                    </button>
                  )
                )}
                {viewingSaved && savedActId && (
                  <button
                    onClick={() => deleteSaved(savedActId, { fromDetail: true })}
                    className="flex items-center gap-1.5 text-sm font-medium text-brand-red hover:bg-red-50 rounded-lg px-3 py-2 transition"
                  >
                    <Trash2 size={14} />
                    Удалить
                  </button>
                )}
                <button onClick={reset} className="text-sm text-brand-muted hover:text-brand-dark">← Новая сверка</button>
              </div>
            </div>

            {error && (
              <div className="flex items-start gap-2 text-sm text-brand-red bg-red-50 border border-red-200 rounded-lg px-3 py-2.5">
                <AlertCircle size={16} className="mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {(result.warnings || []).length > 0 && (
              <div className="text-sm text-brand-amber bg-amber-50 border border-amber-200 rounded-lg px-3 py-2.5">
                {result.warnings!.map((w, i) => <div key={i}>{w}</div>)}
              </div>
            )}

            <div className="card p-5">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <div className="text-brand-muted">Накладные по акту (Кредит)</div>
                  <div className="font-semibold text-brand-dark">{money(result.totals?.credit_total)}</div>
                </div>
                <div>
                  <div className="text-brand-muted">Оплаты по акту (Дебет)</div>
                  <div className="font-semibold text-brand-dark">{money(result.totals?.debit_total)}</div>
                </div>
                <div>
                  <div className="text-brand-muted">Накладные в iiko за период</div>
                  <div className="font-semibold text-brand-dark">{money(result.totals?.iiko_invoices_total)}</div>
                </div>
                <div>
                  <div className="text-brand-muted">Расхождение</div>
                  <div className={`font-semibold ${Math.abs(result.totals?.delta || 0) >= 1 ? 'text-brand-red' : 'text-brand-dark'}`}>
                    {money(result.totals?.delta)}
                  </div>
                </div>
              </div>
              {(result.opening_balance || result.closing_balance) && (
                <div className="mt-4 pt-4 border-t border-brand-border grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-brand-muted">Сальдо на начало: </span>
                    <span className="font-medium text-brand-dark">
                      {result.opening_balance?.debit ? `Дебет ${money(result.opening_balance.debit)}` :
                       result.opening_balance?.credit ? `Кредит ${money(result.opening_balance.credit)}` : '0'}
                    </span>
                  </div>
                  <div>
                    <span className="text-brand-muted">Сальдо на конец: </span>
                    <span className="font-medium text-brand-dark">
                      {result.closing_balance?.debit ? `Дебет ${money(result.closing_balance.debit)}` :
                       result.closing_balance?.credit ? `Кредит ${money(result.closing_balance.credit)}` : '0'}
                    </span>
                  </div>
                </div>
              )}
            </div>

            <div className="card overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-brand-muted border-b border-brand-border">
                    <th className="py-2.5 px-3 font-medium">Дата</th>
                    <th className="py-2.5 px-3 font-medium">Документ</th>
                    <th className="py-2.5 px-3 font-medium text-right">Дебет</th>
                    <th className="py-2.5 px-3 font-medium text-right">Кредит</th>
                    <th className="py-2.5 px-3 font-medium">Найдено в iiko</th>
                    <th className="py-2.5 px-3 font-medium">Статус</th>
                  </tr>
                </thead>
                <tbody>
                  {(result.rows || []).map((r, i) => (
                    <tr key={i} className="border-b border-brand-border last:border-0">
                      <td className="py-2.5 px-3 whitespace-nowrap">{fmtDate(r.date)}</td>
                      <td className="py-2.5 px-3">{r.description}</td>
                      <td className="py-2.5 px-3 text-right tabular-nums">{r.debit ? money(r.debit) : ''}</td>
                      <td className="py-2.5 px-3 text-right tabular-nums">{r.credit ? money(r.credit) : ''}</td>
                      <td className="py-2.5 px-3 text-xs text-brand-muted whitespace-nowrap">
                        {r.matched_invoice ? (
                          <>
                            № {r.matched_invoice.incoming_document_number || r.matched_invoice.iiko_document_number || '—'}
                            {' · '}{fmtDate(r.matched_invoice.date || null)}
                            {' · '}{money(r.matched_invoice.total)}
                          </>
                        ) : '—'}
                      </td>
                      <td className="py-2.5 px-3"><StatusBadge status={r.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {(result.extra_invoices || []).length > 0 && (
              <div className="card p-5">
                <div className="font-medium text-brand-dark mb-3">
                  Накладные в iiko за период, которых нет в присланном акте
                </div>
                <div className="space-y-2">
                  {result.extra_invoices!.map(inv => (
                    <div key={inv.iiko_id} className="flex justify-between text-sm border border-brand-border rounded-lg px-3 py-2">
                      <span className="text-brand-dark">
                        № {inv.incoming_document_number || inv.document_number || inv.iiko_id} от {fmtDate(inv.date)}
                      </span>
                      <span className="badge-warn">{money(inv.total)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </CoLayout>
  )
}
