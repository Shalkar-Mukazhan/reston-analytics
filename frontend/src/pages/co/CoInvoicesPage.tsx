import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import coApi from '../../api/coClient'
import CoLayout from './CoLayout'
import {
  ScanLine, Upload, X, Loader2, AlertCircle, AlertTriangle,
  CheckCircle2, Send, ChevronRight, RefreshCw, Trash2, Pencil,
} from 'lucide-react'

interface OcrItem {
  line_number?: number
  supplier_code: string
  name: string
  unit: string
  quantity: number
  price_per_unit: number
  total_with_vat: number
  vat_amount: number
}
interface OcrResult {
  document?: { number?: string; date?: string }
  supplier?: { name?: string; bin_iin?: string }
  items: OcrItem[]
  totals?: { total_sum_with_vat?: number }
  confidence_score?: number
  warnings?: string[]
}
interface SavedInvoice {
  id: number
  restaurant_id: number
  warehouse_id: number
  warehouse_name: string | null
  supplier_id: number | null
  supplier_name: string | null
  supplier_bin: string | null
  invoice_date: string | null
  document_number: string | null
  uploaded_at: string
  status: string
  needs_resend: boolean
  items_count: number
  total_sum_vat: number | null
}
interface Supplier { id: number; name: string; bin: string | null; iiko_id: string | null }
interface SavedItem {
  id: number
  name: string | null
  supplier_code: string | null
  supplier_id: number | null
  quantity: number
  unit_price_vat: number | null
  total_price_vat: number | null
  iiko_product_name: string | null
  matched: boolean
  container_name: string | null
  container_count: number | null
  iiko_qty: number | null
}
interface IikoProduct { id: number; name: string; unit: string | null }
interface Restaurant { id: number; name: string }
interface Warehouse { id: number; name: string }

