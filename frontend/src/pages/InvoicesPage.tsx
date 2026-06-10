import { useEffect, useRef, useState } from "react"
import api from "../api/client"
import type { Restaurant } from "../types"
import {
  FileInput, Upload, ChevronRight, X, Loader2, AlertCircle,
  PackageCheck, RefreshCw, Building2, Send, CheckCircle2,
} from "lucide-react"
import { cn, formatDate } from "../lib/utils"

// ── Types ─────────────────────────────────────────────────────────────────────

interface Invoice {
  id: number
  restaurant_id: number
  invoice_date: string | null
  uploaded_at: string
  filename: string
  status: string
  error_message?: string | null
  total_sum: number | null
  total_sum_vat: number | null
  supplier_name?: string | null
  items_count?: number
}

interface InvoiceItem {
  id: number
  abl_article: string
  name: string
  iiko_product_id: string | null
  iiko_product_name: string | null
  matched: boolean
  quantity: number
  unit_price: number | null
  unit_price_vat: number | null
  total_price: number | null
  total_price_vat: number | null
  invoice_number: string | null
}

// ── Items modal ───────────────────────────────────────────────────────────────

function ItemsModal({ invoice, restaurantName, onClose }: {
  invoice: Invoice
  restaurantName: string
  onClose: () => void
}) {
  const [items, setItems] = useState<InvoiceItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get(`/invoices/${invoice.id}/items`).then((res) => {
      setItems(res.data)
      setLoading(false)
    })
  }, [invoice.id])

  const fmt = (n: number | null | undefined) =>
    n == null ? "—" : n.toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-5xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-brand-border">
          <div>
            <h2 className="font-bold text-brand-dark text-lg">
              Накладная #{invoice.id}
            </h2>
            <p className="text-brand-muted text-sm mt-0.5">
              {restaurantName} · {invoice.filename}
              {invoice.invoice_date && ` · ${formatDate(invoice.invoice_date)}`}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {invoice.total_sum_vat != null && (
              <span className="text-sm font-semibold text-brand-dark">
                Итого: {invoice.total_sum_vat.toLocaleString("ru-RU", { minimumFractionDigits: 2 })} ₸
              </span>
            )}
            <button onClick={onClose} className="p-2 rounded-lg hover:bg-brand-bg transition-colors">
              <X size={18} className="text-brand-muted" />
            </button>
          </div>
        </div>

        {/* Table */}
        <div className="flex-1 overflow-auto px-6 pb-6 mt-3">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 size={24} className="animate-spin text-brand-muted" />
            </div>
          ) : items.length === 0 ? (
            <div className="text-center py-20 text-brand-muted text-sm">Нет позиций</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-brand-border">
                  {["", "Артикул ABL", "Наименование", "Товар в IIKO", "Кол-во", "Цена (с НДС)", "Сумма (с НДС)"].map((h) => (
                    <th key={h} className="text-left py-2 px-3 text-brand-muted font-medium text-xs uppercase tracking-wide whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className={cn(
                    "border-b border-brand-border/50 transition-colors",
                    item.matched ? "hover:bg-brand-bg/60" : "bg-red-50/60 hover:bg-red-50"
                  )}>
                    <td className="py-2.5 px-3">
                      {item.matched
                        ? <CheckCircle2 size={14} className="text-green-500" />
                        : <AlertCircle size={14} className="text-brand-red" />
                      }
                    </td>
                    <td className="py-2.5 px-3 font-mono text-xs text-brand-muted">{item.abl_article}</td>
                    <td className="py-2.5 px-3 font-medium text-brand-dark max-w-[180px]">{item.name}</td>
                    <td className="py-2.5 px-3 max-w-[200px]">
                      {item.matched ? (
                        <div>
                          <p className="text-brand-dark text-xs font-medium truncate">{item.iiko_product_name}</p>
                          <p className="text-brand-muted text-xs font-mono truncate">{item.iiko_product_id}</p>
                        </div>
                      ) : (
                        <span className="text-brand-red text-xs">Не найден в IIKO</span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-right tabular-nums">{item.quantity.toLocaleString("ru-RU", { maximumFractionDigits: 3 })}</td>
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

// ── Post to IIKO modal ────────────────────────────────────────────────────────

function PostToIikoModal({ invoice, restaurantName, onClose, onDone }: {
  invoice: Invoice
  restaurantName: string
  onClose: () => void
  onDone: () => void
}) {
  const [dateIncoming, setDateIncoming] = useState(() => {
    const d = invoice.invoice_date ? new Date(invoice.invoice_date) : new Date()
    return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.${d.getFullYear()}`
  })
  const [posting, setPosting] = useState(false)
  const [result, setResult] = useState<{ sent?: number; errors?: { invoice_num: string; error: string }[] } | null>(null)
  const [error, setError] = useState("")

  const post = async () => {
    setPosting(true)
    setError("")
    setResult(null)
    try {
      const res = await api.post(`/invoices/${invoice.id}/post-to-iiko`, {
        date_incoming: dateIncoming,
      })
      setResult(res.data)
      if (res.data.errors?.length === 0 || !res.data.errors) onDone()
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
            <span className="font-medium text-brand-dark">{restaurantName}</span> · {invoice.filename}
          </p>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-brand-muted uppercase tracking-wide">Дата прихода (ДД.ММ.ГГГГ)</label>
            <input
              type="text"
              className="input"
              placeholder="11.03.2026"
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
          {result && (
            <div className={cn(
              "flex items-start gap-2 p-3 rounded-lg text-sm",
              result.errors?.length === 0 ? "bg-green-50 border border-green-100 text-green-700" : "bg-yellow-50 border border-yellow-100 text-yellow-700"
            )}>
              <CheckCircle2 size={14} className="flex-shrink-0 mt-0.5" />
              <div>
                <p>Отправлено накладных: {result.sent}</p>
                {result.errors?.map((e, i) => (
                  <p key={i} className="text-brand-red text-xs mt-1">{e.invoice_num}: {e.error}</p>
                ))}
              </div>
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

// ── Main page ──────────────────────────────────────────────────────────────────

export default function InvoicesPage() {
  const [restaurants, setRestaurants] = useState<Restaurant[]>([])
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [restaurantId, setRestaurantId] = useState("")
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [loadingInvoices, setLoadingInvoices] = useState(true)
  const [error, setError] = useState("")
  const [success, setSuccess] = useState("")
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null)
  const [postingInvoice, setPostingInvoice] = useState<Invoice | null>(null)
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
      const res = await api.get("/invoices/")
      setInvoices(res.data)
    } finally {
      setLoadingInvoices(false)
    }
  }

  const upload = async () => {
    if (!file || !restaurantId) return
    setUploading(true)
    setError("")
    setSuccess("")
    try {
      const form = new FormData()
      form.append("file", file)
      form.append("restaurant_id", restaurantId)
      const { data } = await api.post("/invoices/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      setSuccess(`Накладная загружена: ${data.items_count} позиций на сумму ${data.total_sum_vat?.toLocaleString("ru-RU") ?? "—"} ₸`)
      setFile(null)
      if (fileRef.current) fileRef.current.value = ""
      await loadInvoices()
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setUploading(false)
    }
  }

  const restaurantName = (id: number) =>
    restaurants.find((r) => r.id === id)?.name ?? `#${id}`

  return (
    <div className="p-4 sm:p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-brand-dark">Накладные</h1>
        <p className="text-brand-muted text-sm mt-1">Загрузка и просмотр накладных ABL</p>
      </div>

      {/* Upload card */}
      <div className="card p-5 mb-6">
        <h2 className="font-semibold text-brand-dark mb-4 flex items-center gap-2">
          <Upload size={16} className="text-brand-yellow" />
          Загрузить накладную
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
            <label className="text-xs font-medium text-brand-muted uppercase tracking-wide">Файл Excel (.xlsx)</label>
            <input
              ref={fileRef}
              type="file"
              accept=".xlsx"
              className="input cursor-pointer file:mr-3 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:font-medium file:bg-brand-yellow/10 file:text-brand-dark hover:file:bg-brand-yellow/20"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
          <button
            className="btn-primary"
            onClick={upload}
            disabled={uploading || !file || !restaurantId}
          >
            {uploading ? (
              <>
                <Loader2 size={15} className="animate-spin" />
                Загружаем...
              </>
            ) : (
              <>
                <Upload size={15} />
                Загрузить
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
        {success && (
          <div className="mt-3 flex items-center gap-2 p-3 rounded-lg bg-green-50 border border-green-100">
            <PackageCheck size={15} className="text-green-600 flex-shrink-0" />
            <span className="text-green-700 text-sm">{success}</span>
          </div>
        )}
      </div>

      {/* Invoices list */}
      <div className="card">
        <div className="flex items-center justify-between px-4 sm:px-5 py-4 border-b border-brand-border">
          <h2 className="font-semibold text-brand-dark flex items-center gap-2">
            <FileInput size={16} className="text-brand-yellow" />
            История накладных
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
            <FileInput size={40} className="text-brand-border mb-3" />
            <p className="text-sm">Накладных пока нет</p>
            <p className="text-xs mt-1">Загрузите первый файл Excel выше</p>
          </div>
        ) : (
          <>
            {/* Desktop: таблица */}
            <div className="hidden sm:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-brand-border">
                    {["#", "Ресторан", "Поставщик", "Дата накладной", "Сумма с НДС", "Загружен", ""].map((h) => (
                      <th key={h} className="text-left py-3 px-5 text-brand-muted font-medium text-xs uppercase tracking-wide whitespace-nowrap">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((inv) => (
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
                              <Send size={13} />В IIKO
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

            {/* Mobile: карточки */}
            <div className="sm:hidden divide-y divide-brand-border/40">
              {invoices.map((inv) => (
                <div key={inv.id} className="px-4 py-3.5">
                  {/* Строка 1: ресторан + сумма */}
                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <div className="min-w-0">
                      <span className="flex items-center gap-1.5">
                        <Building2 size={13} className="text-brand-muted flex-shrink-0" />
                        <p className="font-semibold text-brand-dark text-sm truncate">{restaurantName(inv.restaurant_id)}</p>
                      </span>
                      <p className="text-brand-muted text-xs mt-0.5 pl-[18px]">{inv.supplier_name ?? "Поставщик не указан"}</p>
                    </div>
                    {inv.total_sum_vat != null ? (
                      <p className="font-bold text-brand-dark text-sm tabular-nums flex-shrink-0">
                        {inv.total_sum_vat.toLocaleString("ru-RU", { minimumFractionDigits: 0 })} ₸
                      </p>
                    ) : (
                      <p className="text-brand-muted text-sm">—</p>
                    )}
                  </div>

                  {/* Строка 2: дата накладной + дата загрузки */}
                  <div className="flex items-center gap-3 mb-3 pl-[18px]">
                    <p className="text-xs text-brand-muted">
                      Накладная: <span className="text-brand-dark font-medium">{formatDate(inv.invoice_date)}</span>
                    </p>
                    <span className="text-brand-border">·</span>
                    <p className="text-xs text-brand-muted">
                      {new Date(inv.uploaded_at).toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
                    </p>
                  </div>

                  {/* Строка 3: кнопки */}
                  <div className="flex items-center gap-2">
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
                        <Send size={13} />В IIKO
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
