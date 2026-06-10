import { useEffect, useRef, useState } from "react"
import api from "../api/client"
import type { Restaurant } from "../types"
import {
  ScanLine, Upload, X, Loader2, AlertCircle, AlertTriangle,
  CheckCircle2, Send, ChevronRight, Building2, RefreshCw, Trash2,
} from "lucide-react"
import { cn, formatDate } from "../lib/utils"

// ── Типы ──────────────────────────────────────────────────────────────────────

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
  recipient?: { name?: string; organization_note?: string }
  items: OcrItem[]
  totals?: { total_quantity?: number; total_sum_with_vat?: number; total_vat?: number }
  confidence_score?: number
  warnings?: string[]
}

interface SavedInvoice {
  id: number
  restaurant_id: number
  invoice_number: string
  invoice_date: string | null
  uploaded_at: string
  status: string
  error_message?: string | null
  total_sum: number | null
  total_sum_vat: number | null
  supplier_name?: string | null
  items_count?: number
}

interface SavedItem {
  id: number
  supplier_code: string
  name: string
  unit_type: string
  quantity: number
  unit_price: number | null
  unit_price_vat: number | null
  total_price: number | null
  total_price_vat: number | null
  vat_amount: number | null
  iiko_product_id: string | null
  matched: boolean
}

// ── Модальное окно: позиции накладной ─────────────────────────────────────────