function ItemsModal({ invoice, onClose, onMappingCreated }: {
  invoice: SavedInvoice
  onClose: () => void
  onMappingCreated: () => void
}) {
  const [items, setItems] = useState<SavedItem[]>([])
  const [loading, setLoading] = useState(true)

  // inline mapping state
  const [mappingItemId, setMappingItemId] = useState<number | null>(null)
  const [mapQuery, setMapQuery] = useState('')
  const [mapResults, setMapResults] = useState<IikoProduct[]>([])
  const [mapSelected, setMapSelected] = useState<IikoProduct | null>(null)
  const [mapSaving, setMapSaving] = useState(false)
  const [mapError, setMapError] = useState('')
  const [savedCount, setSavedCount] = useState(0)

  const fmt = (n: number | null | undefined) =>
    n == null ? '—' : n.toLocaleString('ru-RU', { minimumFractionDigits: 2 })

  useEffect(() => {
    coApi.get(`/invoices/${invoice.id}/items`).then(r => { setItems(r.data); setLoading(false) })
  }, [invoice.id])

  useEffect(() => {
    if (!mapQuery.trim() || mapSelected) { if (!mapSelected) setMapResults([]); return }
    const t = setTimeout(async () => {
      try {
        const { data } = await coApi.get('/admin/products', { params: { search: mapQuery } })
        setMapResults(data)
      } catch { setMapResults([]) }
    }, 300)
    return () => clearTimeout(t)
  }, [mapQuery, mapSelected])

  const openMapping = (item: SavedItem) => {
    setMappingItemId(item.id)
    setMapQuery('')
    setMapResults([])
    setMapSelected(null)
    setMapError('')
  }

  const cancelMapping = () => {
    setMappingItemId(null); setMapQuery(''); setMapResults([])
    setMapSelected(null); setMapError('')
  }

  const confirmMapping = async () => {
    const item = items.find(i => i.id === mappingItemId)
    if (!item || !mapSelected || !item.supplier_id) return
    setMapSaving(true); setMapError('')
    try {
      await coApi.post('/admin/mappings', {
        supplier_id: item.supplier_id,
        supplier_product_name: item.name,
        supplier_product_code: item.supplier_code || undefined,
        product_id: mapSelected.id,
      })
      setItems(prev => prev.map(i => i.id === item.id
        ? { ...i, matched: true, iiko_product_name: mapSelected.name }
        : i
      ))
      setSavedCount(c => c + 1)
      onMappingCreated()
      cancelMapping()
    } catch (e: any) {
      setMapError(e.response?.data?.detail || 'Ошибка сохранения')
    } finally { setMapSaving(false) }
  }

  const NameCell = ({ item }: { item: SavedItem }) => (
    <span className="font-medium text-brand-dark">{item.name || '—'}</span>
  )

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 backdrop-blur-sm sm:p-4">
      <div className="bg-white rounded-t-2xl sm:rounded-2xl shadow-2xl w-full sm:max-w-6xl max-h-[92vh] sm:max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-4 sm:px-6 py-4 border-b border-brand-border shrink-0">
          <div className="min-w-0">
            <h2 className="font-bold text-brand-dark text-base sm:text-lg">Накладная #{invoice.id}</h2>
            <p className="text-brand-muted text-xs sm:text-sm mt-0.5 truncate">
              {invoice.warehouse_name}
              {invoice.supplier_name
                ? <> · {invoice.supplier_name}{invoice.supplier_bin && <span className="font-mono ml-1 text-brand-border">{invoice.supplier_bin}</span>}</>
                : <span className="text-brand-red ml-1">· поставщик не выбран</span>}
              {invoice.invoice_date && ` · ${invoice.invoice_date}`}
            </p>
          </div>
          <div className="flex items-center gap-3 shrink-0 ml-3">
            {invoice.total_sum_vat != null && (
              <span className="text-sm font-semibold text-brand-dark tabular-nums hidden sm:block">
                {invoice.total_sum_vat.toLocaleString('ru-RU', { minimumFractionDigits: 2 })} ₸
              </span>
            )}
            <button onClick={onClose} className="p-2 rounded-lg hover:bg-brand-bg transition-colors">
              <X size={18} className="text-brand-muted" />
            </button>
          </div>
        </div>
        {invoice.total_sum_vat != null && (
          <div className="sm:hidden px-4 py-2 border-b border-brand-border bg-brand-bg/50 text-sm font-semibold text-brand-dark tabular-nums">
            Итого: {invoice.total_sum_vat.toLocaleString('ru-RU', { minimumFractionDigits: 2 })} ₸
          </div>
        )}
        {/* Панель привязки товара */}
        {mappingItemId !== null && (() => {
          const item = items.find(i => i.id === mappingItemId)!
          return (
            <div className="border-b border-orange-200 bg-orange-50 px-4 sm:px-6 py-3 shrink-0">
              <div className="text-xs font-medium text-orange-800 mb-2 flex items-center gap-1.5">
                <AlertCircle size={12} />
                Привязать товар: <span className="font-semibold">{item.supplier_code && `[${item.supplier_code}] `}{item.name}</span>
              </div>
              <div className="flex items-start gap-2 flex-wrap sm:flex-nowrap">
                <div className="relative flex-1 min-w-[200px]">
                  <input
                    autoFocus
                    value={mapQuery}
                    onChange={e => { setMapQuery(e.target.value); setMapSelected(null) }}
                    placeholder="Начните вводить название товара iiko..."
                    className="input text-sm w-full"
                  />
                  {mapResults.length > 0 && !mapSelected && (
                    <div className="absolute z-30 top-full mt-1 left-0 right-0 bg-white border border-brand-border rounded-lg shadow-xl max-h-52 overflow-y-auto">
                      {mapResults.map(p => (
                        <button key={p.id} onMouseDown={() => { setMapSelected(p); setMapQuery(p.name); setMapResults([]) }}
                          className="w-full text-left px-3 py-2.5 text-sm text-brand-dark hover:bg-brand-bg flex items-center justify-between border-b border-brand-border/40 last:border-0">
                          <span>{p.name}</span>
                          {p.unit && <span className="text-xs text-brand-muted ml-2 shrink-0">{p.unit}</span>}
                        </button>
                      ))}
                    </div>
                  )}
                  {mapQuery.length > 1 && mapResults.length === 0 && !mapSelected && (
                    <div className="absolute z-30 top-full mt-1 left-0 right-0 bg-white border border-brand-border rounded-lg shadow-sm px-3 py-2 text-xs text-brand-muted">
                      Ничего не найдено
                    </div>
                  )}
                </div>
                <button
                  onClick={confirmMapping}
                  disabled={!mapSelected || mapSaving}
                  className="btn-primary text-sm shrink-0 disabled:opacity-50"
                >
                  {mapSaving ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                  Сохранить
                </button>
                <button onClick={cancelMapping} className="btn-secondary text-sm shrink-0">
                  <X size={14} />Отмена
                </button>
              </div>
              {mapError && <p className="text-xs text-red-600 mt-1.5">{mapError}</p>}
            </div>
          )
        })()}

        {savedCount > 0 && (
          <div className="shrink-0 px-4 sm:px-6 py-2 bg-green-50 border-b border-green-200 flex items-center gap-2 text-xs text-green-800">
            <CheckCircle2 size={13} />
            Сохранено привязок: {savedCount}. Кнопка «В iiko» теперь активна для повторной отправки.
          </div>
        )}

        <div className="flex-1 overflow-auto">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 size={24} className="animate-spin text-brand-muted" />
            </div>
          ) : (
            <>
              {/* Desktop table */}
              <div className="hidden sm:block overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-white z-10">
                    <tr className="border-b border-brand-border">
                      {['', 'Код', 'Наименование', 'Товар iiko', 'Кол-во', 'Кейсовка', 'iiko кол.', 'Цена', 'Сумма'].map(h => (
                        <th key={h} className="text-left py-2 px-3 text-brand-muted font-medium text-xs uppercase tracking-wide whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {items.map(item => (
                      <tr key={item.id} className={`border-b border-brand-border/50 ${!item.matched ? 'bg-red-50/40' : 'hover:bg-brand-bg/60'} ${mappingItemId === item.id ? 'ring-2 ring-orange-300 ring-inset' : ''}`}>
                        <td className="py-2.5 px-3">
                          {item.matched
                            ? <CheckCircle2 size={14} className="text-green-500" />
                            : <AlertCircle size={14} className="text-brand-red" />}
                        </td>
                        <td className="py-2.5 px-3 font-mono text-xs text-brand-muted whitespace-nowrap">
                          {item.supplier_code || <span className="text-brand-border">—</span>}
                        </td>
                        <td className="py-2.5 px-3 max-w-[200px]"><NameCell item={item} /></td>
                        <td className="py-2.5 px-3 text-xs">
                          {item.matched
                            ? <span className="text-green-700">{item.iiko_product_name}</span>
                            : (
                              <button onClick={() => mappingItemId === item.id ? cancelMapping() : openMapping(item)}
                                className="inline-flex items-center gap-1 text-xs text-brand-red hover:text-orange-600 font-medium hover:underline">
                                <AlertCircle size={11} />
                                {mappingItemId === item.id ? 'Отмена' : 'Привязать'}
                              </button>
                            )}
                        </td>
                        <td className="py-2.5 px-3 text-right tabular-nums whitespace-nowrap">{(item.quantity ?? 0).toLocaleString('ru-RU', { maximumFractionDigits: 3 })}</td>
                        <td className="py-2.5 px-3 text-center">
                          {item.container_name
                            ? <span className="text-xs bg-blue-50 border border-blue-200 text-blue-700 px-2 py-0.5 rounded-full whitespace-nowrap">{item.container_name} ×{item.container_count}</span>
                            : <span className="text-brand-muted text-xs">—</span>}
                        </td>
                        <td className="py-2.5 px-3 text-right tabular-nums whitespace-nowrap">
                          {item.iiko_qty != null
                            ? <span className="font-medium text-brand-dark">{item.iiko_qty.toLocaleString('ru-RU', { maximumFractionDigits: 3 })}</span>
                            : <span className="text-brand-muted text-xs">—</span>}
                        </td>
                        <td className="py-2.5 px-3 text-right tabular-nums whitespace-nowrap">{fmt(item.unit_price_vat)}</td>
                        <td className="py-2.5 px-3 text-right tabular-nums font-medium whitespace-nowrap">{fmt(item.total_price_vat)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {/* Mobile cards */}
              <div className="sm:hidden divide-y divide-brand-border">
                {items.map(item => (
                  <div key={item.id} className={`px-4 py-3 ${!item.matched ? 'bg-red-50/40' : ''} ${mappingItemId === item.id ? 'ring-2 ring-orange-300 ring-inset' : ''}`}>
                    <div className="flex items-start justify-between gap-2 mb-1">
                      <div className="flex items-start gap-1.5 min-w-0">
                        {item.matched
                          ? <CheckCircle2 size={13} className="text-green-500 shrink-0 mt-0.5" />
                          : <AlertCircle size={13} className="text-brand-red shrink-0 mt-0.5" />}
                        <div className="min-w-0">
                          {item.supplier_code && (
                            <span className="inline-block font-mono text-xs text-brand-muted bg-brand-bg border border-brand-border px-1 py-0.5 rounded mr-1 mb-0.5">{item.supplier_code}</span>
                          )}
                          <NameCell item={item} />
                        </div>
                      </div>
                      <span className="font-semibold text-brand-dark tabular-nums text-sm shrink-0">{fmt(item.total_price_vat)} ₸</span>
                    </div>
                    <div className="text-xs ml-5 mt-1">
                      {item.matched
                        ? <span className="text-green-700">{item.iiko_product_name}</span>
                        : (
                          <button onClick={() => mappingItemId === item.id ? cancelMapping() : openMapping(item)}
                            className="text-brand-red hover:underline flex items-center gap-1 font-medium">
                            <AlertCircle size={11} />
                            {mappingItemId === item.id ? 'Отмена привязки' : 'Привязать товар'}
                          </button>
                        )}
                    </div>
                    <div className="flex items-center gap-3 mt-1.5 ml-5 text-xs text-brand-muted flex-wrap">
                      <span>Кол-во: <span className="text-brand-dark tabular-nums">{(item.quantity ?? 0).toLocaleString('ru-RU', { maximumFractionDigits: 3 })}</span></span>
                      <span>Цена: <span className="text-brand-dark tabular-nums">{fmt(item.unit_price_vat)}</span></span>
                      {item.iiko_qty != null && <span>iiko: <span className="text-brand-dark tabular-nums font-medium">{item.iiko_qty.toLocaleString('ru-RU', { maximumFractionDigits: 3 })}</span></span>}
                      {item.container_name && (
                        <span className="bg-blue-50 border border-blue-200 text-blue-700 px-1.5 py-0.5 rounded-full whitespace-nowrap">{item.container_name} ×{item.container_count}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function PostToIikoModal({ invoice, onClose, onSent }: { invoice: SavedInvoice; onClose: () => void; onSent: () => void }) {
  const [dateIncoming, setDateIncoming] = useState(() => {
    const d = new Date()
    return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${d.getFullYear()}`
  })
  const [posting, setPosting] = useState(false)
  const [result, setResult] = useState<{ success?: boolean; documentNumber?: string; skipped?: string[] } | null>(null)
  const [error, setError] = useState('')
  const [cooldown, setCooldown] = useState(0)

  useEffect(() => {
    if (cooldown <= 0) return
    const t = setTimeout(() => setCooldown(c => c - 1), 1000)
    return () => clearTimeout(t)
  }, [cooldown])

  // когда таймер истёк после успеха — сбрасываем чтобы можно было отправить снова
  useEffect(() => {
    if (cooldown === 0 && result?.success) setResult(null)
  }, [cooldown])

  const post = async () => {
    setPosting(true); setError(''); setResult(null)
    try {
      const res = await coApi.post(`/invoices/${invoice.id}/post-to-iiko`, { date_incoming: dateIncoming })
      setResult(res.data)
      setCooldown(7)
      onSent()
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message)
    } finally { setPosting(false) }
  }

  const yearWarning = (() => {
    const parts = dateIncoming.split('.')
    const year = parts.length === 3 ? parseInt(parts[2]) : null
    const cur = new Date().getFullYear()
    return year && (year < cur - 1 || year > cur + 1) ? year : null
  })()

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-brand-border">
          <h2 className="font-bold text-brand-dark text-lg">Отправить в iiko</h2>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-brand-bg transition-colors"><X size={18} className="text-brand-muted" /></button>
        </div>
        <div className="px-6 py-5 space-y-4">
          <p className="text-sm text-brand-muted">{invoice.warehouse_name} · {invoice.supplier_name}</p>
          <div>
            <label className="text-xs font-medium text-brand-muted uppercase tracking-wide block mb-1.5">Дата прихода (ДД.ММ.ГГГГ)</label>
            <input type="text" className="input" placeholder="23.04.2026" value={dateIncoming} onChange={e => setDateIncoming(e.target.value)} />
            {yearWarning && (
              <div className="mt-1.5 flex items-start gap-1.5 p-2 rounded-lg bg-yellow-50 border border-yellow-300">
                <AlertTriangle size={13} className="text-yellow-600 flex-shrink-0 mt-0.5" />
                <span className="text-xs text-yellow-800">Год <strong>{yearWarning}</strong> выглядит как опечатка — проверьте дату</span>
              </div>
            )}
          </div>
          {error && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-red-50 border border-red-100">
              <AlertCircle size={14} className="text-brand-red flex-shrink-0 mt-0.5" />
              <span className="text-brand-red text-sm">{error}</span>
            </div>
          )}
          {result?.success && (
            <div className="p-3 rounded-lg bg-green-50 border border-green-200 text-green-800 text-sm">
              <div className="flex items-center gap-2 font-medium">
                <CheckCircle2 size={15} />
                Отправлено! Документ: {result.documentNumber}
              </div>
              {result.skipped && result.skipped.length > 0 && (
                <p className="text-xs mt-1 text-yellow-700">Пропущено (нет маппинга): {result.skipped.join(', ')}</p>
              )}
            </div>
          )}
          <div className="flex gap-2 justify-end pt-2">
            <button className="btn-secondary" onClick={onClose}>Закрыть</button>
            <button
              className="btn-primary disabled:opacity-60"
              onClick={post}
              disabled={posting || !dateIncoming || cooldown > 0}
            >
              {posting
                ? <><Loader2 size={14} className="animate-spin" />Отправляем...</>
                : cooldown > 0
                  ? <><Loader2 size={14} className="animate-spin text-green-300" />Повтор через {cooldown}с</>
                  : result?.success
                    ? <><Send size={14} />Отправить снова</>
                    : <><Send size={14} />Отправить</>
              }
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function CoInvoicesPage() {
  const navigate = useNavigate()
  const [me, setMe] = useState<{ name: string; role: string } | null>(null)
  const [restaurants, setRestaurants] = useState<Restaurant[]>([])
  const [restaurantId, setRestaurantId] = useState('')
  const [warehouses, setWarehouses] = useState<Warehouse[]>([])
  const [warehouseId, setWarehouseId] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [parsing, setParsing] = useState(false)
  const [parseError, setParseError] = useState('')
  const [ocrResult, setOcrResult] = useState<OcrResult | null>(null)
  const [editItems, setEditItems] = useState<OcrItem[]>([])
  const [docNumber, setDocNumber] = useState('')
  const [docDate, setDocDate] = useState('')
  const [supplierName, setSupplierName] = useState('')
  const [supplierBin, setSupplierBin] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [invoices, setInvoices] = useState<SavedInvoice[]>([])
  const [loadingInvoices, setLoadingInvoices] = useState(true)
  const [selectedInvoice, setSelectedInvoice] = useState<SavedInvoice | null>(null)
  const [postingInvoice, setPostingInvoice] = useState<SavedInvoice | null>(null)
  const [editingWarehouseInvId, setEditingWarehouseInvId] = useState<number | null>(null)
  const [editWarehouses, setEditWarehouses] = useState<Warehouse[]>([])
  const [editWarehouseLoading, setEditWarehouseLoading] = useState(false)
  const [savingWarehouse, setSavingWarehouse] = useState(false)
  const [editingSupplierInvId, setEditingSupplierInvId] = useState<number | null>(null)
  const [supplierPickerSearch, setSupplierPickerSearch] = useState('')
  const [supplierPickerSelected, setSupplierPickerSelected] = useState<Supplier | null>(null)
  const [allSuppliers, setAllSuppliers] = useState<Supplier[]>([])
  const [suppliersLoaded, setSuppliersLoaded] = useState(false)
  const [savingSupplier, setSavingSupplier] = useState(false)
  const [deleteInvoiceModal, setDeleteInvoiceModal] = useState<SavedInvoice | null>(null)
  const [deleteLoading, setDeleteLoading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    coApi.get('/auth/me').then(r => {
      setMe(r.data)
      coApi.get('/admin/restaurants').then(res => {
        setRestaurants(res.data)
        if (res.data.length === 1) {
          setRestaurantId(String(res.data[0].id))
          coApi.get(`/admin/restaurants/${res.data[0].id}/warehouses`, { params: { active_only: true } }).then(w => {
            setWarehouses(w.data)
            if (w.data.length === 1) setWarehouseId(String(w.data[0].id))
          })
        }
      })
    }).catch(() => navigate('/login'))
    loadInvoices()
  }, [])

  const onRestaurantChange = async (rid: string) => {
    setRestaurantId(rid); setWarehouseId(''); setWarehouses([])
    if (rid) {
      const { data } = await coApi.get(`/admin/restaurants/${rid}/warehouses`, { params: { active_only: true } })
      setWarehouses(data)
      if (data.length === 1) setWarehouseId(String(data[0].id))
    }
  }

  const loadInvoices = async () => {
    setLoadingInvoices(true)
    try { setInvoices((await coApi.get('/invoices/')).data) }
    finally { setLoadingInvoices(false) }
  }

  const parse = async () => {
    if (!files.length || !restaurantId) return
    setParsing(true); setParseError(''); setOcrResult(null)
    try {
      const form = new FormData()
      files.forEach(f => form.append('files', f))
      form.append('restaurant_id', restaurantId)
      const { data } = await coApi.post('/invoices/ocr-parse', form, { headers: { 'Content-Type': 'multipart/form-data' } })
      setOcrResult(data)
      setEditItems((data.items || []).map((item: OcrItem) => ({ ...item })))
      setDocNumber(data.document?.number || '')
      setDocDate(data.document?.date || '')
      setSupplierName(data.supplier?.name || '')
      setSupplierBin(data.supplier?.bin_iin || '')
    } catch (e: any) {
      setParseError(e.response?.data?.detail || e.message)
    } finally { setParsing(false) }
  }

  const resetOcr = () => {
    setOcrResult(null); setEditItems([]); setFiles([]); setParseError(''); setSaveError('')
    if (fileRef.current) fileRef.current.value = ''
  }

  const updateItem = (idx: number, field: keyof OcrItem, value: string) => {
    setEditItems(prev => {
      const next = [...prev]
      const item = { ...next[idx] }
      if (['quantity', 'price_per_unit', 'total_with_vat', 'vat_amount'].includes(field)) {
        (item as any)[field] = parseFloat(value) || 0
      } else {
        (item as any)[field] = value
      }
      if (field === 'quantity' || field === 'price_per_unit') {
        item.total_with_vat = parseFloat((item.quantity * item.price_per_unit).toFixed(2))
      }
      next[idx] = item
      return next
    })
  }

  const removeItem = (idx: number) => setEditItems(prev => prev.filter((_, i) => i !== idx))

  const save = async () => {
    if (!editItems.length) return
    setSaving(true); setSaveError('')
    try {
      await coApi.post('/invoices/ocr-confirm', {
        restaurant_id: parseInt(restaurantId),
        warehouse_id: parseInt(warehouseId),
        document_number: docNumber || undefined,
        document_date: docDate || undefined,
        supplier_name: supplierName || undefined,
        supplier_bin: supplierBin || undefined,
        items: editItems,
        total_sum_with_vat: editItems.reduce((s, i) => s + (i.total_with_vat || 0), 0),
      })
      resetOcr()
      await loadInvoices()
    } catch (e: any) {
      setSaveError(e.response?.data?.detail || e.message)
    } finally { setSaving(false) }
  }

  const totalEdit = editItems.reduce((s, i) => s + (i.total_with_vat || 0), 0)

  const startEditWarehouse = async (inv: SavedInvoice) => {
    setEditingWarehouseInvId(inv.id)
    setEditWarehouseLoading(true)
    try {
      const { data } = await coApi.get(`/admin/restaurants/${inv.restaurant_id}/warehouses`, { params: { active_only: true } })
      setEditWarehouses(data)
    } finally {
      setEditWarehouseLoading(false)
    }
  }

  const saveWarehouse = async (inv: SavedInvoice, newWarehouseId: number) => {
    if (newWarehouseId === inv.warehouse_id) { setEditingWarehouseInvId(null); return }
    setSavingWarehouse(true)
    try {
      await coApi.patch(`/invoices/${inv.id}`, { warehouse_id: newWarehouseId })
      const wh = editWarehouses.find(w => w.id === newWarehouseId)
      setInvoices(prev => prev.map(i => i.id === inv.id
        ? { ...i, warehouse_id: newWarehouseId, warehouse_name: wh?.name ?? null }
        : i
      ))
      setEditingWarehouseInvId(null)
    } catch { /* ignore */ }
    finally { setSavingWarehouse(false) }
  }

  const startEditSupplier = async (inv: SavedInvoice) => {
    setEditingSupplierInvId(inv.id)
    setSupplierPickerSearch('')
    setSupplierPickerSelected(null)
    if (!suppliersLoaded) {
      try {
        const { data } = await coApi.get('/admin/suppliers')
        setAllSuppliers(data)
        setSuppliersLoaded(true)
      } catch { /* ignore */ }
    }
  }

  const cancelSupplierPicker = () => {
    setEditingSupplierInvId(null)
    setSupplierPickerSearch('')
    setSupplierPickerSelected(null)
  }

  const confirmSupplierPicker = async () => {
    if (!editingSupplierInvId || !supplierPickerSelected) return
    setSavingSupplier(true)
    try {
      await coApi.patch(`/invoices/${editingSupplierInvId}`, { supplier_id: supplierPickerSelected.id })
      setInvoices(prev => prev.map(i => i.id === editingSupplierInvId
        ? { ...i, supplier_id: supplierPickerSelected.id, supplier_name: supplierPickerSelected.name, supplier_bin: supplierPickerSelected.bin }
        : i
      ))
      cancelSupplierPicker()
    } catch { /* ignore */ }
    finally { setSavingSupplier(false) }
  }

  const deleteInvoice = async () => {
    if (!deleteInvoiceModal) return
    setDeleteLoading(true)
    try {
      await coApi.delete(`/invoices/${deleteInvoiceModal.id}`)
      setInvoices(prev => prev.filter(i => i.id !== deleteInvoiceModal.id))
      setDeleteInvoiceModal(null)
    } catch { /* ignore */ }
    finally { setDeleteLoading(false) }
  }

  const logout = () => {
    localStorage.removeItem('co_access_token')
    localStorage.removeItem('co_refresh_token')
    navigate('/login')
  }

  return (
    <CoLayout me={me} onLogout={logout}>
    <div className="p-4 sm:p-6 max-w-7xl mx-auto">
      {/* Шаг 1 — загрузка */}
      {!ocrResult ? (
        <div className="card p-4 sm:p-5 mb-6">
          <h2 className="font-semibold text-brand-dark mb-4 flex items-center gap-2">
            <Upload size={16} className="text-brand-yellow" />
            Загрузить фото или PDF накладной
          </h2>
          <div className="flex flex-col sm:flex-row flex-wrap gap-3 sm:items-end">
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-brand-muted uppercase tracking-wide">Ресторан</label>
              <select className="input w-full sm:min-w-[200px]" value={restaurantId} onChange={e => onRestaurantChange(e.target.value)}>
                <option value="">Выберите ресторан</option>
                {restaurants.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-brand-muted uppercase tracking-wide">Склад</label>
              <select className="input w-full sm:min-w-[180px]" value={warehouseId} onChange={e => setWarehouseId(e.target.value)} disabled={!restaurantId}>
                <option value="">Выберите склад</option>
                {warehouses.map(w => <option key={w.id} value={w.id}>{w.name}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-brand-muted uppercase tracking-wide">Фото или PDF — до 5 файлов</label>
              <input
                ref={fileRef}
                type="file"
                accept=".jpg,.jpeg,.png,.webp,.pdf"
                multiple
                className="input w-full cursor-pointer file:mr-3 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:font-medium file:bg-brand-yellow/10 file:text-brand-dark hover:file:bg-brand-yellow/20"
                onChange={e => setFiles(Array.from(e.target.files ?? []))}
              />
              {files.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {files.map((f, i) => (
                    <span key={i} className="inline-flex items-center gap-1 text-xs bg-brand-bg border border-brand-border rounded px-2 py-0.5 text-brand-dark">
                      {f.name}
                      <button onClick={() => setFiles(p => p.filter((_, j) => j !== i))} className="text-brand-muted hover:text-brand-red ml-0.5"><X size={11} /></button>
                    </span>
                  ))}
                </div>
              )}
            </div>
            <button className="btn-primary w-full sm:w-auto" onClick={parse} disabled={parsing || !files.length || !restaurantId || !warehouseId}>
              {parsing
                ? <><Loader2 size={15} className="animate-spin" />Распознаём...</>
                : <><ScanLine size={15} />{files.length > 1 ? `Распознать (${files.length} стр.)` : 'Распознать'}</>}
            </button>
          </div>

          {parsing && (
            <div className="mt-4 flex items-center gap-3 p-4 rounded-xl bg-brand-bg border border-brand-border">
              <Loader2 size={18} className="animate-spin text-brand-yellow flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-brand-dark">Анализируем накладную...</p>
                <p className="text-xs text-brand-muted mt-0.5">Claude читает документ — обычно 5–15 секунд</p>
              </div>
            </div>
          )}
          {parseError && (
            <div className="mt-3 flex items-start gap-2 p-3 rounded-lg bg-red-50 border border-red-100">
              <AlertCircle size={15} className="text-brand-red flex-shrink-0 mt-0.5" />
              <span className="text-brand-red text-sm">{parseError}</span>
            </div>
          )}
        </div>
      ) : (
        // Шаг 2 — подтверждение
        <div className="card mb-6">
          <div className="flex items-center justify-between px-5 py-4 border-b border-brand-border">
            <div>
              <h2 className="font-semibold text-brand-dark flex items-center gap-2">
                <CheckCircle2 size={16} className="text-green-500" />
                Накладная распознана — проверьте данные
              </h2>
              {ocrResult.confidence_score != null && (
                <p className="text-xs text-brand-muted mt-0.5">
                  Уверенность: {Math.round(ocrResult.confidence_score * 100)}%
                  {ocrResult.confidence_score < 0.8 && ' — рекомендуем тщательно проверить'}
                </p>
              )}
            </div>
            <button onClick={resetOcr} className="p-2 rounded-lg hover:bg-brand-bg transition-colors"><X size={18} className="text-brand-muted" /></button>
          </div>

          {ocrResult.warnings && ocrResult.warnings.length > 0 && (
            <div className="mx-5 mt-4 flex flex-col gap-1.5">
              {ocrResult.warnings.map((w, i) => (
                <div key={i} className="flex items-start gap-2 p-2.5 rounded-lg bg-yellow-50 border border-yellow-200">
                  <AlertTriangle size={13} className="text-yellow-600 flex-shrink-0 mt-0.5" />
                  <span className="text-yellow-800 text-xs">{w}</span>
                </div>
              ))}
            </div>
          )}

          <div className="px-5 pt-4 pb-2 flex flex-wrap gap-3">
            {[
              { label: '№ документа', value: docNumber, set: setDocNumber, ph: 'УТ-4301', cls: 'w-36' },
              { label: 'Поставщик', value: supplierName, set: setSupplierName, ph: 'ТОО Поставщик', cls: 'flex-1 min-w-[200px]' },
              { label: 'БИН/ИИН', value: supplierBin, set: setSupplierBin, ph: '200640031528', cls: 'w-36 font-mono' },
            ].map(f => (
              <div key={f.label} className="flex flex-col gap-1">
                <label className="text-xs text-brand-muted uppercase tracking-wide font-medium">{f.label}</label>
                <input className={`input ${f.cls}`} value={f.value} onChange={e => f.set(e.target.value)} placeholder={f.ph} />
              </div>
            ))}
          </div>

          <div className="overflow-x-auto px-5 pb-2">
            <table className="w-full text-sm mt-2">
              <thead>
                <tr className="border-b border-brand-border">
                  {['Код поставщика', 'Наименование', 'Ед.', 'Кол-во', 'Цена (с НДС)', 'Сумма (с НДС)', 'НДС', ''].map(h => (
                    <th key={h} className="text-left py-2 px-2 text-brand-muted font-medium text-xs uppercase tracking-wide whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {editItems.map((item, idx) => (
                  <tr key={idx} className="border-b border-brand-border/50 hover:bg-brand-bg/40">
                    <td className="py-1.5 px-2"><input className="input input-sm w-28 font-mono text-xs" value={item.supplier_code} onChange={e => updateItem(idx, 'supplier_code', e.target.value)} /></td>
                    <td className="py-1.5 px-2"><input className="input input-sm w-48" value={item.name} onChange={e => updateItem(idx, 'name', e.target.value)} /></td>
                    <td className="py-1.5 px-2"><input className="input input-sm w-14 text-center" value={item.unit} onChange={e => updateItem(idx, 'unit', e.target.value)} /></td>
                    <td className="py-1.5 px-2"><input className="input input-sm w-20 text-right tabular-nums" type="number" step="0.001" value={item.quantity} onChange={e => updateItem(idx, 'quantity', e.target.value)} /></td>
                    <td className="py-1.5 px-2"><input className="input input-sm w-24 text-right tabular-nums" type="number" step="0.01" value={item.price_per_unit} onChange={e => updateItem(idx, 'price_per_unit', e.target.value)} /></td>
                    <td className="py-1.5 px-2"><input className="input input-sm w-24 text-right tabular-nums" type="number" step="0.01" value={item.total_with_vat} onChange={e => updateItem(idx, 'total_with_vat', e.target.value)} /></td>
                    <td className="py-1.5 px-2"><input className="input input-sm w-20 text-right tabular-nums" type="number" step="0.01" value={item.vat_amount} onChange={e => updateItem(idx, 'vat_amount', e.target.value)} /></td>
                    <td className="py-1.5 px-2"><button onClick={() => removeItem(idx)} className="p-1.5 rounded hover:bg-red-50 text-brand-muted hover:text-brand-red transition-colors"><Trash2 size={13} /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="px-5 py-4 border-t border-brand-border flex items-center justify-between gap-4 flex-wrap">
            <div className="text-sm text-brand-dark">
              <span className="text-brand-muted">Итого ({editItems.length} поз.):</span>{' '}
              <span className="font-bold text-lg">{totalEdit.toLocaleString('ru-RU', { minimumFractionDigits: 2 })} ₸</span>
            </div>
            <div className="flex items-center gap-2">
              {saveError && <span className="text-brand-red text-xs">{saveError}</span>}
              <button className="btn-secondary" onClick={resetOcr}>Отменить</button>
              <button className="btn-primary" onClick={save} disabled={saving || editItems.length === 0}>
                {saving ? <><Loader2 size={14} className="animate-spin" />Сохраняем...</> : <><CheckCircle2 size={14} />Сохранить накладную</>}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Список */}
      <div className="card">
        <div className="flex items-center justify-between px-5 py-4 border-b border-brand-border">
          <h2 className="font-semibold text-brand-dark flex items-center gap-2">
            <ScanLine size={16} className="text-brand-yellow" /> История накладных
          </h2>
          <button className="btn-secondary text-xs py-1.5 px-3" onClick={loadInvoices} disabled={loadingInvoices}>
            <RefreshCw size={13} className={loadingInvoices ? 'animate-spin' : ''} /> Обновить
          </button>
        </div>

        {loadingInvoices && invoices.length === 0 ? (
          <div className="flex items-center justify-center py-16"><Loader2 size={24} className="animate-spin text-brand-muted" /></div>
        ) : invoices.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-brand-muted">
            <ScanLine size={40} className="text-brand-border mb-3" />
            <p className="text-sm">Накладных пока нет</p>
            <p className="text-xs mt-1">Загрузите первое фото или PDF выше</p>
          </div>
        ) : (
          <>
            {/* Панель выбора поставщика */}
            {editingSupplierInvId !== null && (() => {
              const inv = invoices.find(i => i.id === editingSupplierInvId)!
              const filtered = allSuppliers.filter(s =>
                s.name.toLowerCase().includes(supplierPickerSearch.toLowerCase()) ||
                (s.bin || '').includes(supplierPickerSearch)
              )
              return (
                <div className="border-b border-orange-200 bg-orange-50 px-4 sm:px-6 py-3">
                  <div className="text-xs font-medium text-orange-800 mb-2 flex items-center gap-1.5">
                    <AlertCircle size={12} />
                    Выбрать поставщика для накладной
                    {inv.document_number
                      ? <span className="font-mono">№{inv.document_number}</span>
                      : <span>#{inv.id}</span>}
                  </div>
                  <div className="flex items-start gap-2 flex-wrap sm:flex-nowrap">
                    <div className="relative flex-1 min-w-[220px]">
                      <input
                        autoFocus
                        value={supplierPickerSearch}
                        onChange={e => { setSupplierPickerSearch(e.target.value); setSupplierPickerSelected(null) }}
                        placeholder="Поиск по названию или БИН..."
                        className="input text-sm w-full"
                      />
                      {supplierPickerSearch.length > 0 && !supplierPickerSelected && (
                        filtered.length > 0 ? (
                          <div className="absolute z-30 top-full mt-1 left-0 right-0 bg-white border border-brand-border rounded-lg shadow-xl max-h-52 overflow-y-auto">
                            {filtered.slice(0, 20).map(s => (
                              <button key={s.id} onMouseDown={() => { setSupplierPickerSelected(s); setSupplierPickerSearch(s.name) }}
                                className="w-full text-left px-3 py-2.5 text-sm text-brand-dark hover:bg-brand-bg flex items-center justify-between border-b border-brand-border/40 last:border-0">
                                <span className="min-w-0 truncate">{s.name}</span>
                                {s.bin && <span className="text-xs text-brand-muted font-mono ml-2 shrink-0">{s.bin}</span>}
                              </button>
                            ))}
                          </div>
                        ) : (
                          <div className="absolute z-30 top-full mt-1 left-0 right-0 bg-white border border-brand-border rounded-lg shadow-sm px-3 py-2 text-xs text-brand-muted">
                            Ничего не найдено
                          </div>
                        )
                      )}
                    </div>
                    <button
                      onClick={confirmSupplierPicker}
                      disabled={!supplierPickerSelected || savingSupplier}
                      className="btn-primary text-sm shrink-0 disabled:opacity-50"
                    >
                      {savingSupplier ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                      Сохранить
                    </button>
                    <button onClick={cancelSupplierPicker} className="btn-secondary text-sm shrink-0">
                      <X size={14} />Отмена
                    </button>
                  </div>
                </div>
              )
            })()}
            {/* Mobile cards */}
            <div className="sm:hidden divide-y divide-brand-border">
              {invoices.map(inv => (
                <div key={inv.id} className={`px-4 py-3.5 ${editingSupplierInvId === inv.id ? 'bg-orange-50/50 ring-2 ring-inset ring-orange-200' : ''}`}>
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <div className="min-w-0">
                      {editingWarehouseInvId === inv.id ? (
                        <div className="flex items-center gap-1 mb-0.5">
                          {editWarehouseLoading ? (
                            <Loader2 size={13} className="animate-spin text-brand-muted" />
                          ) : (
                            <select
                              autoFocus
                              className="input py-0.5 text-sm max-w-[180px]"
                              defaultValue={inv.warehouse_id}
                              disabled={savingWarehouse}
                              onChange={e => saveWarehouse(inv, parseInt(e.target.value))}
                            >
                              {editWarehouses.map(w => (
                                <option key={w.id} value={w.id}>{w.name}</option>
                              ))}
                            </select>
                          )}
                          {savingWarehouse
                            ? <Loader2 size={13} className="animate-spin text-brand-muted" />
                            : <button onClick={() => setEditingWarehouseInvId(null)} className="p-1 text-brand-muted hover:text-brand-red"><X size={13} /></button>
                          }
                        </div>
                      ) : (
                        <div className="flex items-center gap-1">
                          <div className="font-medium text-brand-dark truncate">{inv.warehouse_name ?? '—'}</div>
                          <button onClick={() => startEditWarehouse(inv)} className="p-0.5 text-brand-muted hover:text-brand-dark shrink-0"><Pencil size={12} /></button>
                        </div>
                      )}
                      {inv.supplier_id ? (
                        <div className="mt-0.5">
                          <span className="text-xs text-brand-muted truncate">{inv.supplier_name}</span>
                          {inv.supplier_bin && <span className="ml-1.5 font-mono text-xs text-brand-border">{inv.supplier_bin}</span>}
                        </div>
                      ) : (
                        <button onClick={() => startEditSupplier(inv)}
                          className="mt-0.5 inline-flex items-center gap-1 text-xs text-brand-red hover:text-orange-600 font-medium hover:underline">
                          <AlertTriangle size={11} />
                          Поставщик не найден — выбрать
                        </button>
                      )}
                    </div>
                    <div className="text-right shrink-0">
                      <div className="font-semibold text-brand-dark tabular-nums text-sm">
                        {inv.total_sum_vat != null ? `${inv.total_sum_vat.toLocaleString('ru-RU', { minimumFractionDigits: 2 })} ₸` : '—'}
                      </div>
                      <div className="text-xs text-brand-muted mt-0.5">{inv.items_count} поз.</div>
                    </div>
                  </div>
                  <div className="text-xs text-brand-muted mt-1 mb-2.5">
                    {inv.document_number && <span className="mr-2 font-mono text-brand-dark font-medium">{inv.document_number}</span>}
                    {inv.invoice_date && <span className="mr-2">{inv.invoice_date}</span>}
                    <span className="text-brand-border">·</span>
                    <span className="ml-2">{new Date(inv.uploaded_at).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}</span>
                    <span className="ml-2 font-mono text-brand-border/80">#{inv.id}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button className="btn-secondary text-xs py-1.5 px-3 flex-1 justify-center" onClick={() => setSelectedInvoice(inv)}>
                      <ChevronRight size={13} />Позиции
                    </button>
                    {inv.status !== 'sent'
                      ? <button className="btn-primary text-xs py-1.5 px-3 flex-1 justify-center" onClick={() => setPostingInvoice(inv)}><Send size={13} />В iiko</button>
                      : <button className="btn-secondary text-xs py-1.5 px-3 flex-1 justify-center" onClick={() => setPostingInvoice(inv)}><Send size={13} />Повторить</button>
                    }
                    <button
                      onClick={() => setDeleteInvoiceModal(inv)}
                      className="btn-secondary text-xs py-1.5 px-2.5 shrink-0 text-brand-muted hover:text-brand-red hover:border-red-300"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
            {/* Desktop table */}
            <div className="hidden sm:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-brand-border">
                    {['#', 'Вх. номер', 'Склад', 'Поставщик', 'Дата', 'Поз.', 'Сумма', 'Загружен', ''].map(h => (
                      <th key={h} className="text-left py-3 px-3 text-brand-muted font-medium text-xs uppercase tracking-wide whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {invoices.map(inv => (
                    <tr key={inv.id} className="border-b border-brand-border/50 hover:bg-brand-bg/60 transition-colors">
                      <td className="py-3 px-3 text-brand-muted font-mono text-xs">{inv.id}</td>
                      <td className="py-3 px-3 font-mono text-xs text-brand-dark">{inv.document_number ?? <span className="text-brand-border">—</span>}</td>
                      <td className="py-3 px-3 font-medium text-brand-dark">
                        {editingWarehouseInvId === inv.id ? (
                          <div className="flex items-center gap-1">
                            {editWarehouseLoading ? (
                              <Loader2 size={13} className="animate-spin text-brand-muted" />
                            ) : (
                              <select
                                autoFocus
                                className="input py-0.5 text-sm"
                                defaultValue={inv.warehouse_id}
                                disabled={savingWarehouse}
                                onChange={e => saveWarehouse(inv, parseInt(e.target.value))}
                              >
                                {editWarehouses.map(w => (
                                  <option key={w.id} value={w.id}>{w.name}</option>
                                ))}
                              </select>
                            )}
                            {savingWarehouse
                              ? <Loader2 size={13} className="animate-spin text-brand-muted" />
                              : <button onClick={() => setEditingWarehouseInvId(null)} className="p-1 text-brand-muted hover:text-brand-red"><X size={13} /></button>
                            }
                          </div>
                        ) : (
                          <div className="flex items-center gap-1 group">
                            <span>{inv.warehouse_name ?? '—'}</span>
                            <button
                              onClick={() => startEditWarehouse(inv)}
                              className="p-0.5 rounded opacity-0 group-hover:opacity-100 text-brand-muted hover:text-brand-dark transition-opacity"
                            >
                              <Pencil size={12} />
                            </button>
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-3">
                        {inv.supplier_id ? (
                          <div>
                            <div className="text-brand-dark">{inv.supplier_name}</div>
                            {inv.supplier_bin && <div className="text-xs font-mono text-brand-muted mt-0.5">{inv.supplier_bin}</div>}
                          </div>
                        ) : (
                          <button onClick={() => startEditSupplier(inv)}
                            className="inline-flex items-center gap-1 text-xs text-brand-red hover:text-orange-600 font-medium hover:underline whitespace-nowrap">
                            <AlertTriangle size={11} />
                            Не найден — выбрать
                          </button>
                        )}
                      </td>
                      <td className="py-3 px-3 text-brand-dark whitespace-nowrap">{inv.invoice_date ?? '—'}</td>
                      <td className="py-3 px-3 text-brand-muted text-center">{inv.items_count}</td>
                      <td className="py-3 px-3 font-medium text-brand-dark tabular-nums whitespace-nowrap">
                        {inv.total_sum_vat != null ? `${inv.total_sum_vat.toLocaleString('ru-RU', { minimumFractionDigits: 2 })} ₸` : '—'}
                      </td>
                      <td className="py-3 px-3 text-brand-muted text-xs whitespace-nowrap">
                        {new Date(inv.uploaded_at).toLocaleString('ru-RU')}
                      </td>
                      <td className="py-3 px-3">
                        <div className="flex items-center gap-2 justify-end">
                          <button className="btn-secondary text-xs py-1 px-2.5" onClick={() => setSelectedInvoice(inv)}>
                            <ChevronRight size={13} />Позиции
                          </button>
                          {inv.status !== 'sent'
                            ? <button className="btn-primary text-xs py-1 px-2.5 inline-flex items-center gap-1" onClick={() => setPostingInvoice(inv)}><Send size={13} />В iiko</button>
                            : <button className="btn-secondary text-xs py-1 px-2.5 inline-flex items-center gap-1" onClick={() => setPostingInvoice(inv)}><Send size={13} />Повторить</button>
                          }
                          <button
                            onClick={() => setDeleteInvoiceModal(inv)}
                            className="btn-secondary text-xs py-1 px-2 text-brand-muted hover:text-brand-red hover:border-red-300"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      {selectedInvoice && <ItemsModal invoice={selectedInvoice} onClose={() => setSelectedInvoice(null)} onMappingCreated={loadInvoices} />}
      {postingInvoice && (
        <PostToIikoModal
          invoice={postingInvoice}
          onClose={() => setPostingInvoice(null)}
          onSent={loadInvoices}
        />
      )}
      {deleteInvoiceModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm">
            <div className="flex items-center justify-between px-6 py-4 border-b border-brand-border">
              <h2 className="font-bold text-brand-dark text-base flex items-center gap-2">
                <Trash2 size={16} className="text-brand-red" />
                Удалить накладную?
              </h2>
              <button onClick={() => setDeleteInvoiceModal(null)} className="p-2 rounded-lg hover:bg-brand-bg transition-colors">
                <X size={18} className="text-brand-muted" />
              </button>
            </div>
            <div className="px-6 py-5 space-y-3">
              <p className="text-sm text-brand-muted">Действительно хотите удалить эту накладную?</p>
              <div className="rounded-xl bg-brand-bg border border-brand-border px-4 py-3 text-sm space-y-1">
                {deleteInvoiceModal.document_number && (
                  <div className="flex justify-between gap-2">
                    <span className="text-brand-muted">Номер</span>
                    <span className="font-mono font-medium text-brand-dark">{deleteInvoiceModal.document_number}</span>
                  </div>
                )}
                <div className="flex justify-between gap-2">
                  <span className="text-brand-muted">Склад</span>
                  <span className="text-brand-dark">{deleteInvoiceModal.warehouse_name ?? '—'}</span>
                </div>
                {deleteInvoiceModal.supplier_name && (
                  <div className="flex justify-between gap-2">
                    <span className="text-brand-muted">Поставщик</span>
                    <span className="text-brand-dark truncate max-w-[180px] text-right">{deleteInvoiceModal.supplier_name}</span>
                  </div>
                )}
                {deleteInvoiceModal.total_sum_vat != null && (
                  <div className="flex justify-between gap-2">
                    <span className="text-brand-muted">Сумма</span>
                    <span className="font-semibold text-brand-dark tabular-nums">
                      {deleteInvoiceModal.total_sum_vat.toLocaleString('ru-RU', { minimumFractionDigits: 2 })} ₸
                    </span>
                  </div>
                )}
              </div>
              <p className="text-xs text-brand-red">Это действие необратимо.</p>
            </div>
            <div className="flex gap-2 px-6 pb-5">
              <button className="btn-secondary flex-1 justify-center" onClick={() => setDeleteInvoiceModal(null)} disabled={deleteLoading}>
                Отмена
              </button>
              <button
                className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-xl bg-red-600 hover:bg-red-700 text-white text-sm font-medium py-2.5 px-4 transition-colors disabled:opacity-50"
                onClick={deleteInvoice}
                disabled={deleteLoading}
              >
                {deleteLoading ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                Да, удалить
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
    </CoLayout>
  )
}
