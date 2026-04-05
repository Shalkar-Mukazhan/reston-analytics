import { useEffect, useRef, useState } from "react"
import api from "../api/client"
import {
  Settings, Users, Store, BarChart3, Upload,
  Plus, Edit2, Trash2, Save, X, Loader2, AlertCircle,
  CheckCircle2, ChevronDown, ChevronUp, Eye, EyeOff,
  RefreshCw, Wifi, WifiOff, BookOpen, CreditCard,
  Layers, Tag, Database, Search, ChefHat, Trash, ArrowLeftRight, FileSpreadsheet,
  ShieldCheck, ToggleLeft, ToggleRight, FileInput, TrendingUp,
} from "lucide-react"
import { cn } from "../lib/utils"

// ── Types ─────────────────────────────────────────────────────────────────────

interface AdminUser {
  id: number
  username: string
  role: "store" | "co" | "admin"
  is_active: boolean
  restaurant_ids: number[]
}

interface Restaurant {
  id: number
  code: string
  name: string
  base_url: string | null
  iiko_login: string | null
  department_name: string | null
  is_active: boolean
  store_id: string | null
  presets: { type: string; uuid: string }[]
}

interface ProductGroup {
  id: number
  name: string
  account_id: number | null
}

interface WasteRate {
  group_id: number
  group_name: string
  rate_pct: number | null
}

interface Account {
  id: number
  account_iiko_id: string
  name: string
  groups: { id: number; name: string }[]
}

interface CatalogItem {
  id: number
  product_num: string
  name: string
  group: string | null
  group_id: number | null
  unit_type: string | null
  product_iiko_id: string
  is_deleted: boolean
}

interface Preset {
  id: number
  preset_type: string
  preset_uuid: string
  description: string | null
  restaurants: { id: number; code: string; name: string }[]
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const ROLE_LABEL: Record<string, string> = { store: "Ресторан", co: "ЦО", admin: "Администратор" }
const PRESET_TYPES = ["sales", "writeoff", "inventory", "revenue_net", "complete_waste"]
const PRESET_LABELS: Record<string, string> = {
  sales: "Продажи",
  writeoff: "Списание",
  inventory: "Инвентаризация",
  revenue_net: "Выручка (net)",
  complete_waste: "Полное списание",
}

function Alert({ type, message }: { type: "success" | "error"; message: string }) {
  return (
    <div className={cn(
      "flex items-center gap-2 p-3 rounded-lg text-sm mb-4",
      type === "success"
        ? "bg-green-50 border border-green-100 text-green-700"
        : "bg-red-50 border border-red-100 text-brand-red"
    )}>
      {type === "success" ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}
      {message}
    </div>
  )
}

// ── Tab: Users ─────────────────────────────────────────────────────────────────

function UsersTab({ restaurants }: { restaurants: Restaurant[] }) {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null)
  const [editId, setEditId] = useState<number | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [showPass, setShowPass] = useState(false)
  const [form, setForm] = useState<{
    username: string; password: string; role: string; is_active: boolean; restaurant_ids: number[]
  }>({ username: "", password: "", role: "store", is_active: true, restaurant_ids: [] })
  const [saving, setSaving] = useState(false)