function ItemsModal({ invoice, restaurantName, onClose }: {
  invoice: SavedInvoice
  restaurantName: string
  onClose: () => void
}) {
  const [items, setItems] = useState<SavedItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get(`/invoices2/${invoice.id}/items`).then((res) => {
      setItems(res.data)
      setLoading(false)
    })
  }, [invoice.id])

  const fmt = (n: number | null | undefined) =>
    n == null ? "—" : n.toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-5xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-brand-border">
          <div>
            <h2 className="font-bold text-brand-dark text-lg">Накладная #{invoice.id}</h2>
            <p className="text-brand-muted text-sm mt-0.5">
              {restaurantName} · {invoice.invoice_number}
              {invoice.invoice_date && ` · ${formatDate(invoice.invoice_date)}`}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {invoice.total_sum_vat != null && (
              <span className="text-sm font-semibold text-brand-dark">
                {invoice.total_sum_vat.toLocaleString("ru-RU", { minimumFractionDigits: 2 })} ₸
              </span>
            )}
            <button onClick={onClose} className="p-2 rounded-lg hover:bg-brand-bg transition-colors">
              <X size={18} className="text-brand-muted" />
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-auto px-6 pb-6 mt-3">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 size={24} className="animate-spin text-brand-muted" />
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-brand-border">
                  {["", "Код поставщика", "Наименование", "iiko ID", "Кол-во", "Цена (с НДС)", "Сумма (с НДС)"].map(h => (
                    <th key={h} className="text-left py-2 px-3 text-brand-muted font-medium text-xs uppercase tracking-wide whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map(item => (
                  <tr key={item.id} className={cn(
                    "border-b border-brand-border/50",
                    item.matched ? "hover:bg-brand-bg/60" : "bg-red-50/60"
                  )}>
                    <td className="py-2.5 px-3">
                      {item.matched
                        ? <CheckCircle2 size={14} className="text-green-500" />
                        : <AlertCircle size={14} className="text-brand-red" />
                      }
                    </td>
                    <td className="py-2.5 px-3 font-mono text-xs text-brand-muted">{item.supplier_code || "—"}</td>
                    <td className="py-2.5 px-3 font-medium text-brand-dark max-w-[200px]">{item.name}</td>
                    <td className="py-2.5 px-3 font-mono text-xs text-brand-muted">{item.iiko_product_id || <span className="text-brand-red">Не сопоставлен</span>}</td>
                    <td className="py-2.5 px-3 text-right tabular-nums">{(item.quantity ?? 0).toLocaleString("ru-RU", { maximumFractionDigits: 3 })}</td>
                    <td className="py-2.5 px-3 text-right tabular-nums">{fmt(item.unit_price_vat)}</td>
                    <td className="py-2.5 px-3 text-right tabular-nums font-medium">{fmt(item.total_price_vat)}</td>
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

// ── Модальное окно: отправить в iiko ─────────────────────────────────────────

function PostToIikoModal({ invoice, restaurantName, onClose, onDone }: {
  invoice: SavedInvoice
  restaurantName: string
  onClose: () => void
  onDone: () => void
}) {
  const [dateIncoming, setDateIncoming] = useState(() => {
    const d = invoice.invoice_date ? new Date(invoice.invoice_date) : new Date()
    return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.${d.getFullYear()}`
  })
  const [posting, setPosting] = useState(false)
  const [_result, setResult] = useState<{ success?: boolean; documentNumber?: string; skipped?: string[] } | null>(null)
  const [error, setError] = useState("")

  const post = async () => {
    setPosting(true)
    setError("")
    setResult(null)
    try {
      const res = await api.post(`/invoices2/${invoice.id}/post-to-iiko`, { date_incoming: dateIncoming })
      setResult(res.data)
      onDone()
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setPosting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-brand-border">
          <h2 className="font-bold text-brand-dark text-lg">Отправить в IIKO</h2>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-brand-bg transition-colors">
            <X size={18} className="text-brand-muted" />
          </button>
        </div>
        <div className="px-6 py-5 space-y-4">
          <p className="text-sm text-brand-muted">
            <span className="font-medium text-brand-dark">{restaurantName}</span> · {invoice.invoice_number}
          </p>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-brand-muted uppercase tracking-wide">Дата прихода (ДД.ММ.ГГГГ)</label>
            <input
              type="text"
              className="input"
              placeholder="23.04.2026"
              value={dateIncoming}
              onChange={(e) => setDateIncoming(e.target.value)}
            />
          </div>
          {error && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-red-50 border border-red-100">
              <AlertCircle size={14} className="text-brand-red flex-shrink-0 mt-0.5" />
              <span className="text-brand-red text-sm">{error}</span>
            </div>
          )}
          <div className="flex gap-2 justify-end pt-2">
            <button className="btn-secondary" onClick={onClose}>Отмена</button>
            <button className="btn-primary" onClick={post} disabled={posting || !dateIncoming}>
              {posting ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
              {posting ? "Отправляем..." : "Отправить"}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Главная страница ───────────────────────────────────────────────────────────

export default function Invoices2Page() {
  const [restaurants, setRestaurants] = useState<Restaurant[]>([])
  const [restaurantId, setRestaurantId] = useState("")
  const [files, setFiles] = useState<File[]>([])
  const [parsing, setParsing] = useState(false)
  const [parseError, setParseError] = useState("")

  // OCR результат — показываем для подтверждения
  const [ocrResult, setOcrResult] = useState<OcrResult | null>(null)
  const [editItems, setEditItems] = useState<OcrItem[]>([])
  const [docNumber, setDocNumber] = useState("")
  const [docDate, setDocDate] = useState("")
  const [supplierName, setSupplierName] = useState("")
  const [supplierBin, setSupplierBin] = useState("")
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState("")

  // Список сохранённых накладных
  const [invoices, setInvoices] = useState<SavedInvoice[]>([])
  const [loadingInvoices, setLoadingInvoices] = useState(true)
  const [selectedInvoice, setSelectedInvoice] = useState<SavedInvoice | null>(null)
  const [postingInvoice, setPostingInvoice] = useState<SavedInvoice | null>(null)

  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    api.get("/auth/me").then((res) => {
      setRestaurants(res.data.restaurants)
      if (res.data.restaurants.length === 1) setRestaurantId(String(res.data.restaurants[0].id))
    })
    loadInvoices()
  }, [])

  const loadInvoices = async () => {
    setLoadingInvoices(true)
    try {
      const res = await api.get("/invoices2/")
      setInvoices(res.data)
    } finally {
      setLoadingInvoices(false)
    }
  }

  const restaurantName = (id: number) =>
    restaurants.find((r) => r.id === id)?.name ?? `#${id}`

  // ── Шаг 1: Распознать фото/PDF ─────────────────────────────────────────────

  const parse = async () => {
    if (!files.length || !restaurantId) return
    setParsing(true)
    setParseError("")
    setOcrResult(null)
    try {
      const form = new FormData()
      files.forEach((f) => form.append("files", f))
      form.append("restaurant_id", restaurantId)
      const { data } = await api.post("/invoices2/ocr-parse", form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      setOcrResult(data)
      setEditItems((data.items || []).map((item: OcrItem) => ({ ...item })))
      setDocNumber(data.document?.number || "")
      setDocDate(data.document?.date || "")
      setSupplierName(data.supplier?.name || "")
      setSupplierBin(data.supplier?.bin_iin || "")
    } catch (e: any) {
      setParseError(e.response?.data?.detail || e.message)
    } finally {
      setParsing(false)
    }
  }

  const resetOcr = () => {
    setOcrResult(null)
    setEditItems([])
    setFiles([])
    setParseError("")
    setSaveError("")
    setSupplierBin("")
    if (fileRef.current) fileRef.current.value = ""
  }

  // ── Редактирование строк таблицы ───────────────────────────────────────────

  const updateItem = (idx: number, field: keyof OcrItem, value: string) => {
    setEditItems(prev => {
      const next = [...prev]
      const item = { ...next[idx] }
      if (field === "quantity" || field === "price_per_unit" || field === "total_with_vat" || field === "vat_amount") {
        (item as any)[field] = parseFloat(value) || 0
      } else {
        (item as any)[field] = value
      }
      // Пересчитываем total при изменении qty или price
      if (field === "quantity" || field === "price_per_unit") {
        item.total_with_vat = parseFloat((item.quantity * item.price_per_unit).toFixed(2))
      }
      next[idx] = item
      return next
    })
  }

  const removeItem = (idx: number) => {
    setEditItems(prev => prev.filter((_, i) => i !== idx))
  }

  // ── Шаг 2: Сохранить подтверждённую накладную ──────────────────────────────

  const save = async () => {
    if (!editItems.length) return
    setSaving(true)
    setSaveError("")
    try {
      const total = editItems.reduce((s, i) => s + (i.total_with_vat || 0), 0)
      await api.post("/invoices2/ocr-confirm", {
        restaurant_id: parseInt(restaurantId),
        document_number: docNumber || undefined,
        document_date: docDate || undefined,
        supplier_name: supplierName || undefined,
        supplier_bin_iin: supplierBin || undefined,
        items: editItems,
        total_sum_with_vat: total,
      })
      resetOcr()
      await loadInvoices()
    } catch (e: any) {
      setSaveError(e.response?.data?.detail || e.message)
    } finally {
      setSaving(false)
    }
  }

  const totalEdit = editItems.reduce((s, i) => s + (i.total_with_vat || 0), 0)

  // ──────────────────────────────────────────────────────────────────────────
  return (
    <div className="p-4 sm:p-6 max-w-6xl mx-auto">
      {/* Заголовок */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-brand-dark flex items-center gap-2">
          <ScanLine size={22} className="text-brand-yellow" />
          Накладные 2
        </h1>
        <p className="text-brand-muted text-sm mt-1">
          Загрузка накладных через фото или PDF — распознавание через AI
        </p>
      </div>

      {/* ── Блок загрузки / подтверждения ─────────────────────────────────── */}
      {!ocrResult ? (
        // Шаг 1 — загрузка файла
        <div className="card p-5 mb-6">
          <h2 className="font-semibold text-brand-dark mb-4 flex items-center gap-2">
            <Upload size={16} className="text-brand-yellow" />
            Загрузить фото или PDF накладной
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
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-brand-muted uppercase tracking-wide">
                Фото или PDF — до 5 файлов (.jpg, .png, .pdf)
              </label>
              <input
                ref={fileRef}
                type="file"
                accept=".jpg,.jpeg,.png,.webp,.pdf"
                multiple
                className="input cursor-pointer file:mr-3 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:font-medium file:bg-brand-yellow/10 file:text-brand-dark hover:file:bg-brand-yellow/20"
                onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
              />
              {files.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {files.map((f, i) => (
                    <span key={i} className="inline-flex items-center gap-1 text-xs bg-brand-bg border border-brand-border rounded px-2 py-0.5 text-brand-dark">
                      {f.name}
                      <button
                        type="button"
                        onClick={() => setFiles(prev => prev.filter((_, j) => j !== i))}
                        className="text-brand-muted hover:text-brand-red ml-0.5"
                      >
                        <X size={11} />
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>
            <button
              className="btn-primary"
              onClick={parse}
              disabled={parsing || !files.length || !restaurantId}
            >
              {parsing
                ? <><Loader2 size={15} className="animate-spin" />Распознаём...</>
                : <><ScanLine size={15} />{files.length > 1 ? `Распознать (${files.length} стр.)` : "Распознать"}</>
              }
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
        // Шаг 2 — подтверждение распознанных данных
        <div className="card mb-6">
          {/* Шапка */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-brand-border">
            <div>
              <h2 className="font-semibold text-brand-dark flex items-center gap-2">
                <CheckCircle2 size={16} className="text-green-500" />
                Накладная распознана — проверьте данные
              </h2>
              {ocrResult.confidence_score != null && (
                <p className="text-xs text-brand-muted mt-0.5">
                  Уверенность: {Math.round(ocrResult.confidence_score * 100)}%
                  {ocrResult.confidence_score < 0.8 && " — рекомендуем тщательно проверить"}
                </p>
              )}
            </div>
            <button onClick={resetOcr} className="p-2 rounded-lg hover:bg-brand-bg transition-colors" title="Отменить">
              <X size={18} className="text-brand-muted" />
            </button>
          </div>

          {/* Предупреждения OCR */}
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

          {/* Поля шапки документа */}
          <div className="px-5 pt-4 pb-2 flex flex-wrap gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-brand-muted uppercase tracking-wide font-medium">№ документа</label>
              <input
                className="input w-36"
                value={docNumber}
                onChange={(e) => setDocNumber(e.target.value)}
                placeholder="УТ-4301"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-brand-muted uppercase tracking-wide font-medium">Дата</label>
              <input
                className="input w-36"
                value={docDate}
                onChange={(e) => setDocDate(e.target.value)}
                placeholder="2026-04-21"
              />
            </div>
            <div className="flex flex-col gap-1 flex-1 min-w-[200px]">
              <label className="text-xs text-brand-muted uppercase tracking-wide font-medium">Поставщик</label>
              <input
                className="input"
                value={supplierName}
                onChange={(e) => setSupplierName(e.target.value)}
                placeholder="Baker Foods ТОО"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-brand-muted uppercase tracking-wide font-medium">БИН/ИИН</label>
              <input
                className="input w-36 font-mono"
                value={supplierBin}
                onChange={(e) => setSupplierBin(e.target.value)}
                placeholder="200640031528"
              />
            </div>
          </div>

          {/* Таблица позиций — редактируемая */}
          <div className="overflow-x-auto px-5 pb-2">
            <table className="w-full text-sm mt-2">
              <thead>
                <tr className="border-b border-brand-border">
                  {["Код поставщика", "Наименование", "Ед.", "Кол-во", "Цена (с НДС)", "Сумма (с НДС)", "НДС", ""].map(h => (
                    <th key={h} className="text-left py-2 px-2 text-brand-muted font-medium text-xs uppercase tracking-wide whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {editItems.map((item, idx) => (
                  <tr key={idx} className="border-b border-brand-border/50 hover:bg-brand-bg/40">
                    <td className="py-1.5 px-2">
                      <input
                        className="input input-sm w-28 font-mono text-xs"
                        value={item.supplier_code}
                        onChange={(e) => updateItem(idx, "supplier_code", e.target.value)}
                      />
                    </td>
                    <td className="py-1.5 px-2">
                      <input
                        className="input input-sm w-48"
                        value={item.name}
                        onChange={(e) => updateItem(idx, "name", e.target.value)}
                      />
                    </td>
                    <td className="py-1.5 px-2">
                      <input
                        className="input input-sm w-14 text-center"
                        value={item.unit}
                        onChange={(e) => updateItem(idx, "unit", e.target.value)}
                      />
                    </td>
                    <td className="py-1.5 px-2">
                      <input
                        className="input input-sm w-20 text-right tabular-nums"
                        type="number"
                        step="0.001"
                        value={item.quantity}
                        onChange={(e) => updateItem(idx, "quantity", e.target.value)}
                      />
                    </td>
                    <td className="py-1.5 px-2">
                      <input
                        className="input input-sm w-24 text-right tabular-nums"
                        type="number"
                        step="0.01"
                        value={item.price_per_unit}
                        onChange={(e) => updateItem(idx, "price_per_unit", e.target.value)}
                      />
                    </td>
                    <td className="py-1.5 px-2">
                      <input
                        className="input input-sm w-24 text-right tabular-nums"
                        type="number"
                        step="0.01"
                        value={item.total_with_vat}
                        onChange={(e) => updateItem(idx, "total_with_vat", e.target.value)}
                      />
                    </td>
                    <td className="py-1.5 px-2">
                      <input
                        className="input input-sm w-20 text-right tabular-nums"
                        type="number"
                        step="0.01"
                        value={item.vat_amount}
                        onChange={(e) => updateItem(idx, "vat_amount", e.target.value)}
                      />
                    </td>
                    <td className="py-1.5 px-2">
                      <button
                        onClick={() => removeItem(idx)}
                        className="p-1.5 rounded hover:bg-red-50 text-brand-muted hover:text-brand-red transition-colors"
                        title="Удалить строку"
                      >
                        <Trash2 size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Итого + кнопка сохранить */}
          <div className="px-5 py-4 border-t border-brand-border flex items-center justify-between gap-4 flex-wrap">
            <div className="text-sm text-brand-dark">
              <span className="text-brand-muted">Итого ({editItems.length} поз.):</span>{" "}
              <span className="font-bold text-lg">
                {totalEdit.toLocaleString("ru-RU", { minimumFractionDigits: 2 })} ₸
              </span>
            </div>
            <div className="flex items-center gap-2">
              {saveError && (
                <span className="text-brand-red text-xs">{saveError}</span>
              )}
              <button className="btn-secondary" onClick={resetOcr}>Отменить</button>
              <button
                className="btn-primary"
                onClick={save}
                disabled={saving || editItems.length === 0}
              >
                {saving
                  ? <><Loader2 size={14} className="animate-spin" />Сохраняем...</>
                  : <><CheckCircle2 size={14} />Сохранить накладную</>
                }
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Список сохранённых накладных ───────────────────────────────────── */}
      <div className="card">
        <div className="flex items-center justify-between px-4 sm:px-5 py-4 border-b border-brand-border">
          <h2 className="font-semibold text-brand-dark flex items-center gap-2">
            <ScanLine size={16} className="text-brand-yellow" />
            История накладных (OCR)
          </h2>
          <button
            className="btn-secondary text-xs py-1.5 px-3"
            onClick={loadInvoices}
            disabled={loadingInvoices}
          >
            <RefreshCw size={13} className={loadingInvoices ? "animate-spin" : ""} />
            Обновить
          </button>
        </div>

        {loadingInvoices && invoices.length === 0 ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 size={24} className="animate-spin text-brand-muted" />
          </div>
        ) : invoices.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-brand-muted">
            <ScanLine size={40} className="text-brand-border mb-3" />
            <p className="text-sm">Накладных пока нет</p>
            <p className="text-xs mt-1">Загрузите первое фото или PDF выше</p>
          </div>
        ) : (
          <>
            {/* Desktop */}
            <div className="hidden sm:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-brand-border">
                    {["#", "Ресторан", "Поставщик", "Дата", "Сумма с НДС", "Загружен", ""].map(h => (
                      <th key={h} className="text-left py-3 px-5 text-brand-muted font-medium text-xs uppercase tracking-wide whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {invoices.map(inv => (
                    <tr key={inv.id} className="border-b border-brand-border/50 hover:bg-brand-bg/60 transition-colors">
                      <td className="py-3 px-5 text-brand-muted font-mono text-xs">{inv.id}</td>
                      <td className="py-3 px-5 font-medium text-brand-dark">
                        <span className="flex items-center gap-1.5">
                          <Building2 size={13} className="text-brand-muted" />
                          {restaurantName(inv.restaurant_id)}
                        </span>
                      </td>
                      <td className="py-3 px-5 text-brand-muted">{inv.supplier_name ?? "—"}</td>
                      <td className="py-3 px-5 text-brand-dark">{formatDate(inv.invoice_date)}</td>
                      <td className="py-3 px-5 font-medium text-brand-dark tabular-nums">
                        {inv.total_sum_vat != null
                          ? `${inv.total_sum_vat.toLocaleString("ru-RU", { minimumFractionDigits: 2 })} ₸`
                          : "—"}
                      </td>
                      <td className="py-3 px-5 text-brand-muted text-xs whitespace-nowrap">
                        {new Date(inv.uploaded_at).toLocaleString("ru-RU")}
                      </td>
                      <td className="py-3 px-5">
                        <div className="flex items-center gap-2 justify-end">
                          <button className="btn-secondary text-xs py-1 px-2.5" onClick={() => setSelectedInvoice(inv)}>
                            <ChevronRight size={13} />Позиции
                          </button>
                          {inv.status !== "sent" && (
                            <button className="btn-primary text-xs py-1 px-2.5" onClick={() => setPostingInvoice(inv)}>
                              <Send size={13} />В iiko
                            </button>
                          )}
                          {inv.status === "sent" && (
                            <span className="badge-ok inline-flex items-center gap-1 text-xs">
                              <CheckCircle2 size={11} />Отправлено
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile */}
            <div className="sm:hidden divide-y divide-brand-border/40">
              {invoices.map(inv => (
                <div key={inv.id} className="px-4 py-3.5">
                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <div className="min-w-0">
                      <span className="flex items-center gap-1.5">
                        <Building2 size={13} className="text-brand-muted flex-shrink-0" />
                        <p className="font-semibold text-brand-dark text-sm truncate">{restaurantName(inv.restaurant_id)}</p>
                      </span>
                      <p className="text-brand-muted text-xs mt-0.5 pl-[18px]">{inv.supplier_name ?? "Поставщик не указан"}</p>
                    </div>
                    {inv.total_sum_vat != null && (
                      <p className="font-bold text-brand-dark text-sm tabular-nums flex-shrink-0">
                        {inv.total_sum_vat.toLocaleString("ru-RU", { minimumFractionDigits: 0 })} ₸
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 mt-3">
                    <button
                      className="flex-1 flex items-center justify-center gap-1.5 text-xs font-medium text-brand-dark border border-brand-border rounded-lg py-2 hover:bg-brand-bg transition-colors"
                      onClick={() => setSelectedInvoice(inv)}
                    >
                      <ChevronRight size={13} />Позиции
                    </button>
                    {inv.status !== "sent" ? (
                      <button
                        className="flex-1 flex items-center justify-center gap-1.5 text-xs font-semibold bg-brand-yellow text-brand-dark rounded-lg py-2 hover:brightness-95 transition-all"
                        onClick={() => setPostingInvoice(inv)}
                      >
                        <Send size={13} />В iiko
                      </button>
                    ) : (
                      <span className="flex-1 flex items-center justify-center gap-1.5 text-xs font-medium bg-green-50 text-green-700 border border-green-200 rounded-lg py-2">
                        <CheckCircle2 size={13} />Отправлено
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {selectedInvoice && (
        <ItemsModal
          invoice={selectedInvoice}
          restaurantName={restaurantName(selectedInvoice.restaurant_id)}
          onClose={() => setSelectedInvoice(null)}
        />
      )}
      {postingInvoice && (
        <PostToIikoModal
          invoice={postingInvoice}
          restaurantName={restaurantName(postingInvoice.restaurant_id)}
          onClose={() => setPostingInvoice(null)}
          onDone={() => { setPostingInvoice(null); loadInvoices() }}
        />
      )}
    </div>
  )
}