  const load = async () => {
    setLoading(true)
    try { const r = await api.get("/admin/users"); setUsers(r.data) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const openNew = () => {
    setEditId(null)
    setForm({ username: "", password: "", role: "store", is_active: true, restaurant_ids: [] })
    setShowForm(true); setMsg(null)
  }

  const openEdit = (u: AdminUser) => {
    setEditId(u.id)
    setForm({ username: u.username, password: "", role: u.role, is_active: u.is_active, restaurant_ids: u.restaurant_ids })
    setShowForm(true); setMsg(null)
  }

  const save = async () => {
    setSaving(true); setMsg(null)
    try {
      const payload: any = { ...form, restaurant_ids: form.restaurant_ids.map(Number) }
      if (!payload.password) delete payload.password
      if (editId) {
        await api.patch(`/admin/users/${editId}`, payload)
        setMsg({ type: "success", text: "Пользователь обновлён" })
      } else {
        await api.post("/admin/users", payload)
        setMsg({ type: "success", text: "Пользователь создан" })
      }
      await load(); setShowForm(false)
    } catch (e: any) {
      setMsg({ type: "error", text: e.response?.data?.detail || e.message })
    } finally { setSaving(false) }
  }

  const remove = async (id: number, username: string) => {
    if (!confirm(`Удалить пользователя «${username}»?`)) return
    try { await api.delete(`/admin/users/${id}`); await load() }
    catch (e: any) { setMsg({ type: "error", text: e.response?.data?.detail || e.message }) }
  }

  const toggleRestaurant = (rid: number) => {
    setForm((f) => ({
      ...f,
      restaurant_ids: f.restaurant_ids.includes(rid)
        ? f.restaurant_ids.filter((x) => x !== rid)
        : [...f.restaurant_ids, rid],
    }))
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-brand-muted text-sm">{users.length} пользователей</p>
        <button className="btn-primary text-sm py-2" onClick={openNew}>
          <Plus size={15} /> Добавить
        </button>
      </div>

      {msg && <Alert type={msg.type} message={msg.text} />}

      {showForm && (
        <div className="card p-5 mb-5 border-2 border-brand-yellow/30">
          <h3 className="font-semibold text-brand-dark mb-4">{editId ? "Редактировать" : "Новый"} пользователь</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="text-xs font-medium text-brand-muted uppercase tracking-wide mb-1.5 block">Логин</label>
              <input className="input w-full" value={form.username} onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-brand-muted uppercase tracking-wide mb-1.5 block">
                Пароль {editId && <span className="normal-case">(пусто — не менять)</span>}
              </label>
              <div className="relative">
                <input
                  className="input w-full pr-10"
                  type={showPass ? "text" : "password"}
                  value={form.password}
                  onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                />
                <button type="button" onClick={() => setShowPass((s) => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-brand-muted hover:text-brand-dark">
                  {showPass ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-brand-muted uppercase tracking-wide mb-1.5 block">Роль</label>
              <select className="input w-full" value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}>
                <option value="store">Ресторан</option>
                <option value="co">ЦО</option>
                <option value="admin">Администратор</option>
              </select>
            </div>
            <div className="flex items-center gap-3 pt-6">
              <input type="checkbox" id="is_active" checked={form.is_active}
                onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
                className="w-4 h-4 accent-brand-yellow" />
              <label htmlFor="is_active" className="text-sm text-brand-dark">Активен</label>
            </div>
          </div>
          <div className="mb-4">
            <label className="text-xs font-medium text-brand-muted uppercase tracking-wide mb-2 block">Доступ к ресторанам</label>
            <div className="flex flex-wrap gap-2 max-h-36 overflow-y-auto p-2 border border-brand-border rounded-lg bg-brand-bg/50">
              {restaurants.map((r) => (
                <button key={r.id} type="button" onClick={() => toggleRestaurant(r.id)}
                  className={cn(
                    "px-2.5 py-1 rounded-md text-xs font-medium transition-colors",
                    form.restaurant_ids.includes(r.id)
                      ? "bg-brand-yellow text-brand-dark"
                      : "bg-white border border-brand-border text-brand-muted hover:border-brand-yellow"
                  )}>
                  {r.code}
                </button>
              ))}
            </div>
          </div>
          <div className="flex gap-2">
            <button className="btn-primary" onClick={save} disabled={saving}>
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Сохранить
            </button>
            <button className="btn-secondary" onClick={() => setShowForm(false)}>
              <X size={14} /> Отмена
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-10"><Loader2 size={24} className="animate-spin text-brand-muted" /></div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-brand-border">
                {["Логин", "Роль", "Рестораны", "Статус", ""].map((h) => (
                  <th key={h} className="text-left py-2.5 px-4 text-brand-muted font-medium text-xs uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-brand-border/50 hover:bg-brand-bg/60 transition-colors">
                  <td className="py-3 px-4 font-medium text-brand-dark">{u.username}</td>
                  <td className="py-3 px-4 text-brand-muted">{ROLE_LABEL[u.role] ?? u.role}</td>
                  <td className="py-3 px-4 text-brand-muted text-xs">
                    {u.restaurant_ids.length === 0 ? "—" : `${u.restaurant_ids.length} рест.`}
                  </td>
                  <td className="py-3 px-4">
                    <span className={u.is_active ? "badge-ok" : "badge-muted"}>
                      {u.is_active ? "Активен" : "Отключён"}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex gap-2 justify-end">
                      <button className="btn-secondary py-1 px-2 text-xs" onClick={() => openEdit(u)}>
                        <Edit2 size={12} /> Изменить
                      </button>
                      <button className="btn-danger py-1 px-2 text-xs" onClick={() => remove(u.id, u.username)}>
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Tab: Restaurants ──────────────────────────────────────────────────────────

function RestaurantsTab() {
  const [restaurants, setRestaurants] = useState<Restaurant[]>([])
  const [allPresets, setAllPresets] = useState<Preset[]>([])
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null)
  const [editId, setEditId] = useState<number | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [expandedRates, setExpandedRates] = useState<number | null>(null)
  const [rates, setRates] = useState<WasteRate[]>([])
  const [savingRates, setSavingRates] = useState(false)
  const [testingConn, setTestingConn] = useState<number | null>(null)
  const [connResult, setConnResult] = useState<{ id: number; ok: boolean; msg: string } | null>(null)
  // selectedPresetIds — список ID выбранных пресетов из глобального списка
  const [selectedPresetIds, setSelectedPresetIds] = useState<number[]>([])
  const [form, setForm] = useState<{
    code: string; name: string; base_url: string; iiko_login: string; iiko_password: string
    department_name: string; store_id: string; is_active: boolean; google_sheet_url: string
    checklist_start_hour: number
  }>({
    code: "", name: "", base_url: "", iiko_login: "", iiko_password: "",
    department_name: "", store_id: "", is_active: true, google_sheet_url: "",
    checklist_start_hour: 7,
  })
  const [saving, setSaving] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [rRes, pRes] = await Promise.all([api.get("/admin/restaurants"), api.get("/admin/presets")])
      setRestaurants(rRes.data)
      setAllPresets(pRes.data)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const openNew = () => {
    setEditId(null)
    setForm({ code: "", name: "", base_url: "", iiko_login: "", iiko_password: "", department_name: "", store_id: "", is_active: true, google_sheet_url: "", checklist_start_hour: 7 })
    setSelectedPresetIds([])
    setShowForm(true); setMsg(null)
  }

  const openEdit = (r: Restaurant) => {
    setEditId(r.id)
    setForm({
      code: r.code, name: r.name, base_url: r.base_url ?? "",
      iiko_login: r.iiko_login ?? "", iiko_password: "",
      department_name: r.department_name ?? "",
      store_id: r.store_id ?? "", is_active: r.is_active,
      google_sheet_url: (r as any).google_sheet_url ?? "",
      checklist_start_hour: (r as any).checklist_start_hour ?? 7,
    })
    // Сопоставляем пресеты ресторана с глобальным списком по uuid
    const ids = allPresets
      .filter((p) => r.presets.some((rp) => rp.uuid === p.preset_uuid && rp.type === p.preset_type))
      .map((p) => p.id)
    setSelectedPresetIds(ids)
    setShowForm(true); setMsg(null); setConnResult(null)
  }

  const save = async () => {
    setSaving(true); setMsg(null)
    try {
      // Преобразуем выбранные ID пресетов в {type, uuid}
      const presets = allPresets
        .filter((p) => selectedPresetIds.includes(p.id))
        .map((p) => ({ type: p.preset_type, uuid: p.preset_uuid }))

      if (editId) {
        const payload: any = {
          name: form.name, department_name: form.department_name,
          base_url: form.base_url, iiko_login: form.iiko_login,
          store_id: form.store_id || null, is_active: form.is_active, presets,
          google_sheet_url: form.google_sheet_url || null,
          checklist_start_hour: form.checklist_start_hour,
        }
        if (form.iiko_password) payload.iiko_password = form.iiko_password
        await api.patch(`/admin/restaurants/${editId}`, payload)
        setMsg({ type: "success", text: "Ресторан обновлён" })
      } else {
        await api.post("/admin/restaurants", {
          code: form.code, name: form.name, department_name: form.department_name,
          base_url: form.base_url, iiko_login: form.iiko_login, iiko_password: form.iiko_password,
          store_id: form.store_id || null, presets,
        })
        setMsg({ type: "success", text: "Ресторан создан" })
      }
      await load(); setShowForm(false)
    } catch (e: any) {
      setMsg({ type: "error", text: e.response?.data?.detail || e.message })
    } finally { setSaving(false) }
  }

  const togglePreset = (id: number) => {
    setSelectedPresetIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    )
  }

  const remove = async (id: number, name: string) => {
    if (!confirm(`Удалить ресторан «${name}»?`)) return
    try { await api.delete(`/admin/restaurants/${id}`); await load() }
    catch (e: any) { setMsg({ type: "error", text: e.response?.data?.detail || e.message }) }
  }

  const toggleRates = async (id: number) => {
    if (expandedRates === id) { setExpandedRates(null); return }
    setExpandedRates(id)
    const r = await api.get(`/admin/restaurants/${id}/waste-rates`)
    setRates(r.data)
  }

  const saveRates = async (id: number) => {
    setSavingRates(true)
    try {
      const payload = rates.filter((r) => r.rate_pct != null).map((r) => ({ group_id: r.group_id, rate_pct: r.rate_pct! }))
      await api.put(`/admin/restaurants/${id}/waste-rates`, payload)
      setMsg({ type: "success", text: "Нормы сохранены" })
    } catch (e: any) {
      setMsg({ type: "error", text: e.response?.data?.detail || e.message })
    } finally { setSavingRates(false) }
  }

  const testConnection = async (id: number) => {
    setTestingConn(id); setConnResult(null)
    try {
      const { data } = await api.post(`/admin/iiko/test-connection/${id}`)
      setConnResult({ id, ok: data.ok, msg: data.ok ? "Подключение успешно" : data.error })
    } catch (e: any) {
      setConnResult({ id, ok: false, msg: e.response?.data?.detail || e.message })
    } finally { setTestingConn(null) }
  }

  const updateRate = (groupId: number, val: string) => {
    setRates((prev) => prev.map((r) => r.group_id === groupId ? { ...r, rate_pct: val === "" ? null : parseFloat(val) } : r))
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-brand-muted text-sm">{restaurants.length} ресторанов</p>
        <button className="btn-primary text-sm py-2" onClick={openNew}>
          <Plus size={15} /> Добавить
        </button>
      </div>

      {msg && <Alert type={msg.type} message={msg.text} />}

      {showForm && (
        <div className="card p-5 mb-5 border-2 border-brand-yellow/30">
          <h3 className="font-semibold text-brand-dark mb-4">{editId ? "Редактировать" : "Новый"} ресторан</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="text-xs font-medium text-brand-muted uppercase tracking-wide mb-1.5 block">Код</label>
              <input className="input w-full" value={form.code} disabled={!!editId} onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-brand-muted uppercase tracking-wide mb-1.5 block">Название</label>
              <input className="input w-full" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-brand-muted uppercase tracking-wide mb-1.5 block">IIKO Base URL</label>
              <input className="input w-full" placeholder="https://xxx.iiko.it" value={form.base_url} onChange={(e) => setForm((f) => ({ ...f, base_url: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-brand-muted uppercase tracking-wide mb-1.5 block">IIKO Login</label>
              <input className="input w-full" value={form.iiko_login} onChange={(e) => setForm((f) => ({ ...f, iiko_login: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-brand-muted uppercase tracking-wide mb-1.5 block">
                IIKO Password {editId && <span className="normal-case">(пусто — не менять)</span>}
              </label>
              <input className="input w-full" type="password" value={form.iiko_password} onChange={(e) => setForm((f) => ({ ...f, iiko_password: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-brand-muted uppercase tracking-wide mb-1.5 block">Department name (IIKO)</label>
              <input className="input w-full" value={form.department_name} onChange={(e) => setForm((f) => ({ ...f, department_name: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-brand-muted uppercase tracking-wide mb-1.5 block">Store ID (IIKO)</label>
              <input className="input w-full" value={form.store_id} onChange={(e) => setForm((f) => ({ ...f, store_id: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-brand-muted uppercase tracking-wide mb-1.5 block">Чек-лист Google Sheets URL</label>
              <input className="input w-full" placeholder="https://docs.google.com/spreadsheets/d/..." value={form.google_sheet_url} onChange={(e) => setForm((f) => ({ ...f, google_sheet_url: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-brand-muted uppercase tracking-wide mb-1.5 block">Час начала бизнес дня</label>
              <select className="input w-full" value={form.checklist_start_hour} onChange={(e) => setForm((f) => ({ ...f, checklist_start_hour: parseInt(e.target.value) }))}>
                {Array.from({length: 12}, (_, i) => i + 5).map(h => (
                  <option key={h} value={h}>{h}:00</option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-3 pt-6">
              <input type="checkbox" id="r_active" checked={form.is_active}
                onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
                className="w-4 h-4 accent-brand-yellow" />
              <label htmlFor="r_active" className="text-sm text-brand-dark">Активен</label>
            </div>
          </div>

          <div className="mb-4">
            <label className="text-xs font-medium text-brand-muted uppercase tracking-wide mb-2 block">
              Пресеты OLAP
              {allPresets.length === 0 && (
                <span className="ml-2 text-brand-red normal-case font-normal">— сначала добавьте пресеты в табе «Пресеты»</span>
              )}
            </label>
            {allPresets.length > 0 ? (
              <div className="border border-brand-border rounded-xl p-3 max-h-52 overflow-y-auto space-y-1.5">
                {allPresets.map((p) => (
                  <label key={p.id} className={cn(
                    "flex items-start gap-3 p-2 rounded-lg cursor-pointer transition-colors",
                    selectedPresetIds.includes(p.id) ? "bg-brand-yellow/10" : "hover:bg-brand-bg/60"
                  )}>
                    <input
                      type="checkbox"
                      className="mt-0.5 w-4 h-4 accent-brand-yellow flex-shrink-0"
                      checked={selectedPresetIds.includes(p.id)}
                      onChange={() => togglePreset(p.id)}
                    />
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-brand-dark">
                        <span className="px-1.5 py-0.5 rounded bg-brand-yellow/20 text-brand-dark mr-1.5">{p.preset_type}</span>
                        {p.description || ""}
                      </p>
                      <p className="font-mono text-xs text-brand-muted truncate mt-0.5">{p.preset_uuid}</p>
                    </div>
                  </label>
                ))}
              </div>
            ) : (
              <p className="text-xs text-brand-muted italic py-2">Нет доступных пресетов</p>
            )}
          </div>

          {/* Test connection result */}
          {connResult && editId === connResult.id && (
            <div className={cn(
              "flex items-center gap-2 p-3 rounded-lg text-sm mb-4",
              connResult.ok ? "bg-green-50 border border-green-100 text-green-700" : "bg-red-50 border border-red-100 text-brand-red"
            )}>
              {connResult.ok ? <Wifi size={14} /> : <WifiOff size={14} />}
              {connResult.msg}
            </div>
          )}

          <div className="flex gap-2 flex-wrap">
            <button className="btn-primary" onClick={save} disabled={saving}>
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Сохранить
            </button>
            {editId && (
              <button className="btn-secondary" onClick={() => testConnection(editId)} disabled={testingConn === editId}>
                {testingConn === editId ? <Loader2 size={14} className="animate-spin" /> : <Wifi size={14} />}
                Тест подключения
              </button>
            )}
            <button className="btn-secondary" onClick={() => setShowForm(false)}>
              <X size={14} /> Отмена
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-10"><Loader2 size={24} className="animate-spin text-brand-muted" /></div>
      ) : (
        <div className="space-y-2">
          {restaurants.map((r) => (
            <div key={r.id} className="border border-brand-border rounded-xl overflow-hidden">
              <div className="flex items-center gap-4 p-4 bg-white hover:bg-brand-bg/40 transition-colors">
                <div className="flex-shrink-0 w-12 h-10 rounded-lg bg-brand-yellow/10 flex items-center justify-center">
                  <span className="text-xs font-bold text-brand-dark">{r.code}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-brand-dark text-sm">{r.name}</p>
                  <p className="text-xs text-brand-muted">{r.base_url ?? "IIKO не настроен"}</p>
                </div>
                <div className="flex items-center gap-1.5">
                  {r.store_id
                    ? <span className="badge-ok text-xs">Store ID ✓</span>
                    : <span className="badge-warn text-xs">Нет Store ID</span>
                  }
                  <span className={r.presets.length > 0 ? "badge-ok text-xs" : "badge-warn text-xs"}>
                    {r.presets.length} пресетов
                  </span>
                  <span className={r.is_active ? "badge-ok" : "badge-muted"}>
                    {r.is_active ? "Активен" : "Выкл."}
                  </span>
                </div>
                <div className="flex gap-2">
                  <button
                    className={cn("btn-secondary py-1 px-2.5 text-xs", expandedRates === r.id && "bg-brand-yellow/10 border-brand-yellow/30")}
                    onClick={() => toggleRates(r.id)}
                  >
                    <BarChart3 size={12} /> Нормы
                    {expandedRates === r.id ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                  </button>
                  <button className="btn-secondary py-1 px-2 text-xs" onClick={() => openEdit(r)}>
                    <Edit2 size={12} />
                  </button>
                  <button className="btn-danger py-1 px-2 text-xs" onClick={() => remove(r.id, r.name)}>
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>

              {expandedRates === r.id && (
                <div className="border-t border-brand-border bg-brand-bg/50 p-4">
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-sm font-medium text-brand-dark">Нормы списания по группам (%)</p>
                    <button className="btn-primary text-xs py-1.5 px-3" onClick={() => saveRates(r.id)} disabled={savingRates}>
                      {savingRates ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />} Сохранить
                    </button>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                    {rates.map((rate) => (
                      <div key={rate.group_id}>
                        <label className="text-xs text-brand-muted mb-1 block truncate">{rate.group_name}</label>
                        <input type="number" step="1" min="0" max="100" className="input w-full text-sm"
                          value={rate.rate_pct ?? ""} placeholder="—"
                          onChange={(e) => updateRate(rate.group_id, e.target.value)} />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Tab: IIKO Sync ────────────────────────────────────────────────────────────

function IikoSyncTab() {
  const [restaurants, setRestaurants] = useState<Restaurant[]>([])
  const [loading, setLoading] = useState(true)
  const [syncingStores, setSyncingStores] = useState(false)
  const [syncingSupplier, setSyncingSupplier] = useState<number | null>(null)
  const [storesResult, setStoresResult] = useState<{ matched: number; found: number } | null>(null)
  const [supplierResults, setSupplierResults] = useState<Record<number, { added: number; updated: number } | string>>({})
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null)

  useEffect(() => {
    api.get("/admin/restaurants").then((r) => { setRestaurants(r.data); setLoading(false) })
  }, [])

  const syncStores = async () => {
    setSyncingStores(true); setStoresResult(null); setMsg(null)
    try {
      const { data } = await api.post("/admin/iiko/sync-stores")
      setStoresResult({ matched: data.restaurants_matched, found: data.stores_found })
      setMsg({ type: "success", text: `Склады синхронизированы: найдено ${data.stores_found}, привязано ${data.restaurants_matched} ресторанов` })
      const r = await api.get("/admin/restaurants"); setRestaurants(r.data)
    } catch (e: any) {
      setMsg({ type: "error", text: e.response?.data?.detail || e.message })
    } finally { setSyncingStores(false) }
  }

  const syncSuppliers = async (id: number) => {
    setSyncingSupplier(id)
    try {
      const { data } = await api.post(`/admin/iiko/sync-suppliers/${id}`)
      setSupplierResults((prev) => ({ ...prev, [id]: { added: data.added, updated: data.updated } }))
    } catch (e: any) {
      setSupplierResults((prev) => ({ ...prev, [id]: e.response?.data?.detail || e.message }))
    } finally { setSyncingSupplier(null) }
  }

  return (
    <div className="space-y-6">
      {msg && <Alert type={msg.type} message={msg.text} />}

      {/* Sync Stores */}
      <div className="card p-5">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="font-semibold text-brand-dark flex items-center gap-2 mb-1">
              <Store size={15} className="text-brand-yellow" /> Синхронизация Store ID
            </h3>
            <p className="text-sm text-brand-muted">
              Загружает склады из IIKO и автоматически привязывает их к ресторанам по коду.
              Нужно выполнить один раз для каждого нового ресторана.
            </p>
            {storesResult && (
              <p className="text-sm text-green-700 mt-2">
                Найдено складов: <b>{storesResult.found}</b>, привязано ресторанов: <b>{storesResult.matched}</b>
              </p>
            )}
          </div>
          <button className="btn-primary flex-shrink-0 ml-4" onClick={syncStores} disabled={syncingStores}>
            {syncingStores ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
            Синхронизировать
          </button>
        </div>
      </div>

      {/* Sync Suppliers per restaurant */}
      <div className="card">
        <div className="px-5 py-4 border-b border-brand-border">
          <h3 className="font-semibold text-brand-dark flex items-center gap-2">
            <Users size={15} className="text-brand-yellow" /> Синхронизация поставщиков
          </h3>
          <p className="text-sm text-brand-muted mt-0.5">Загружает список поставщиков из IIKO для каждого ресторана</p>
        </div>
        {loading ? (
          <div className="flex justify-center py-10"><Loader2 size={22} className="animate-spin text-brand-muted" /></div>
        ) : (
          <div className="divide-y divide-brand-border">
            {restaurants.filter((r) => r.is_active).map((r) => {
              const result = supplierResults[r.id]
              return (
                <div key={r.id} className="flex items-center gap-4 px-5 py-3">
                  <div className="w-10 h-8 rounded-lg bg-brand-yellow/10 flex items-center justify-center flex-shrink-0">
                    <span className="text-xs font-bold text-brand-dark">{r.code}</span>
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-brand-dark">{r.name}</p>
                    {result && typeof result === "object" && (
                      <p className="text-xs text-green-600 mt-0.5">Добавлено: {result.added}, обновлено: {result.updated}</p>
                    )}
                    {result && typeof result === "string" && (
                      <p className="text-xs text-brand-red mt-0.5">{result}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {r.base_url
                      ? <span className="badge-ok text-xs">IIKO ✓</span>
                      : <span className="badge-muted text-xs">Нет URL</span>
                    }
                    <button
                      className="btn-secondary text-xs py-1 px-2.5"
                      disabled={!r.base_url || syncingSupplier === r.id}
                      onClick={() => syncSuppliers(r.id)}
                    >
                      {syncingSupplier === r.id ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
                      Загрузить
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Tab: Groups ───────────────────────────────────────────────────────────────

function GroupsTab() {
  const [groups, setGroups] = useState<ProductGroup[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null)
  const [editId, setEditId] = useState<number | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: "", account_id: "" })
  const [saving, setSaving] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [gRes, aRes] = await Promise.all([api.get("/admin/product-groups"), api.get("/admin/accounts")])
      setGroups(gRes.data); setAccounts(aRes.data)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const openNew = () => { setEditId(null); setForm({ name: "", account_id: "" }); setShowForm(true); setMsg(null) }
  const openEdit = (g: ProductGroup) => {
    setEditId(g.id)
    setForm({ name: g.name, account_id: g.account_id ? String(g.account_id) : "" })
    setShowForm(true); setMsg(null)
  }

  const save = async () => {
    setSaving(true); setMsg(null)
    try {
      const payload = { name: form.name, account_id: form.account_id ? Number(form.account_id) : null }
      if (editId) {
        await api.patch(`/admin/product-groups/${editId}`, payload)
        setMsg({ type: "success", text: "Группа обновлена" })
      } else {
        await api.post("/admin/product-groups", payload)
        setMsg({ type: "success", text: "Группа создана" })
      }
      await load(); setShowForm(false)
    } catch (e: any) {
      setMsg({ type: "error", text: e.response?.data?.detail || e.message })
    } finally { setSaving(false) }
  }

  const remove = async (id: number, name: string) => {
    if (!confirm(`Удалить группу «${name}»? Товары в ней станут без группы.`)) return
    try { await api.delete(`/admin/product-groups/${id}`); await load() }
    catch (e: any) { setMsg({ type: "error", text: e.response?.data?.detail || e.message }) }
  }

  const accountName = (id: number | null) => accounts.find((a) => a.id === id)?.name ?? "—"

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-brand-muted text-sm">{groups.length} групп товаров</p>
        <button className="btn-primary text-sm py-2" onClick={openNew}>
          <Plus size={15} /> Добавить группу
        </button>
      </div>

      {msg && <Alert type={msg.type} message={msg.text} />}

      {showForm && (
        <div className="card p-5 mb-5 border-2 border-brand-yellow/30">
          <h3 className="font-semibold text-brand-dark mb-4">{editId ? "Редактировать" : "Новая"} группа</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="text-xs font-medium text-brand-muted uppercase tracking-wide mb-1.5 block">Название</label>
              <input className="input w-full" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
            </div>
            <div>
              <label className="text-xs font-medium text-brand-muted uppercase tracking-wide mb-1.5 block">Счёт списания IIKO</label>
              <select className="input w-full" value={form.account_id} onChange={(e) => setForm((f) => ({ ...f, account_id: e.target.value }))}>
                <option value="">— не привязан —</option>
                {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
            </div>
          </div>
          <div className="flex gap-2">
            <button className="btn-primary" onClick={save} disabled={saving}>
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Сохранить
            </button>
            <button className="btn-secondary" onClick={() => setShowForm(false)}><X size={14} /> Отмена</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-10"><Loader2 size={24} className="animate-spin text-brand-muted" /></div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-brand-border bg-brand-bg/50">
                {["Группа", "Счёт IIKO", ""].map((h) => (
                  <th key={h} className="text-left py-2.5 px-4 text-brand-muted font-medium text-xs uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {groups.map((g) => (
                <tr key={g.id} className="border-b border-brand-border/50 hover:bg-brand-bg/60 transition-colors">
                  <td className="py-3 px-4 font-medium text-brand-dark">{g.name}</td>
                  <td className="py-3 px-4 text-xs text-brand-muted">{accountName(g.account_id)}</td>
                  <td className="py-3 px-4">
                    <div className="flex gap-2 justify-end">
                      <button className="btn-secondary py-1 px-2 text-xs" onClick={() => openEdit(g)}><Edit2 size={12} /> Изменить</button>
                      <button className="btn-danger py-1 px-2 text-xs" onClick={() => remove(g.id, g.name)}><Trash2 size={12} /></button>
                    </div>
                  </td>
                </tr>
              ))}
              {groups.length === 0 && (
                <tr><td colSpan={3} className="text-center py-10 text-brand-muted text-sm">Нет групп. Добавьте первую.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Tab: Accounts ─────────────────────────────────────────────────────────────

function AccountsTab() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [groups, setGroups] = useState<ProductGroup[]>([])
  const [restaurants, setRestaurants] = useState<Restaurant[]>([])
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null)
  const [editId, setEditId] = useState<number | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ account_iiko_id: "", name: "" })
  const [saving, setSaving] = useState(false)
  const [savingGroup, setSavingGroup] = useState<number | null>(null)
  const [syncRestId, setSyncRestId] = useState<string>("")
  const [syncing, setSyncing] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [accRes, grpRes, restRes] = await Promise.all([
        api.get("/admin/accounts"),
        api.get("/admin/product-groups"),
        api.get("/admin/restaurants"),
      ])
      setAccounts(accRes.data)
      setGroups(grpRes.data)
      const active = restRes.data.filter((r: Restaurant) => r.is_active && r.base_url)
      setRestaurants(active)
      if (active.length > 0 && !syncRestId) setSyncRestId(String(active[0].id))
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const syncFromIiko = async () => {
    if (!syncRestId) return
    setSyncing(true); setMsg(null)
    try {
      const { data } = await api.post(`/admin/iiko/sync-accounts/${syncRestId}`)
      setMsg({ type: "success", text: `Синхронизировано из IIKO: добавлено ${data.added}, обновлено ${data.updated}, всего ${data.total}` })
      await load()
    } catch (e: any) {
      setMsg({ type: "error", text: e.response?.data?.detail || e.message })
    } finally { setSyncing(false) }
  }

  const openNew = () => { setEditId(null); setForm({ account_iiko_id: "", name: "" }); setShowForm(true); setMsg(null) }
  const openEdit = (a: Account) => { setEditId(a.id); setForm({ account_iiko_id: a.account_iiko_id, name: a.name }); setShowForm(true); setMsg(null) }

  const save = async () => {
    setSaving(true); setMsg(null)
    try {
      if (editId) {
        await api.patch(`/admin/accounts/${editId}`, form)
        setMsg({ type: "success", text: "Счёт обновлён" })
      } else {
        await api.post("/admin/accounts", form)
        setMsg({ type: "success", text: "Счёт создан" })
      }
      await load(); setShowForm(false)
    } catch (e: any) {
      setMsg({ type: "error", text: e.response?.data?.detail || e.message })
    } finally { setSaving(false) }
  }

  const remove = async (id: number, name: string) => {
    if (!confirm(`Удалить счёт «${name}»? Все связанные группы будут отвязаны.`)) return
    try { await api.delete(`/admin/accounts/${id}`); await load() }
    catch (e: any) { setMsg({ type: "error", text: e.response?.data?.detail || e.message }) }
  }

  const assignAccount = async (groupId: number, accountId: number | null) => {
    setSavingGroup(groupId)
    try {
      await api.patch(`/admin/product-groups/${groupId}`, { account_id: accountId })
      setGroups((prev) => prev.map((g) => g.id === groupId ? { ...g, account_id: accountId } : g))
    } catch (e: any) {
      setMsg({ type: "error", text: e.response?.data?.detail || e.message })
    } finally { setSavingGroup(null) }
  }

  if (loading) return <div className="flex justify-center py-10"><Loader2 size={24} className="animate-spin text-brand-muted" /></div>

  return (
    <div className="space-y-6">
      {msg && <Alert type={msg.type} message={msg.text} />}

      {/* Sync from IIKO */}
      <div className="card p-5 mb-5">
        <h3 className="font-semibold text-brand-dark flex items-center gap-2 mb-1">
          <RefreshCw size={15} className="text-brand-yellow" /> Загрузить счета из IIKO автоматически
        </h3>
        <p className="text-sm text-brand-muted mb-3">
          UUID счетов хранятся в IIKO. Выберите ресторан и нажмите «Синхронизировать» — счета подтянутся автоматически.
        </p>
        <div className="flex gap-3 items-center flex-wrap">
          <select
            className="input text-sm py-2 min-w-[220px]"
            value={syncRestId}
            onChange={(e) => setSyncRestId(e.target.value)}
          >
            {restaurants.map((r) => <option key={r.id} value={r.id}>{r.name} ({r.code})</option>)}
          </select>
          <button className="btn-primary" onClick={syncFromIiko} disabled={syncing || !syncRestId}>
            {syncing ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            Синхронизировать из IIKO
          </button>
        </div>
      </div>

      {/* Accounts CRUD */}
      <div className="card">
        <div className="flex items-center justify-between px-5 py-4 border-b border-brand-border">
          <h3 className="font-semibold text-brand-dark flex items-center gap-2">
            <CreditCard size={15} className="text-brand-yellow" /> Счета списания IIKO
          </h3>
          <button className="btn-primary text-sm py-1.5" onClick={openNew}>
            <Plus size={14} /> Добавить вручную
          </button>
        </div>

        {showForm && (
          <div className="p-5 border-b border-brand-border bg-brand-bg/30">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="text-xs font-medium text-brand-muted uppercase tracking-wide mb-1.5 block">IIKO Account UUID</label>
                <input className="input w-full font-mono text-xs" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                  value={form.account_iiko_id} onChange={(e) => setForm((f) => ({ ...f, account_iiko_id: e.target.value }))} />
              </div>
              <div>
                <label className="text-xs font-medium text-brand-muted uppercase tracking-wide mb-1.5 block">Название</label>
                <input className="input w-full" placeholder="Например: Списание продуктов"
                  value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
              </div>
            </div>
            <div className="flex gap-2">
              <button className="btn-primary" onClick={save} disabled={saving}>
                {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Сохранить
              </button>
              <button className="btn-secondary" onClick={() => setShowForm(false)}><X size={14} /> Отмена</button>
            </div>
          </div>
        )}

        <div className="divide-y divide-brand-border">
          {accounts.length === 0 ? (
            <p className="text-sm text-brand-muted text-center py-8">Нет счетов. Добавьте первый.</p>
          ) : accounts.map((a) => (
            <div key={a.id} className="flex items-start gap-4 px-5 py-3">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-brand-dark">{a.name}</p>
                <p className="text-xs font-mono text-brand-muted mt-0.5">{a.account_iiko_id}</p>
                {a.groups.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1.5">
                    {a.groups.map((g) => (
                      <span key={g.id} className="px-2 py-0.5 rounded-md text-xs bg-brand-yellow/10 text-brand-dark">{g.name}</span>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex gap-2 flex-shrink-0">
                <button className="btn-secondary py-1 px-2 text-xs" onClick={() => openEdit(a)}><Edit2 size={12} /></button>
                <button className="btn-danger py-1 px-2 text-xs" onClick={() => remove(a.id, a.name)}><Trash2 size={12} /></button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Group → Account mapping */}
      <div className="card">
        <div className="px-5 py-4 border-b border-brand-border">
          <h3 className="font-semibold text-brand-dark flex items-center gap-2">
            <BarChart3 size={15} className="text-brand-yellow" /> Привязка групп к счетам
          </h3>
          <p className="text-sm text-brand-muted mt-0.5">Каждая группа товаров должна быть привязана к счёту списания IIKO</p>
        </div>
        <div className="divide-y divide-brand-border">
          {groups.map((g) => (
            <div key={g.id} className="flex items-center gap-4 px-5 py-2.5">
              <p className="flex-1 text-sm text-brand-dark">{g.name}</p>
              <div className="flex items-center gap-2">
                {savingGroup === g.id && <Loader2 size={12} className="animate-spin text-brand-muted" />}
                <select
                  className="input text-xs py-1.5 min-w-[200px]"
                  value={g.account_id ?? ""}
                  onChange={(e) => assignAccount(g.id, e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">— не привязан —</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>{a.name}</option>
                  ))}
                </select>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Tab: Catalog ──────────────────────────────────────────────────────────────

function CatalogTab() {
  const [data, setData] = useState<{ total: number; stats: { total_all: number; no_group: number; deleted: number }; items: CatalogItem[] } | null>(null)
  const [groups, setGroups] = useState<ProductGroup[]>([])
  const [restaurants, setRestaurants] = useState<Restaurant[]>([])
  const [filter, setFilter] = useState("all")
  const [search, setSearch] = useState("")
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null)
  const [syncRestId, setSyncRestId] = useState<string>("")
  const [syncing, setSyncing] = useState(false)
  const [editingGroup, setEditingGroup] = useState<number | null>(null) // product id
  const [savingGroup, setSavingGroup] = useState<number | null>(null)

  const load = async (f = filter, s = search) => {
    setLoading(true)
    try {
      const res = await api.get(`/admin/product-catalog?filter=${f}&search=${encodeURIComponent(s)}&limit=200`)
      setData(res.data)
    } finally { setLoading(false) }
  }

  useEffect(() => {
    load()
    api.get("/admin/product-groups").then((r) => setGroups(r.data))
    api.get("/admin/restaurants").then((r) => {
      const active = r.data.filter((x: Restaurant) => x.is_active && x.base_url)
      setRestaurants(active)
      if (active.length > 0) setSyncRestId(String(active[0].id))
    })
  }, [])

  const handleFilter = (f: string) => { setFilter(f); load(f, search) }
  const handleSearch = (s: string) => { setSearch(s); if (s.length === 0 || s.length >= 2) load(filter, s) }

  const syncCatalog = async () => {
    if (!syncRestId) return
    setSyncing(true); setMsg(null)
    try {
      const { data: d } = await api.post(`/admin/iiko/sync-catalog/${syncRestId}`)
      setMsg({ type: "success", text: `Синхронизировано: добавлено ${d.added}, обновлено ${d.updated}, без группы ${d.unmapped} из ${d.total}` })
      await load()
    } catch (e: any) {
      setMsg({ type: "error", text: e.response?.data?.detail || e.message })
    } finally { setSyncing(false) }
  }

  const changeGroup = async (productId: number, groupId: number | null) => {
    setSavingGroup(productId)
    try {
      await api.patch(`/admin/product-catalog/${productId}`, { group_id: groupId })
      setData((prev) => prev ? {
        ...prev,
        items: prev.items.map((it) => it.id === productId
          ? { ...it, group_id: groupId, group: groups.find((g) => g.id === groupId)?.name ?? null }
          : it
        ),
      } : prev)
      setEditingGroup(null)
    } catch (e: any) {
      setMsg({ type: "error", text: e.response?.data?.detail || e.message })
    } finally { setSavingGroup(null) }
  }

  return (
    <div>
      {/* Sync from IIKO */}
      <div className="card p-5 mb-5">
        <h3 className="font-semibold text-brand-dark flex items-center gap-2 mb-1">
          <Database size={15} className="text-brand-yellow" /> Выгрузка товаров из IIKO
        </h3>
        <p className="text-sm text-brand-muted mb-3">
          Загружает номенклатуру из IIKO. Новые товары появляются без группы — их нужно будет назначить вручную.
        </p>
        <div className="flex gap-3 items-center flex-wrap">
          <select className="input text-sm py-2 min-w-[220px]" value={syncRestId} onChange={(e) => setSyncRestId(e.target.value)}>
            {restaurants.map((r) => <option key={r.id} value={r.id}>{r.name} ({r.code})</option>)}
          </select>
          <button className="btn-primary" onClick={syncCatalog} disabled={syncing || !syncRestId}>
            {syncing ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            Выгрузить из IIKO
          </button>
        </div>
        {msg && <div className="mt-3"><Alert type={msg.type} message={msg.text} /></div>}
      </div>

      {/* Stats */}
      {data && (
        <div className="grid grid-cols-4 gap-4 mb-5">
          {[
            { label: "Всего товаров", value: data.stats.total_all, color: "text-brand-dark" },
            { label: "Активные", value: data.stats.total_all - data.stats.deleted, color: "text-green-600" },
            { label: "Удалены в IIKO", value: data.stats.deleted, color: data.stats.deleted > 0 ? "text-orange-500" : "text-brand-muted" },
            { label: "Без группы", value: data.stats.no_group, color: data.stats.no_group > 0 ? "text-brand-red" : "text-green-600" },
          ].map(({ label, value, color }) => (
            <div key={label} className="card p-4 text-center">
              <p className={cn("text-2xl font-bold", color)}>{value}</p>
              <p className="text-xs text-brand-muted mt-1">{label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Filters + search */}
      <div className="flex flex-wrap gap-3 mb-4">
        <div className="flex gap-1">
          {[
            { key: "all",      label: "Все" },
            { key: "no_group", label: "Без группы" },
            { key: "deleted",  label: "Удалённые в IIKO" },
          ].map(({ key, label }) => (
            <button key={key} onClick={() => handleFilter(key)}
              className={cn("px-3 py-1.5 text-xs font-medium rounded-lg transition-colors",
                filter === key ? "bg-brand-yellow text-brand-dark" : "text-brand-muted hover:bg-brand-bg border border-brand-border")}>
              {label}
            </button>
          ))}
        </div>
        <input className="input text-sm py-1.5 min-w-[240px]" placeholder="Поиск по коду или названию..."
          value={search} onChange={(e) => handleSearch(e.target.value)} />
      </div>

      {loading ? (
        <div className="flex justify-center py-10"><Loader2 size={24} className="animate-spin text-brand-muted" /></div>
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-brand-border bg-brand-bg/50">
                  {["Код", "Наименование", "Группа", "Ед.", "Статус", ""].map((h) => (
                    <th key={h} className="text-left py-2.5 px-4 text-brand-muted font-medium text-xs uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data?.items.map((item) => (
                  <tr key={item.id} className={cn("border-b border-brand-border/50 hover:bg-brand-bg/40 transition-colors",
                    item.is_deleted ? "bg-orange-50/40" : !item.group_id && "bg-red-50/40")}>
                    <td className="py-2 px-4 font-mono text-xs text-brand-muted">{item.product_num}</td>
                    <td className="py-2 px-4 font-medium text-brand-dark max-w-[240px] truncate">{item.name}</td>
                    <td className="py-2 px-4 text-xs">
                      {editingGroup === item.id ? (
                        <div className="flex items-center gap-1">
                          <select
                            className="input text-xs py-1 min-w-[160px]"
                            defaultValue={item.group_id ?? ""}
                            onChange={(e) => changeGroup(item.id, e.target.value ? Number(e.target.value) : null)}
                          >
                            <option value="">— без группы —</option>
                            {groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
                          </select>
                          {savingGroup === item.id && <Loader2 size={12} className="animate-spin text-brand-muted" />}
                          <button className="text-brand-muted hover:text-brand-red" onClick={() => setEditingGroup(null)}><X size={12} /></button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1.5">
                          {item.group
                            ? <span className="px-2 py-0.5 rounded bg-brand-yellow/10 text-brand-dark">{item.group}</span>
                            : <span className="badge-over text-xs">Нет группы</span>
                          }
                        </div>
                      )}
                    </td>
                    <td className="py-2 px-4 text-xs text-brand-muted">{item.unit_type ?? "—"}</td>
                    <td className="py-2 px-4 text-xs">
                      {item.is_deleted
                        ? <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-orange-100 text-orange-700 font-medium">Удалён в IIKO</span>
                        : <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-100 text-green-700 font-medium">Активен</span>
                      }
                    </td>
                    <td className="py-2 px-2 text-xs">
                      {editingGroup !== item.id && (
                        <button
                          className="btn-secondary py-0.5 px-2 text-xs"
                          onClick={() => setEditingGroup(item.id)}
                        >
                          <Edit2 size={11} /> Группа
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {data?.items.length === 0 && (
                  <tr><td colSpan={5} className="text-center py-10 text-brand-muted text-sm">Ничего не найдено</td></tr>
                )}
              </tbody>
            </table>
          </div>
          {data && (
            <div className="px-4 py-2 border-t border-brand-border text-xs text-brand-muted">
              Показано: {data.items.length} из {data.total}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Tab: Presets ──────────────────────────────────────────────────────────────

function PresetsTab() {
  const [presets, setPresets] = useState<Preset[]>([])
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null)
  const [editId, setEditId] = useState<number | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ preset_type: "sales", preset_uuid: "", description: "" })
  const [saving, setSaving] = useState(false)

  const load = async () => {
    setLoading(true)
    try { const r = await api.get("/admin/presets"); setPresets(r.data) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const openNew = () => {
    setEditId(null)
    setForm({ preset_type: "sales", preset_uuid: "", description: "" })
    setShowForm(true); setMsg(null)
  }

  const openEdit = (p: Preset) => {
    setEditId(p.id)
    setForm({ preset_type: p.preset_type, preset_uuid: p.preset_uuid, description: p.description ?? "" })
    setShowForm(true); setMsg(null)
  }

  const save = async () => {
    setSaving(true); setMsg(null)
    try {
      const payload = { ...form, description: form.description || null }
      if (editId) {
        await api.patch(`/admin/presets/${editId}`, payload)
        setMsg({ type: "success", text: "Пресет обновлён" })
      } else {
        await api.post("/admin/presets", payload)
        setMsg({ type: "success", text: "Пресет создан" })
      }
      await load(); setShowForm(false)
    } catch (e: any) {
      setMsg({ type: "error", text: e.response?.data?.detail || e.message })
    } finally { setSaving(false) }
  }

  const remove = async (id: number, type: string) => {
    if (!confirm(`Удалить пресет «${PRESET_LABELS[type] ?? type}»? Он будет отвязан от всех ресторанов.`)) return
    try { await api.delete(`/admin/presets/${id}`); await load() }
    catch (e: any) { setMsg({ type: "error", text: e.response?.data?.detail || e.message }) }
  }

  const grouped = PRESET_TYPES.map((type) => ({
    type,
    label: PRESET_LABELS[type],
    items: presets.filter((p) => p.preset_type === type),
  }))

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <p className="text-brand-muted text-sm">{presets.length} пресетов · настроены независимо от ресторанов</p>
          <p className="text-xs text-brand-muted mt-0.5">Один пресет (UUID) можно назначить нескольким ресторанам сразу</p>
        </div>
        <button className="btn-primary text-sm py-2" onClick={openNew}>
          <Plus size={15} /> Добавить пресет
        </button>
      </div>

      {msg && <Alert type={msg.type} message={msg.text} />}

      {showForm && (
        <div className="card p-5 mb-5 border-2 border-brand-yellow/30">
          <h3 className="font-semibold text-brand-dark mb-4">{editId ? "Редактировать" : "Новый"} пресет</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="text-xs font-medium text-brand-muted uppercase tracking-wide mb-1.5 block">
                Тип пресета (название свободное)
              </label>
              <input
                className="input w-full"
                placeholder="например: sales, revenue_net, my_custom_report"
                value={form.preset_type}
                onChange={(e) => setForm((f) => ({ ...f, preset_type: e.target.value }))}
              />
              <p className="text-xs text-brand-muted mt-1">
                Стандартные: sales · writeoff · inventory · revenue_net · complete_waste
              </p>
            </div>
            <div>
              <label className="text-xs font-medium text-brand-muted uppercase tracking-wide mb-1.5 block">UUID пресета</label>
              <input className="input w-full font-mono text-xs" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                value={form.preset_uuid} onChange={(e) => setForm((f) => ({ ...f, preset_uuid: e.target.value }))} />
            </div>
            <div className="sm:col-span-2">
              <label className="text-xs font-medium text-brand-muted uppercase tracking-wide mb-1.5 block">Описание (необязательно)</label>
              <input className="input w-full" placeholder="Например: Продажи для всей сети"
                value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} />
            </div>
          </div>
          <div className="flex gap-2">
            <button className="btn-primary" onClick={save} disabled={saving}>
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Сохранить
            </button>
            <button className="btn-secondary" onClick={() => setShowForm(false)}><X size={14} /> Отмена</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-10"><Loader2 size={24} className="animate-spin text-brand-muted" /></div>
      ) : (
        <div className="space-y-4">
          {grouped.map(({ type, label, items }) => (
            <div key={type} className="card overflow-hidden">
              <div className="px-5 py-3 border-b border-brand-border bg-brand-bg/50 flex items-center gap-2">
                <Layers size={14} className="text-brand-yellow" />
                <span className="font-medium text-brand-dark text-sm">{label}</span>
                <span className="ml-auto text-xs text-brand-muted">{items.length} шт.</span>
              </div>
              {items.length === 0 ? (
                <p className="text-xs text-brand-muted text-center py-4">Нет пресетов этого типа</p>
              ) : (
                <div className="divide-y divide-brand-border/50">
                  {items.map((p) => (
                    <div key={p.id} className="flex items-start gap-4 px-5 py-3">
                      <div className="flex-1 min-w-0">
                        <p className="font-mono text-xs text-brand-dark mb-0.5">{p.preset_uuid}</p>
                        {p.description && <p className="text-xs text-brand-muted">{p.description}</p>}
                        {p.restaurants.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1.5">
                            {p.restaurants.map((r) => (
                              <span key={r.id} className="px-2 py-0.5 rounded bg-brand-yellow/10 text-brand-dark text-xs">{r.code}</span>
                            ))}
                          </div>
                        )}
                        {p.restaurants.length === 0 && (
                          <span className="text-xs text-brand-muted italic">Не назначен ни одному ресторану</span>
                        )}
                      </div>
                      <div className="flex gap-2 flex-shrink-0">
                        <button className="btn-secondary py-1 px-2 text-xs" onClick={() => openEdit(p)}><Edit2 size={12} /></button>
                        <button className="btn-danger py-1 px-2 text-xs" onClick={() => remove(p.id, p.preset_type)}><Trash2 size={12} /></button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Tab: ABL Mapping ──────────────────────────────────────────────────────────

function AblMappingTab() {
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null)
  const [stats, setStats] = useState<{ total: number; linked: number; not_linked: number } | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    api.get("/admin/abl-stats").then((r) => setStats(r.data)).catch(() => {})
  }, [])

  const upload = async () => {
    if (!file) return
    setUploading(true); setMsg(null)
    try {
      const form = new FormData()
      form.append("file", file)
      const { data } = await api.post("/admin/upload-mapping-abl", form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      setMsg({ type: "success", text: `Загружено: ${data.created ?? data.added ?? 0} создано, ${data.updated} обновлено. Привязано к IIKO: ${data.linked_to_iiko} из ${data.total_in_db}` })
      setFile(null)
      if (fileRef.current) fileRef.current.value = ""
      const s = await api.get("/admin/abl-stats"); setStats(s.data)
    } catch (e: any) {
      setMsg({ type: "error", text: e.response?.data?.detail || e.message })
    } finally { setUploading(false) }
  }

  return (
    <div>
      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-3 gap-4 mb-5">
          {[
            { label: "Всего артикулов ABL", value: stats.total, color: "text-brand-dark" },
            { label: "Привязано к IIKO", value: stats.linked, color: "text-green-600" },
            { label: "Не привязано", value: stats.not_linked, color: stats.not_linked > 0 ? "text-brand-red" : "text-green-600" },
          ].map(({ label, value, color }) => (
            <div key={label} className="card p-4 text-center">
              <p className={cn("text-2xl font-bold", color)}>{value}</p>
              <p className="text-xs text-brand-muted mt-1">{label}</p>
            </div>
          ))}
        </div>
      )}

      {msg && <Alert type={msg.type} message={msg.text} />}

      <div className="card p-5">
        <h3 className="font-semibold text-brand-dark mb-1 flex items-center gap-2">
          <Upload size={15} className="text-brand-yellow" /> Загрузить mapping_ABL.xlsx
        </h3>
        <p className="text-sm text-brand-muted mb-4">
          Ежемесячный файл от отдела снабжения. Обновляет базу артикулов ABL и привязку к товарам IIKO.
        </p>
        <div className="flex flex-wrap gap-3 items-end">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-brand-muted uppercase tracking-wide">Файл Excel (.xlsx)</label>
            <input ref={fileRef} type="file" accept=".xlsx"
              className="input cursor-pointer file:mr-3 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:font-medium file:bg-brand-yellow/10 file:text-brand-dark hover:file:bg-brand-yellow/20"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </div>
          <button className="btn-primary" onClick={upload} disabled={uploading || !file}>
            {uploading ? <><Loader2 size={15} className="animate-spin" />Загружаем...</> : <><Upload size={15} />Загрузить</>}
          </button>
        </div>
        <p className="text-xs text-brand-muted mt-3">
          Колонки: Артикул ABL, Основной артикул ABL, Артикул айко, Наименование, Поставщик, Цена продажи, Цена продажи с НДС
        </p>
      </div>
    </div>
  )
}

// ── Tab: Recipes ──────────────────────────────────────────────────────────────

const FSKZ_ID = 35 // Центральный IIKO сервер (iikoChain) — техкарты хранятся здесь

interface RecipeSearchResult {
  chart_id: number
  dish_id: number
  dish_name: string
  dish_iiko_uuid: string
  date_from: string
  date_to: string | null
  matched_ingredients: {
    ingredient_id: number
    ingredient_iiko_uuid: string
    ingredient_name: string
    amount_in: number
  }[]
}

interface RecipeStats {
  dishes: number
  charts: number
  ingredients: number
}

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

interface CatalogSearchResult {
  id: number
  product_num: string
  name: string
  unit_type: string | null
  product_iiko_id: string
}

function RecipesTab() {
  const [stats, setStats] = useState<RecipeStats | null>(null)
  const [search, setSearch] = useState("")
  const [results, setResults] = useState<RecipeSearchResult[] | null>(null)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [syncing, setSyncing] = useState(false)
  const [searching, setSearching] = useState(false)
  const [removing, setRemoving] = useState(false)
  const [replacing, setReplacing] = useState(false)
  const [effectiveDate, setEffectiveDate] = useState(todayIso())
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null)

  // Импорт Excel
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importDate, setImportDate] = useState(todayIso())
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<any>(null)
  const importInputRef = useRef<HTMLInputElement>(null)

  // Форма замены
  const [showReplaceForm, setShowReplaceForm] = useState(false)
  const [newIngSearch, setNewIngSearch] = useState("")
  const [newIngResults, setNewIngResults] = useState<CatalogSearchResult[]>([])
  const [newIngSearching, setNewIngSearching] = useState(false)
  const [selectedNewIng, setSelectedNewIng] = useState<CatalogSearchResult | null>(null)
  const [newAmount, setNewAmount] = useState("")

  const loadStats = async () => {
    try {
      const { data: dishes } = await api.get(`/recipes/dishes?restaurant_id=${FSKZ_ID}`)
      setStats({
        dishes: dishes.length,
        charts: dishes.reduce((s: number, d: any) => s + d.charts_count, 0),
        ingredients: dishes.reduce((s: number, d: any) => s + d.ingredients_count, 0),
      })
    } catch {}
  }

  useEffect(() => { loadStats() }, [])

  const handleSync = async () => {
    setSyncing(true); setMsg(null)
    try {
      const { data } = await api.post(`/recipes/sync/${FSKZ_ID}`, { date_from: "2024-01-01" })
      setMsg({ type: "success", text: `Синхронизировано: ${data.charts_created} новых + ${data.charts_updated} обновлено, ${data.ingredients_total} ингредиентов, ${data.dishes_total} блюд` })
      await loadStats()
      setResults(null); setSelected(new Set())
    } catch (e: any) {
      setMsg({ type: "error", text: e.response?.data?.detail || e.message })
    } finally { setSyncing(false) }
  }

  const handleImportExcel = async () => {
    if (!importFile) return
    setImporting(true); setImportResult(null)
    try {
      const form = new FormData()
      form.append("file", importFile)
      form.append("restaurant_id", String(FSKZ_ID))
      form.append("effective_date", importDate)
      const { data } = await api.post("/recipes/import-excel", form, {
        headers: { "Content-Type": "multipart/form-data" },
      })
      setImportResult(data)
      await loadStats()
    } catch (e: any) {
      setImportResult({ error: e.response?.data?.detail || e.message })
    } finally { setImporting(false) }
  }

  const handleSearch = async () => {
    if (!search.trim()) return
    setSearching(true); setMsg(null); setSelected(new Set())
    setShowReplaceForm(false); setSelectedNewIng(null); setNewIngSearch(""); setNewIngResults([])
    try {
      const { data } = await api.get(`/recipes/search?restaurant_id=${FSKZ_ID}&ingredient=${encodeURIComponent(search.trim())}`)
      setResults(data)
      if (data.length === 0) setMsg({ type: "error", text: `Ингредиент «${search}» не найден ни в одной техкарте` })
    } catch (e: any) {
      setMsg({ type: "error", text: e.response?.data?.detail || e.message })
    } finally { setSearching(false) }
  }

  const toggleAll = () => {
    if (!results) return
    if (selected.size === results.length) setSelected(new Set())
    else setSelected(new Set(results.map((r) => r.chart_id)))
  }

  const toggle = (chartId: number) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(chartId) ? next.delete(chartId) : next.add(chartId)
      return next
    })
  }

  const ingredientUuid = results?.[0]?.matched_ingredients?.[0]?.ingredient_iiko_uuid ?? ""
  const ingredientName = results?.[0]?.matched_ingredients?.[0]?.ingredient_name ?? search

  const handleBulkRemove = async () => {
    if (selected.size === 0) return
    if (!confirm(
      `Удалить «${ingredientName}» из ${selected.size} техкарт в IIKO?\n\n` +
      `Дата вступления в силу: ${effectiveDate}\n` +
      `Старые техкарты останутся в истории IIKO. Изменение нельзя отменить.`
    )) return

    setRemoving(true); setMsg(null)
    try {
      const { data } = await api.post("/recipes/bulk-remove-ingredient", {
        restaurant_id: FSKZ_ID,
        ingredient_iiko_uuid: ingredientUuid,
        chart_ids: Array.from(selected),
        effective_date: effectiveDate,
      })
      const skipped = data.results?.filter((r: any) => r.skipped).length ?? 0
      const failed  = data.results?.filter((r: any) => !r.ok).length ?? 0
      setMsg({
        type: failed === 0 ? "success" : "error",
        text: `В IIKO созданы новые техкарты: ${data.ok} шт. с ${effectiveDate}` +
              (skipped > 0 ? ` · пропущено: ${skipped}` : "") +
              (failed  > 0 ? ` · ошибок: ${failed}` : ""),
      })
      setResults((prev) => prev ? prev.filter((r) => !selected.has(r.chart_id)) : prev)
      setSelected(new Set())
    } catch (e: any) {
      setMsg({ type: "error", text: e.response?.data?.detail || e.message })
    } finally { setRemoving(false) }
  }

  const handleSearchNewIng = async () => {
    if (!newIngSearch.trim()) return
    setNewIngSearching(true)
    try {
      const { data } = await api.get(`/admin/product-catalog?search=${encodeURIComponent(newIngSearch.trim())}&limit=15&filter=all`)
      setNewIngResults(data.items ?? data ?? [])
    } catch {}
    finally { setNewIngSearching(false) }
  }

  const handleBulkReplace = async () => {
    if (selected.size === 0 || !selectedNewIng || !newAmount) return
    const amt = parseFloat(newAmount)
    if (isNaN(amt) || amt <= 0) { setMsg({ type: "error", text: "Введите корректное количество" }); return }

    if (!confirm(
      `Заменить «${ingredientName}» → «${selectedNewIng.name}» (${amt}) в ${selected.size} техкартах?\n\n` +
      `Дата вступления в силу: ${effectiveDate}\n` +
      `Изменение нельзя отменить.`
    )) return

    setReplacing(true); setMsg(null)
    try {
      const { data } = await api.post("/recipes/bulk-replace-ingredient", {
        restaurant_id: FSKZ_ID,
        old_ingredient_uuid: ingredientUuid,
        new_ingredient_uuid: selectedNewIng.product_iiko_id,
        new_ingredient_name: selectedNewIng.name,
        new_amount_in: amt,
        chart_ids: Array.from(selected),
        effective_date: effectiveDate,
      })
      const skipped = data.results?.filter((r: any) => r.skipped).length ?? 0
      const failed  = data.results?.filter((r: any) => !r.ok).length ?? 0
      setMsg({
        type: failed === 0 ? "success" : "error",
        text: `Замена выполнена: ${data.ok} шт. с ${effectiveDate}` +
              (skipped > 0 ? ` · пропущено: ${skipped}` : "") +
              (failed  > 0 ? ` · ошибок: ${failed}` : ""),
      })
      setResults((prev) => prev ? prev.filter((r) => !selected.has(r.chart_id)) : prev)
      setSelected(new Set())
      setShowReplaceForm(false); setSelectedNewIng(null); setNewIngSearch(""); setNewIngResults([])
    } catch (e: any) {
      setMsg({ type: "error", text: e.response?.data?.detail || e.message })
    } finally { setReplacing(false) }
  }

  return (
    <div>
      {/* Sync card */}
      <div className="card p-5 mb-5">
        <h3 className="font-semibold text-brand-dark flex items-center gap-2 mb-1">
          <ChefHat size={15} className="text-brand-yellow" /> Технологические карты — FSKZ (центральный сервер)
        </h3>
        <p className="text-sm text-brand-muted mb-3">
          Синхронизирует техкарты из центрального iikoChain. Изменения здесь применяются ко всей сети ресторанов.
        </p>
        <button className="btn-primary" onClick={handleSync} disabled={syncing}>
          {syncing ? <><Loader2 size={14} className="animate-spin" />Синхронизация...</> : <><RefreshCw size={14} />Синхронизировать с IIKO</>}
        </button>
        {msg && <div className="mt-3"><Alert type={msg.type} message={msg.text} /></div>}
      </div>

      {/* Excel Import */}
      <div className="card p-5 mb-5">
        <h3 className="font-semibold text-brand-dark flex items-center gap-2 mb-1">
          <FileSpreadsheet size={15} className="text-green-600" /> Импорт рецептур из Excel
        </h3>
        <p className="text-sm text-brand-muted mb-3">
          Формат файла: <span className="font-mono text-xs bg-brand-bg px-1.5 py-0.5 rounded">Название блюда | Код блюда | Код товара | Ед. изм. | Фактор</span>.
          Блюда должны быть синхронизированы, товары — в каталоге.
        </p>
        <div className="flex gap-2 items-center flex-wrap">
          <input
            ref={importInputRef}
            type="file"
            accept=".xlsx,.xls"
            className="hidden"
            onChange={(e) => setImportFile(e.target.files?.[0] ?? null)}
          />
          <button className="btn-secondary text-sm" onClick={() => importInputRef.current?.click()}>
            <FileSpreadsheet size={14} />
            {importFile ? importFile.name : "Выбрать файл..."}
          </button>
          <div className="flex items-center gap-1.5">
            <label className="text-xs text-brand-muted whitespace-nowrap">С даты:</label>
            <input
              type="date"
              className="input text-xs py-1 px-2 min-w-[130px]"
              value={importDate}
              onChange={(e) => setImportDate(e.target.value)}
            />
          </div>
          <button
            className={`btn-primary text-sm ${!importFile || importing ? "opacity-50 cursor-not-allowed" : ""}`}
            onClick={handleImportExcel}
            disabled={!importFile || importing}
          >
            {importing ? <><Loader2 size={14} className="animate-spin" />Загрузка...</> : <><Upload size={14} />Загрузить и создать</>}
          </button>
          {importFile && !importing && (
            <button className="text-brand-muted hover:text-brand-red" onClick={() => { setImportFile(null); setImportResult(null); if (importInputRef.current) importInputRef.current.value = "" }}>
              <X size={16} />
            </button>
          )}
        </div>

        {importResult && (
          <div className="mt-3">
            {importResult.error ? (
              <Alert type="error" message={importResult.error} />
            ) : (
              <div>
                <Alert
                  type={importResult.failed === 0 ? "success" : "error"}
                  message={`Создано техкарт: ${importResult.ok} · ошибок: ${importResult.failed} · дата: ${importResult.effective_date}`}
                />
                {importResult.parse_errors?.length > 0 && (
                  <div className="mt-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800">
                    <p className="font-semibold mb-1">Предупреждения при разборе файла:</p>
                    {importResult.parse_errors.slice(0, 10).map((e: string, i: number) => (
                      <p key={i}>• {e}</p>
                    ))}
                    {importResult.parse_errors.length > 10 && <p>...и ещё {importResult.parse_errors.length - 10}</p>}
                  </div>
                )}
                {importResult.results?.filter((r: any) => !r.ok).length > 0 && (
                  <div className="mt-2 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-800">
                    <p className="font-semibold mb-1">Ошибки при создании в IIKO:</p>
                    {importResult.results.filter((r: any) => !r.ok).slice(0, 10).map((r: any, i: number) => (
                      <p key={i}>• {r.dish_code} {r.dish_name && `(${r.dish_name})`}: {r.error}</p>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-3 gap-4 mb-5">
          {[
            { label: "Блюд / заготовок", value: stats.dishes },
            { label: "Техкарт", value: stats.charts },
            { label: "Ингредиентов (активных)", value: stats.ingredients },
          ].map(({ label, value }) => (
            <div key={label} className="card p-4 text-center">
              <p className="text-2xl font-bold text-brand-dark">{value.toLocaleString()}</p>
              <p className="text-xs text-brand-muted mt-1">{label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Search */}
      <div className="card p-5 mb-5">
        <h3 className="font-semibold text-brand-dark mb-3">Поиск по ингредиенту</h3>
        <div className="flex gap-2">
          <input
            className="input flex-1 text-sm"
            placeholder="Например: САЛФЕТКИ СУХИЕ, булка, соус..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
          <button className="btn-primary" onClick={handleSearch} disabled={searching || !search.trim()}>
            {searching ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
            Найти
          </button>
        </div>
      </div>

      {/* Results */}
      {results && results.length > 0 && (
        <div className="card overflow-hidden">
          {/* Action bar */}
          <div className="px-4 py-3 bg-brand-bg/50 border-b border-brand-border">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium text-brand-dark">
                  Найдено: <span className="text-brand-yellow font-bold">{results.length}</span> техкарт с «{ingredientName}»
                </span>
                {selected.size > 0 && (
                  <span className="text-xs text-brand-muted">выбрано: {selected.size}</span>
                )}
              </div>
              <div className="flex gap-2 items-center flex-wrap">
                <div className="flex items-center gap-1.5">
                  <label className="text-xs text-brand-muted whitespace-nowrap">С даты:</label>
                  <input
                    type="date"
                    className="input text-xs py-1 px-2 min-w-[130px]"
                    value={effectiveDate}
                    onChange={(e) => setEffectiveDate(e.target.value)}
                  />
                </div>
                <button className="btn-secondary text-xs py-1.5 px-3" onClick={toggleAll}>
                  {selected.size === results.length ? "Снять все" : "Выбрать все"}
                </button>
                {/* Замена */}
                <button
                  className={`flex items-center gap-1.5 text-xs py-1.5 px-3 rounded-lg font-medium transition-colors ${
                    selected.size > 0
                      ? showReplaceForm
                        ? "bg-brand-dark text-white"
                        : "bg-blue-600 text-white hover:bg-blue-700"
                      : "bg-brand-border text-brand-muted cursor-not-allowed"
                  }`}
                  onClick={() => { setShowReplaceForm((v) => !v); setSelectedNewIng(null); setNewIngResults([]); setNewIngSearch("") }}
                  disabled={selected.size === 0}
                >
                  <ArrowLeftRight size={13} />
                  Заменить ({selected.size})
                </button>
                {/* Удаление */}
                <button
                  className={`flex items-center gap-1.5 text-xs py-1.5 px-3 rounded-lg font-medium transition-colors ${
                    selected.size > 0 && !removing
                      ? "bg-brand-red text-white hover:bg-brand-red/90"
                      : "bg-brand-border text-brand-muted cursor-not-allowed"
                  }`}
                  onClick={handleBulkRemove}
                  disabled={selected.size === 0 || removing}
                >
                  {removing ? <Loader2 size={13} className="animate-spin" /> : <Trash size={13} />}
                  Удалить ({selected.size})
                </button>
              </div>
            </div>

            {/* Форма замены */}
            {showReplaceForm && (
              <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <p className="text-sm font-semibold text-blue-900 mb-3 flex items-center gap-2">
                  <ArrowLeftRight size={14} />
                  Заменить «{ingredientName}» на:
                </p>

                {/* Выбор нового продукта */}
                {!selectedNewIng ? (
                  <div className="mb-3">
                    <div className="flex gap-2 mb-2">
                      <input
                        className="input flex-1 text-sm"
                        placeholder="Название нового продукта..."
                        value={newIngSearch}
                        onChange={(e) => setNewIngSearch(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && handleSearchNewIng()}
                      />
                      <button className="btn-primary text-xs py-1.5 px-3" onClick={handleSearchNewIng} disabled={newIngSearching || !newIngSearch.trim()}>
                        {newIngSearching ? <Loader2 size={13} className="animate-spin" /> : <Search size={13} />}
                        Найти
                      </button>
                    </div>
                    {newIngResults.length > 0 && (
                      <div className="border border-brand-border rounded-lg overflow-hidden max-h-48 overflow-y-auto bg-white">
                        {newIngResults.map((p) => (
                          <div
                            key={p.id}
                            className="px-3 py-2 hover:bg-brand-yellow/10 cursor-pointer border-b border-brand-border/50 last:border-0"
                            onClick={() => { setSelectedNewIng(p); setNewIngResults([]) }}
                          >
                            <span className="text-xs font-mono text-brand-muted mr-2">{p.product_num}</span>
                            <span className="text-sm text-brand-dark">{p.name}</span>
                            {p.unit_type && <span className="ml-2 text-xs text-brand-muted">({p.unit_type})</span>}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex items-center gap-2 mb-3 p-2 bg-white border border-blue-300 rounded-lg">
                    <CheckCircle2 size={14} className="text-green-600 shrink-0" />
                    <span className="text-sm font-medium text-brand-dark flex-1">{selectedNewIng.name}</span>
                    <span className="text-xs text-brand-muted">{selectedNewIng.product_num}</span>
                    <button className="text-brand-muted hover:text-brand-red ml-1" onClick={() => { setSelectedNewIng(null); setNewIngResults([]) }}>
                      <X size={14} />
                    </button>
                  </div>
                )}

                {/* Количество */}
                <div className="flex items-center gap-3 mb-3">
                  <label className="text-sm text-blue-900 whitespace-nowrap">Количество (брутто):</label>
                  <input
                    type="number"
                    min="0"
                    step="0.001"
                    className="input w-32 text-sm"
                    placeholder="напр. 1.5"
                    value={newAmount}
                    onChange={(e) => setNewAmount(e.target.value)}
                  />
                  {selectedNewIng?.unit_type && (
                    <span className="text-xs text-brand-muted">{selectedNewIng.unit_type}</span>
                  )}
                </div>

                {/* Кнопки */}
                <div className="flex gap-2">
                  <button
                    className={`flex items-center gap-1.5 text-sm py-2 px-4 rounded-lg font-medium transition-colors ${
                      selectedNewIng && newAmount && !replacing
                        ? "bg-blue-600 text-white hover:bg-blue-700"
                        : "bg-brand-border text-brand-muted cursor-not-allowed"
                    }`}
                    onClick={handleBulkReplace}
                    disabled={!selectedNewIng || !newAmount || replacing}
                  >
                    {replacing ? <Loader2 size={14} className="animate-spin" /> : <ArrowLeftRight size={14} />}
                    Применить замену в {selected.size} техкартах
                  </button>
                  <button className="btn-secondary text-sm py-2 px-4" onClick={() => setShowReplaceForm(false)}>
                    Отмена
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-brand-border">
                  <th className="py-2.5 px-4 w-10">
                    <input type="checkbox" checked={selected.size === results.length} onChange={toggleAll} className="rounded border-brand-border" />
                  </th>
                  <th className="text-left py-2.5 px-4 text-brand-muted font-medium text-xs uppercase tracking-wide">Блюдо / заготовка</th>
                  <th className="text-left py-2.5 px-4 text-brand-muted font-medium text-xs uppercase tracking-wide">Ингредиент</th>
                  <th className="text-left py-2.5 px-4 text-brand-muted font-medium text-xs uppercase tracking-wide">Кол-во (брутто)</th>
                  <th className="text-left py-2.5 px-4 text-brand-muted font-medium text-xs uppercase tracking-wide">Период</th>
                </tr>
              </thead>
              <tbody>
                {results.map((row) => (
                  <tr
                    key={row.chart_id}
                    className={cn(
                      "border-b border-brand-border/50 hover:bg-brand-bg/40 transition-colors cursor-pointer",
                      selected.has(row.chart_id) && "bg-brand-yellow/5"
                    )}
                    onClick={() => toggle(row.chart_id)}
                  >
                    <td className="py-2 px-4" onClick={(e) => e.stopPropagation()}>
                      <input type="checkbox" checked={selected.has(row.chart_id)} onChange={() => toggle(row.chart_id)} className="rounded border-brand-border" />
                    </td>
                    <td className="py-2 px-4 font-medium text-brand-dark max-w-[260px]">
                      <span className="truncate block">{row.dish_name}</span>
                    </td>
                    <td className="py-2 px-4 text-xs">
                      {row.matched_ingredients.map((m) => (
                        <span key={m.ingredient_id} className="inline-block px-2 py-0.5 rounded bg-brand-yellow/10 text-brand-dark mr-1">
                          {m.ingredient_name}
                        </span>
                      ))}
                    </td>
                    <td className="py-2 px-4 text-sm font-mono text-brand-dark">
                      {row.matched_ingredients.map((m) => m.amount_in).join(", ")}
                    </td>
                    <td className="py-2 px-4 text-xs text-brand-muted">
                      {row.date_from} → {row.date_to ?? "∞"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────────

// ── Tab: Access (feature flags per restaurant) ────────────────────────────────

interface AccessRestaurant {
  id: number
  name: string
  code: string
  feat_invoices: boolean
  feat_analytics: boolean
}

function AccessTab() {
  const [restaurants, setRestaurants] = useState<AccessRestaurant[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState<number | null>(null)

  useEffect(() => {
    api.get("/admin/restaurants")
      .then(r => setRestaurants(r.data.map((x: any) => ({
        id: x.id, name: x.name, code: x.code,
        feat_invoices:  x.feat_invoices  !== false,
        feat_analytics: x.feat_analytics !== false,
      }))))
      .finally(() => setLoading(false))
  }, [])

  const toggle = async (id: number, field: "feat_invoices" | "feat_analytics") => {
    const rest = restaurants.find(r => r.id === id)
    if (!rest) return
    const newVal = !rest[field]
    setSaving(id)
    try {
      await api.patch(`/admin/restaurants/${id}/features`, { [field]: newVal })
      setRestaurants(prev => prev.map(r => r.id === id ? { ...r, [field]: newVal } : r))
    } catch {
      // откатываем
    } finally {
      setSaving(null)
    }
  }

  const FEATURES: { key: "feat_invoices" | "feat_analytics"; label: string; icon: React.ReactNode; desc: string }[] = [
    { key: "feat_invoices",  label: "Накладные",  icon: <FileInput size={15} />,  desc: "Раздел приёма накладных ABL" },
    { key: "feat_analytics", label: "Аналитика",  icon: <TrendingUp size={15} />, desc: "Раздел аналитики и трендов" },
  ]

  if (loading) return <div className="flex justify-center py-20"><Loader2 size={22} className="animate-spin text-brand-muted" /></div>

  return (
    <div className="space-y-6">
      <div className="card p-5">
        <div className="flex items-center gap-3 mb-1">
          <ShieldCheck size={18} className="text-brand-yellow" />
          <h2 className="font-semibold text-brand-dark">Доступ к разделам</h2>
        </div>
        <p className="text-xs text-brand-muted mb-5">
          Управляйте какие разделы видят пользователи каждого ресторана (role = store).
          CO и администраторы видят всё всегда.
        </p>

        {/* Шапка фич */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-brand-border">
                <th className="text-left py-2.5 px-4 text-brand-muted font-medium text-xs uppercase tracking-wide">Ресторан</th>
                {FEATURES.map(f => (
                  <th key={f.key} className="text-center py-2.5 px-6 text-brand-muted font-medium text-xs uppercase tracking-wide whitespace-nowrap">
                    <div className="flex flex-col items-center gap-0.5">
                      <span className="flex items-center gap-1">{f.icon} {f.label}</span>
                      <span className="text-brand-muted/60 font-normal normal-case">{f.desc}</span>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {restaurants.map(r => (
                <tr key={r.id} className="border-b border-brand-border/50 hover:bg-brand-bg/60 transition-colors">
                  <td className="py-3 px-4">
                    <p className="font-medium text-brand-dark">{r.name}</p>
                    <p className="text-xs text-brand-muted font-mono">{r.code}</p>
                  </td>
                  {FEATURES.map(f => {
                    const enabled = r[f.key]
                    return (
                      <td key={f.key} className="py-3 px-6 text-center">
                        <button
                          onClick={() => toggle(r.id, f.key)}
                          disabled={saving === r.id}
                          title={enabled ? "Отключить" : "Включить"}
                          className="inline-flex items-center gap-2 transition-colors"
                        >
                          {saving === r.id
                            ? <Loader2 size={20} className="animate-spin text-brand-muted" />
                            : enabled
                              ? <ToggleRight size={28} className="text-green-500" />
                              : <ToggleLeft size={28} className="text-brand-border" />
                          }
                          <span className={cn("text-xs font-medium", enabled ? "text-green-600" : "text-brand-muted")}>
                            {enabled ? "Вкл" : "Выкл"}
                          </span>
                        </button>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

type TabId = "restaurants" | "users" | "groups" | "accounts" | "catalog" | "presets" | "iiko" | "abl" | "recipes" | "access"

export default function AdminPage() {
  const [tab, setTab] = useState<TabId>("restaurants")
  const [restaurants, setRestaurants] = useState<Restaurant[]>([])

  useEffect(() => {
    api.get("/admin/restaurants").then((r) => setRestaurants(r.data))
  }, [])

  const tabs: { id: TabId; label: string; icon: React.ReactNode }[] = [
    { id: "restaurants", label: "Рестораны",    icon: <Store size={15} /> },
    { id: "users",       label: "Пользователи", icon: <Users size={15} /> },
    { id: "groups",      label: "Группы",        icon: <Tag size={15} /> },
    { id: "accounts",    label: "Счета",         icon: <CreditCard size={15} /> },
    { id: "catalog",     label: "Каталог",       icon: <BookOpen size={15} /> },
    { id: "presets",     label: "Пресеты",       icon: <Layers size={15} /> },
    { id: "iiko",        label: "IIKO Sync",        icon: <RefreshCw size={15} /> },
    { id: "abl",         label: "ABL Маппинг",      icon: <Upload size={15} /> },
    { id: "recipes",     label: "Тех. карты",        icon: <ChefHat size={15} /> },
  ]

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-brand-dark flex items-center gap-2">
          <Settings size={22} className="text-brand-yellow" /> Администрирование
        </h1>
        <p className="text-brand-muted text-sm mt-1">Управление пользователями, ресторанами и справочниками</p>
      </div>

      <div className="flex gap-1 mb-6 bg-white border border-brand-border rounded-xl p-1 w-fit flex-wrap">
        {tabs.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all",
              tab === t.id ? "bg-brand-yellow text-brand-dark shadow-sm" : "text-brand-muted hover:text-brand-dark"
            )}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      <div>
        {tab === "restaurants" && <RestaurantsTab />}
        {tab === "users"       && <UsersTab restaurants={restaurants} />}
        {tab === "groups"      && <GroupsTab />}
        {tab === "accounts"    && <AccountsTab />}
        {tab === "catalog"     && <CatalogTab />}
        {tab === "presets"     && <PresetsTab />}
        {tab === "iiko"        && <IikoSyncTab />}
        {tab === "abl"         && <AblMappingTab />}
        {tab === "recipes"     && <RecipesTab />}
      </div>
    </div>
  )
}
