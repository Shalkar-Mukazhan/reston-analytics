import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import coApi from '../../api/coClient'
import CoLayout from './CoLayout'
import {
  RefreshCw, Plus, Edit2, Trash2, Save, X, Search,
  Loader2, CheckCircle2, AlertCircle, Warehouse, Package,
  Truck, Users, Store, ChevronDown, ChevronUp, ArrowLeftRight, Box,
} from 'lucide-react'

const errMsg = (e: any): string => {
  const d = e?.response?.data?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map((x: any) => x.msg ?? JSON.stringify(x)).join(', ')
  return e?.message ?? 'Неизвестная ошибка'
}

type Tab = 'restaurants' | 'warehouses' | 'products' | 'suppliers' | 'mapping' | 'containers' | 'users'


interface Restaurant { id: number; code: string; name: string; base_url: string; iiko_login: string; iiko_concept_id: string | null; inventory_preset_id: string | null; is_active: boolean; warehouses_count: number }
interface Warehouse { id: number; name: string; iiko_store_id: string | null; is_active: boolean; is_writeoff_default: boolean; warehouse_type_id: number | null; warehouse_type_name: string | null }
interface WarehouseType { id: number; name: string; account_name: string | null }
interface Product { id: number; iiko_article_id: string | null; name: string; unit: string | null; is_active: boolean }
interface Supplier { id: number; iiko_id: string | null; name: string; bin: string | null; contact: string | null; is_active: boolean }
interface CoUser { id: number; email: string; name: string; role: string; is_active: boolean; restaurant_ids: number[] }
interface IikoStore { iiko_store_id: string; name: string; added: boolean }
interface Mapping { id: number; supplier_id: number; supplier_name: string | null; supplier_product_name: string; supplier_product_code: string | null; product_id: number | null; product_name: string | null; product_iiko_id: string | null; container_id: number | null; container_name: string | null; container_count: number | null }
interface Container { id: number; product_id: number; product_name: string | null; iiko_container_id: string; name: string; count: number }

function Toast({ msg, ok }: { msg: string; ok: boolean }) {
  return (
    <div className={`fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-3 rounded-xl text-sm font-medium shadow-lg border ${ok ? 'bg-green-50 border-green-200 text-green-800' : 'bg-red-50 border-red-200 text-red-800'}`}>
      {ok ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
      {msg}
    </div>
  )
}

function SyncBtn({ label, onSync }: { label: string; onSync: () => Promise<string> }) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState('')
  const click = async () => {
    setLoading(true); setResult('')
    try { setResult(await onSync()) }
    catch (e) { setResult('Ошибка: ' + errMsg(e)) }
    finally { setLoading(false) }
  }
  return (
    <div className="flex items-center gap-2">
      <button
        onClick={click}
        disabled={loading}
        className="flex items-center gap-1.5 px-3 py-1.5 bg-brand-yellow/20 hover:bg-brand-yellow/30 border border-brand-yellow/40 text-brand-dark text-xs rounded-lg transition-colors disabled:opacity-50 font-medium"
      >
        {loading ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
        {label}
      </button>
      {result && <span className="text-xs text-brand-muted">{result}</span>}
    </div>
  )
}

export default function CoAdminPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [me, setMe] = useState<{ name: string; role: string } | null>(null)
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null)

  const showToast = (msg: string, ok = true) => {
    setToast({ msg, ok })
    setTimeout(() => setToast(null), 3500)
  }

  useEffect(() => {
    coApi.get('/auth/me').then(r => {
      setMe(r.data)
      if (!searchParams.get('tab')) {
        navigate(`/co/admin?tab=${r.data.role === 'admin' ? 'restaurants' : 'mapping'}`, { replace: true })
      }
    }).catch(() => navigate('/co/login'))
  }, [])

  const logout = () => {
    localStorage.removeItem('co_access_token')
    localStorage.removeItem('co_refresh_token')
    navigate('/login')
  }

  const isAdmin = me?.role === 'admin'
  const tab = (searchParams.get('tab') as Tab) || 'mapping'

  return (
    <CoLayout me={me} onLogout={logout}>
      <div className="p-4 sm:p-6">
        {tab === 'restaurants' && <RestaurantsTab showToast={showToast} isAdmin={isAdmin} />}
        {tab === 'warehouses' && <WarehousesTab showToast={showToast} />}
        {tab === 'products' && <ProductsTab showToast={showToast} />}
        {tab === 'suppliers' && <SuppliersTab showToast={showToast} isAdmin={isAdmin} />}
        {tab === 'mapping' && <MappingTab showToast={showToast} />}
        {tab === 'containers' && <ContainersTab showToast={showToast} />}
        {tab === 'users' && <UsersTab showToast={showToast} />}
      </div>
      {toast && <Toast msg={toast.msg} ok={toast.ok} />}
    </CoLayout>
  )
}

// ── RESTAURANTS ───────────────────────────────────────────────────────────────

function RestaurantsTab({ showToast, isAdmin }: { showToast: (m: string, ok?: boolean) => void; isAdmin: boolean }) {
  const [list, setList] = useState<Restaurant[]>([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState<Partial<Restaurant & { iiko_password: string }> | null>(null)
  const [editId, setEditId] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  const [syncConcepts, setSyncConcepts] = useState<{ rid: number; concepts: { id: string; name: string; type: string }[] } | null>(null)
  const [quickForm, setQuickForm] = useState<{ code: string; name: string; base_url: string } | null>(null)
  const [savingQuick, setSavingQuick] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try { setList((await coApi.get('/admin/restaurants')).data) }
    catch (e) { showToast(errMsg(e), false) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const save = async () => {
    if (!form?.name || !form?.code || !form?.base_url) return
    setSaving(true)
    try {
      editId ? await coApi.patch(`/admin/restaurants/${editId}`, form) : await coApi.post('/admin/restaurants', form)
      showToast(editId ? 'Обновлено' : 'Создан'); setForm(null); setEditId(null); load()
    } catch (e) { showToast(errMsg(e), false) }
    finally { setSaving(false) }
  }

  const del = async (id: number) => {
    if (!confirm('Удалить ресторан?')) return
    try { await coApi.delete(`/admin/restaurants/${id}`); showToast('Удалено'); load() }
    catch (e) { showToast(errMsg(e), false) }
  }

  const saveQuick = async () => {
    if (!quickForm?.code || !quickForm?.name || !quickForm?.base_url) return
    setSavingQuick(true)
    try {
      await coApi.post('/admin/restaurants/quick', quickForm)
      showToast('Ресторан добавлен'); setQuickForm(null); load()
    } catch (e) { showToast(errMsg(e), false) }
    finally { setSavingQuick(false) }
  }

  // ── Упрощённый вид для non-admin ──
  if (!isAdmin) {
    return (
      <div className="space-y-4 max-w-3xl">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-brand-dark">Рестораны</h2>
          {!quickForm && (
            <button onClick={() => setQuickForm({ code: '', name: '', base_url: '' })} className="btn-primary">
              <Plus size={14} /> Добавить
            </button>
          )}
        </div>
        {quickForm && (
          <div className="card p-4 space-y-3 border border-brand-yellow/30">
            <p className="text-xs text-brand-muted">Логин и пароль iiko скопируются автоматически из существующего ресторана</p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[{ key: 'code', label: 'Код', ph: 'MAXIMA' }, { key: 'name', label: 'Название', ph: 'Maxima Coffee' }, { key: 'base_url', label: 'iiko URL', ph: 'iiko-server:8080 (https автоматически)' }].map(f => (
                <div key={f.key}>
                  <label className="block text-xs font-medium text-brand-muted mb-1">{f.label}</label>
                  <input value={(quickForm as any)[f.key]} onChange={e => setQuickForm(p => p ? { ...p, [f.key]: f.key === 'code' ? e.target.value.toUpperCase() : e.target.value } : null)} placeholder={f.ph} className="input" />
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <button onClick={saveQuick} disabled={savingQuick || !quickForm.code || !quickForm.name || !quickForm.base_url} className="btn-primary">
                {savingQuick ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Сохранить
              </button>
              <button onClick={() => setQuickForm(null)} className="btn-secondary"><X size={14} /> Отмена</button>
            </div>
          </div>
        )}
        {loading ? (
          <div className="flex items-center gap-2 text-brand-muted"><Loader2 size={16} className="animate-spin" /> Загрузка...</div>
        ) : list.length === 0 ? (
          <div className="card p-8 text-center text-brand-muted">Нет ресторанов</div>
        ) : (
          <div className="card overflow-hidden">
            {/* Mobile cards */}
            <div className="sm:hidden divide-y divide-brand-border">
              {list.map(r => (
                <div key={r.id} className="px-4 py-3">
                  <div className="font-medium text-brand-dark">{r.name} <span className="text-brand-muted font-mono text-xs">{r.code}</span></div>
                  <div className="text-xs text-brand-muted mt-0.5">{r.base_url} · {r.warehouses_count} складов</div>
                </div>
              ))}
            </div>
            {/* Desktop table */}
            <div className="hidden sm:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-brand-bg">
                  <tr className="border-b border-brand-border text-brand-muted text-xs">
                    <th className="text-left px-4 py-2.5 font-medium">Код</th>
                    <th className="text-left px-4 py-2.5 font-medium">Название</th>
                    <th className="text-left px-4 py-2.5 font-medium">iiko URL</th>
                    <th className="text-left px-4 py-2.5 font-medium">Складов</th>
                  </tr>
                </thead>
                <tbody>
                  {list.map(r => (
                    <tr key={r.id} className="border-b border-brand-border hover:bg-brand-bg">
                      <td className="px-4 py-2.5 font-mono text-xs text-brand-muted">{r.code}</td>
                      <td className="px-4 py-2.5 font-medium text-brand-dark">{r.name}</td>
                      <td className="px-4 py-2.5 text-xs text-brand-muted">{r.base_url}</td>
                      <td className="px-4 py-2.5 text-brand-muted text-xs">{r.warehouses_count}</td>
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

  return (
    <div className="space-y-4 max-w-4xl">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-brand-dark">Рестораны</h2>
        <button onClick={() => { setForm({ code: '', name: '', base_url: '', iiko_login: '', iiko_password: '' }); setEditId(null) }} className="btn-primary">
          <Plus size={14} /> Добавить
        </button>
      </div>

      {form && (
        <div className="card p-5 space-y-4">
          <h3 className="text-sm font-semibold text-brand-dark">{editId ? 'Редактировать ресторан' : 'Новый ресторан'}</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[
              { key: 'code', label: 'Код', ph: 'MAXIMA' },
              { key: 'name', label: 'Название', ph: 'Maxima Coffee' },
              { key: 'base_url', label: 'iiko URL', ph: 'http://iiko-server:8080' },
              { key: 'iiko_login', label: 'Логин iiko', ph: 'admin' },
            ].map(f => (
              <div key={f.key}>
                <label className="block text-xs font-medium text-brand-muted mb-1">{f.label}</label>
                <input value={(form as any)[f.key] ?? ''} onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))} placeholder={f.ph} className="input" />
              </div>
            ))}
            <div>
              <label className="block text-xs font-medium text-brand-muted mb-1">Пароль iiko</label>
              <input type="password" value={form.iiko_password ?? ''} onChange={e => setForm(p => ({ ...p, iiko_password: e.target.value }))} className="input" />
            </div>
            <div className="sm:col-span-2">
              <details className="group">
                <summary className="text-xs text-brand-muted cursor-pointer hover:text-brand-dark select-none">Дополнительные настройки iiko</summary>
                <div className="mt-2 space-y-3">
                  <div>
                    <label className="block text-xs font-medium text-brand-muted mb-1">UUID концепции (фильтр складов)</label>
                    <input
                      value={(form as any).iiko_concept_id ?? ''}
                      onChange={e => setForm(p => ({ ...p, iiko_concept_id: e.target.value }))}
                      placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                      className="input font-mono text-xs"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-brand-muted mb-1">UUID пресета инвентаризации (для акта списания)</label>
                    <input
                      value={(form as any).inventory_preset_id ?? ''}
                      onChange={e => setForm(p => ({ ...p, inventory_preset_id: e.target.value }))}
                      placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                      className="input font-mono text-xs"
                    />
                  </div>
                </div>
              </details>
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={save} disabled={saving} className="btn-primary">
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Сохранить
            </button>
            <button onClick={() => { setForm(null); setEditId(null) }} className="btn-secondary">
              <X size={14} /> Отмена
            </button>
          </div>
        </div>
      )}

      {syncConcepts && (
        <div className="card p-4 border-brand-yellow border bg-brand-yellow/5">
          <div className="flex items-start justify-between mb-2">
            <div>
              <p className="text-sm font-semibold text-brand-dark">Концепции из iiko</p>
              <p className="text-xs text-brand-muted mt-0.5">Скопируйте UUID нужной концепции в поле ресторана, затем повторите синхронизацию — получите только её склады</p>
            </div>
            <button onClick={() => setSyncConcepts(null)} className="p-1 hover:bg-brand-bg rounded text-brand-muted"><X size={14} /></button>
          </div>
          <div className="space-y-1 mt-2">
            {syncConcepts.concepts.map(c => (
              <div key={c.id} className="flex items-center justify-between bg-white rounded px-3 py-1.5 border border-brand-border">
                <div>
                  <span className="text-sm text-brand-dark">{c.name}</span>
                  <span className="text-xs text-brand-muted ml-2">{c.type}</span>
                </div>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(c.id)
                    showToast(`UUID скопирован: ${c.name}`)
                  }}
                  className="text-xs font-mono text-brand-muted hover:text-brand-dark border border-brand-border rounded px-2 py-0.5 hover:bg-brand-bg transition-colors"
                >
                  {c.id.slice(0, 18)}… 📋
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-brand-muted"><Loader2 size={16} className="animate-spin" /> Загрузка...</div>
      ) : list.length === 0 ? (
        <div className="card p-8 text-center text-brand-muted text-sm">Нет ресторанов. Добавьте первый.</div>
      ) : (
        <div className="space-y-3">
          {list.map(r => (
            <div key={r.id} className="card p-4">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <div className="font-semibold text-brand-dark">{r.name} <span className="text-brand-muted font-normal text-sm">#{r.code}</span></div>
                  <div className="text-xs text-brand-muted mt-0.5">{r.base_url} · логин: {r.iiko_login}</div>
                  <div className="text-xs text-brand-muted">
                    {r.warehouses_count} складов
                    {r.iiko_concept_id && <span className="ml-2 text-green-600">· концепция: {r.iiko_concept_id.slice(0, 8)}…</span>}
                  </div>
                </div>
                <div className="flex gap-1">
                  <button onClick={() => { setForm({ ...r, iiko_password: '' }); setEditId(r.id) }} className="p-1.5 hover:bg-brand-bg rounded-lg text-brand-muted hover:text-brand-dark transition-colors"><Edit2 size={14} /></button>
                  <button onClick={() => del(r.id)} className="p-1.5 hover:bg-red-50 rounded-lg text-brand-muted hover:text-red-600 transition-colors"><Trash2 size={14} /></button>
                </div>
              </div>
              <div className="flex flex-wrap gap-2 pt-3 border-t border-brand-border">
                <SyncBtn label="Обновить склады" onSync={async () => {
                  const { data } = await coApi.post(`/admin/restaurants/${r.id}/sync/warehouses`)
                  if (data.concepts?.length > 0 && !data.filtered_by_concept) {
                    setSyncConcepts({ rid: r.id, concepts: data.concepts })
                  }
                  const suffix = data.filtered_by_concept ? ` (концепция)` : ` (все)`
                  return `найдено ${data.found}${suffix}, обновлено ${data.updated ?? 0}`
                }} />
                <SyncBtn label="Синхр. товары" onSync={async () => {
                  const { data } = await coApi.post(`/admin/restaurants/${r.id}/sync/products`)
                  return `добавлено ${data.added}, обновлено ${data.updated}`
                }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── WAREHOUSES ────────────────────────────────────────────────────────────────

function WarehousesTab({ showToast }: { showToast: (m: string, ok?: boolean) => void }) {
  const [restaurants, setRestaurants] = useState<Restaurant[]>([])
  const [warehouses, setWarehouses] = useState<Record<number, Warehouse[]>>({})
  const [warehouseTypes, setWarehouseTypes] = useState<WarehouseType[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  const [showAddPanel, setShowAddPanel] = useState<number | null>(null)
  const [iikoStores, setIikoStores] = useState<IikoStore[]>([])
  const [iikoLoading, setIikoLoading] = useState(false)
  const [iikoSearch, setIikoSearch] = useState('')
  const [adding, setAdding] = useState<string | null>(null)
  const [addingAll, setAddingAll] = useState<number | null>(null)
  const [updating, setUpdating] = useState<number | null>(null)

  const [clearing, setClearing] = useState<number | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [restsRes, typesRes] = await Promise.all([
        coApi.get('/admin/restaurants'),
        coApi.get('/writeoffs/settings/warehouse-types'),
      ])
      const rests: Restaurant[] = restsRes.data
      setRestaurants(rests)
      setWarehouseTypes(typesRes.data)
      const all: Record<number, Warehouse[]> = {}
      await Promise.all(rests.map(async r => { all[r.id] = (await coApi.get(`/admin/restaurants/${r.id}/warehouses`)).data }))
      setWarehouses(all)
      setExpanded(new Set())
    } catch (e) { showToast(errMsg(e), false) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const reloadWarehouses = async (rid: number) => {
    const { data } = await coApi.get(`/admin/restaurants/${rid}/warehouses`)
    setWarehouses(prev => ({ ...prev, [rid]: data }))
  }

  const toggleActive = async (wid: number, rid: number, current: boolean) => {
    try {
      const { data } = await coApi.patch(`/admin/warehouses/${wid}`, { is_active: !current })
      setWarehouses(prev => ({ ...prev, [rid]: (prev[rid] ?? []).map(w => w.id === wid ? { ...w, is_active: data.is_active } : w) }))
      showToast(data.is_active ? 'Склад активирован' : 'Склад деактивирован')
    } catch (e) { showToast(errMsg(e), false) }
  }

  const openIikoPanel = async (rid: number) => {
    setShowAddPanel(rid); setIikoSearch(''); setIikoStores([]); setIikoLoading(true)
    try {
      const { data } = await coApi.get(`/admin/restaurants/${rid}/iiko/warehouses`)
      setIikoStores(data)
    } catch (e) { showToast('Не удалось загрузить из iiko: ' + errMsg(e), false) }
    finally { setIikoLoading(false) }
  }

  const addFromIiko = async (rid: number, store: IikoStore) => {
    setAdding(store.iiko_store_id)
    try {
      await coApi.post(`/admin/restaurants/${rid}/warehouses`, { name: store.name, iiko_store_id: store.iiko_store_id })
      showToast(`Добавлен: ${store.name}`)
      setIikoStores(prev => prev.map(s => s.iiko_store_id === store.iiko_store_id ? { ...s, added: true } : s))
      await reloadWarehouses(rid)
    } catch (e) { showToast(errMsg(e), false) }
    finally { setAdding(null) }
  }

  const updateNames = async (rid: number) => {
    setUpdating(rid)
    try {
      const { data } = await coApi.post(`/admin/restaurants/${rid}/sync/warehouses`)
      showToast(`Обновлено имён: ${data.updated ?? 0}`)
      await reloadWarehouses(rid)
    } catch (e) { showToast(errMsg(e), false) }
    finally { setUpdating(null) }
  }

  const addAllFromIiko = async (rid: number) => {
    setAddingAll(rid)
    try {
      const { data: stores } = await coApi.get(`/admin/restaurants/${rid}/iiko/warehouses`)
      const toAdd = (stores as IikoStore[]).filter(s => !s.added)
      if (toAdd.length === 0) { showToast('Все склады уже добавлены'); return }
      await Promise.all(toAdd.map(s => coApi.post(`/admin/restaurants/${rid}/warehouses`, { name: s.name, iiko_store_id: s.iiko_store_id })))
      showToast(`Добавлено ${toAdd.length} складов`)
      await reloadWarehouses(rid)
    } catch (e) { showToast(errMsg(e), false) }
    finally { setAddingAll(null) }
  }

  const clearAll = async (rid: number, rname: string) => {
    const count = (warehouses[rid] ?? []).length
    if (!confirm(`Удалить все ${count} складов ресторана "${rname}"?\nСклады с накладными останутся.`)) return
    setClearing(rid)
    try {
      const { data } = await coApi.delete(`/admin/restaurants/${rid}/warehouses`)
      showToast(`Удалено ${data.deleted}${data.skipped ? `, пропущено ${data.skipped} (накладные)` : ''}`)
      await reloadWarehouses(rid)
    } catch (e) { showToast(errMsg(e), false) }
    finally { setClearing(null) }
  }

  const setWarehouseType = async (wid: number, rid: number, typeId: number | null) => {
    try {
      const { data } = await coApi.patch(`/writeoffs/settings/warehouses/${wid}/type`, { warehouse_type_id: typeId })
      setWarehouses(prev => ({
        ...prev,
        [rid]: (prev[rid] ?? []).map(w => w.id === wid
          ? { ...w, warehouse_type_id: data.warehouse_type_id, warehouse_type_name: data.warehouse_type_name }
          : w),
      }))
    } catch (e) { showToast(errMsg(e), false) }
  }

  const toggle = (id: number) => setExpanded(p => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n })

  const filteredStores = iikoStores.filter(s => !iikoSearch || s.name.toLowerCase().includes(iikoSearch.toLowerCase()))

  if (loading) return <div className="flex items-center gap-2 text-brand-muted"><Loader2 size={16} className="animate-spin" /> Загрузка...</div>

  return (
    <div className="space-y-3 max-w-3xl">
      <h2 className="text-lg font-bold text-brand-dark">Склады</h2>
      {restaurants.map(r => (
        <div key={r.id} className="card overflow-hidden">
          {/* Заголовок ресторана */}
          <div className="flex items-start sm:items-center px-4 py-3 gap-2 flex-col sm:flex-row">
            <button onClick={() => toggle(r.id)} className="flex items-center gap-2 w-full sm:flex-1 text-left min-w-0">
              <span className="font-semibold text-brand-dark truncate">{r.name}</span>
              <span className="text-xs bg-brand-bg border border-brand-border rounded-full px-2 py-0.5 text-brand-muted shrink-0">{(warehouses[r.id] ?? []).length}</span>
              {expanded.has(r.id) ? <ChevronUp size={14} className="text-brand-muted shrink-0" /> : <ChevronDown size={14} className="text-brand-muted shrink-0" />}
            </button>
            <div className="flex items-center gap-1.5 flex-wrap">
              <button
                onClick={() => openIikoPanel(r.id)}
                className="flex items-center gap-1 text-xs bg-brand-yellow/20 hover:bg-brand-yellow/30 border border-brand-yellow/40 text-brand-dark px-2.5 py-1 rounded-lg font-medium transition-colors"
              >
                <Plus size={11} /> Из iiko
              </button>
              <button
                onClick={() => addAllFromIiko(r.id)}
                disabled={addingAll === r.id}
                className="flex items-center gap-1 text-xs bg-green-50 hover:bg-green-100 border border-green-300 text-green-700 px-2.5 py-1 rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                {addingAll === r.id ? <Loader2 size={11} className="animate-spin" /> : <Plus size={11} />}
                Добавить все
              </button>
              <button
                onClick={() => updateNames(r.id)}
                disabled={updating === r.id}
                title="Обновить имена из iiko"
                className="flex items-center gap-1 text-xs text-brand-muted hover:text-brand-dark hover:bg-brand-bg border border-brand-border px-2.5 py-1 rounded-lg transition-colors disabled:opacity-50"
              >
                {updating === r.id ? <Loader2 size={11} className="animate-spin" /> : <RefreshCw size={11} />}
                Обновить
              </button>
              <button
                onClick={() => clearAll(r.id, r.name)}
                disabled={clearing === r.id}
                className="flex items-center gap-1 text-xs text-red-500 hover:text-red-700 hover:bg-red-50 border border-red-200 px-2.5 py-1 rounded-lg transition-colors disabled:opacity-50"
              >
                {clearing === r.id ? <Loader2 size={11} className="animate-spin" /> : <Trash2 size={11} />}
                Очистить все
              </button>
            </div>
          </div>

          {expanded.has(r.id) && (
            <div className="border-t border-brand-border">
              {/* Список складов */}
              <div className="px-4 pt-3 pb-1 space-y-1">
                {(warehouses[r.id] ?? []).map(w => (
                  <div key={w.id} className={`flex items-center gap-2 rounded-lg px-3 py-2 ${w.is_active ? 'bg-brand-bg' : 'bg-red-50/60'}`}>
                    <span className={`text-sm truncate flex-1 min-w-0 ${w.is_active ? 'text-brand-dark' : 'text-brand-muted line-through'}`}>{w.name}</span>
                    {!w.is_active && <span className="text-xs text-red-500 bg-red-50 border border-red-200 rounded px-1 shrink-0">скрыт</span>}
                    {/* Тип склада */}
                    <select
                      value={w.warehouse_type_id ?? ''}
                      onChange={e => setWarehouseType(w.id, r.id, e.target.value ? parseInt(e.target.value) : null)}
                      className="text-xs border border-brand-border rounded-lg px-2 py-1 bg-white text-brand-dark shrink-0 max-w-[120px]"
                    >
                      <option value="">— тип —</option>
                      {warehouseTypes.map(t => (
                        <option key={t.id} value={t.id}>{t.name}</option>
                      ))}
                    </select>
                    <div className="flex gap-1 shrink-0">
                      <button
                        onClick={() => toggleActive(w.id, r.id, w.is_active)}
                        title={w.is_active ? 'Скрыть' : 'Показать'}
                        className={`p-1.5 rounded text-xs transition-colors ${w.is_active ? 'text-green-600 hover:bg-green-50' : 'text-brand-muted hover:bg-brand-bg'}`}
                      >
                        {w.is_active ? '✓' : '○'}
                      </button>
                      <button onClick={async () => { if (!confirm('Удалить?')) return; await coApi.delete(`/admin/warehouses/${w.id}`); showToast('Удалено'); reloadWarehouses(r.id) }} className="p-1 hover:bg-red-50 rounded text-brand-muted hover:text-red-600 transition-colors">
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                ))}
                {(warehouses[r.id] ?? []).length === 0 && (
                  <p className="text-xs text-brand-muted py-1 italic">Нет складов</p>
                )}
              </div>

              {/* Панель поиска iiko складов */}
              {showAddPanel === r.id && (
                <div className="px-4 pb-4">
                  <div className="border border-brand-border rounded-xl p-3 space-y-2 bg-brand-bg/50">
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-semibold text-brand-dark">Склады из iiko</p>
                      <button onClick={() => { setShowAddPanel(null); setIikoSearch('') }} className="p-0.5 rounded text-brand-muted hover:text-brand-dark"><X size={14} /></button>
                    </div>
                    <input value={iikoSearch} onChange={e => setIikoSearch(e.target.value)} placeholder="Поиск по названию..." className="input" autoFocus />
                    {iikoLoading ? (
                      <div className="flex items-center gap-2 py-3 text-brand-muted text-xs justify-center">
                        <Loader2 size={13} className="animate-spin" /> Загрузка из iiko...
                      </div>
                    ) : (
                      <div className="max-h-60 overflow-y-auto space-y-0.5">
                        {filteredStores.length === 0 && <p className="text-xs text-brand-muted py-3 text-center">{iikoSearch ? 'Ничего не найдено' : 'Нет доступных складов'}</p>}
                        {filteredStores.map(s => (
                          <div key={s.iiko_store_id} className={`flex items-center justify-between px-3 py-2 rounded-lg transition-colors ${s.added ? 'opacity-40' : 'hover:bg-white'}`}>
                            <span className="text-sm text-brand-dark">{s.name}</span>
                            {s.added ? (
                              <span className="text-xs text-green-600 font-medium">✓ добавлен</span>
                            ) : (
                              <button onClick={() => addFromIiko(r.id, s)} disabled={adding === s.iiko_store_id} className="flex items-center gap-1 text-xs bg-brand-yellow/20 hover:bg-brand-yellow/30 border border-brand-yellow/40 text-brand-dark px-2.5 py-1 rounded-lg font-medium transition-colors disabled:opacity-50">
                                {adding === s.iiko_store_id ? <Loader2 size={11} className="animate-spin" /> : <Plus size={11} />} Добавить
                              </button>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

// ── PRODUCTS ──────────────────────────────────────────────────────────────────

function ProductsTab({ showToast }: { showToast: (m: string, ok?: boolean) => void }) {
  const [list, setList] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  const load = useCallback(async (q = '') => {
    setLoading(true)
    try { setList((await coApi.get('/admin/products', { params: q ? { search: q } : {} })).data) }
    catch (e) { showToast(errMsg(e), false) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])
  useEffect(() => { const t = setTimeout(() => load(search), 400); return () => clearTimeout(t) }, [search])

  return (
    <div className="space-y-4 max-w-4xl">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-brand-dark">Товары <span className="text-brand-muted font-normal text-sm">({list.length})</span></h2>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Поиск..." className="input w-64" />
      </div>
      <p className="text-xs text-brand-muted">Загрузите товары через кнопку <strong>"Синхр. товары"</strong> во вкладке Рестораны.</p>
      {loading ? (
        <div className="flex items-center gap-2 text-brand-muted"><Loader2 size={16} className="animate-spin" /> Загрузка...</div>
      ) : list.length === 0 ? (
        <div className="card p-8 text-center text-brand-muted text-sm">Нет товаров</div>
      ) : (
        <div className="card overflow-hidden">
          {/* Mobile list */}
          <div className="sm:hidden divide-y divide-brand-border">
            {list.map(p => (
              <div key={p.id} className="px-4 py-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-brand-dark truncate">{p.name}</span>
                  <span className={`badge-${p.is_active ? 'ok' : 'over'} text-xs shrink-0`}>{p.is_active ? 'активен' : 'неактивен'}</span>
                </div>
                {p.unit && <div className="text-xs text-brand-muted mt-0.5">{p.unit}</div>}
              </div>
            ))}
          </div>
          {/* Desktop table */}
          <div className="hidden sm:block overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-brand-bg">
                <tr className="border-b border-brand-border text-brand-muted text-xs">
                  <th className="text-left px-4 py-2 font-medium">Название</th>
                  <th className="text-left px-4 py-2 font-medium">Ед. изм.</th>
                  <th className="text-left px-4 py-2 font-medium">iiko ID</th>
                  <th className="text-left px-4 py-2 font-medium">Статус</th>
                </tr>
              </thead>
              <tbody>
                {list.map(p => (
                  <tr key={p.id} className="border-b border-brand-border hover:bg-brand-bg">
                    <td className="px-4 py-2 text-brand-dark">{p.name}</td>
                    <td className="px-4 py-2 text-brand-muted">{p.unit ?? '—'}</td>
                    <td className="px-4 py-2 text-brand-muted text-xs font-mono">{p.iiko_article_id ? p.iiko_article_id.slice(0, 14) + '...' : '—'}</td>
                    <td className="px-4 py-2"><span className={`badge-${p.is_active ? 'ok' : 'over'}`}>{p.is_active ? 'активен' : 'неактивен'}</span></td>
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

// ── SUPPLIERS ─────────────────────────────────────────────────────────────────

function SuppliersTab({ showToast, isAdmin }: { showToast: (m: string, ok?: boolean) => void; isAdmin: boolean }) {
  const [list, setList] = useState<Supplier[]>([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState<Partial<Supplier> | null>(null)
  const [editId, setEditId] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  const [query, setQuery] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try { setList((await coApi.get('/admin/suppliers')).data) }
    catch (e) { showToast(errMsg(e), false) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const save = async () => {
    if (!form?.name) return
    setSaving(true)
    try {
      editId ? await coApi.patch(`/admin/suppliers/${editId}`, form) : await coApi.post('/admin/suppliers', form)
      showToast(editId ? 'Обновлено' : 'Создан'); setForm(null); setEditId(null); load()
    } catch (e) { showToast(errMsg(e), false) }
    finally { setSaving(false) }
  }

  const q = query.toLowerCase().trim()
  const visible = list.filter(s => s.bin).filter(s =>
    !q || s.name.toLowerCase().includes(q) || (s.bin ?? '').includes(q)
  )

  return (
    <div className="space-y-4 max-w-3xl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-bold text-brand-dark">Поставщики</h2>
        <div className="flex items-center gap-2 flex-wrap">
          <SyncBtn label="Синхронизировать из iiko" onSync={async () => {
            const { data } = await coApi.post('/admin/restaurants/2/sync/suppliers')
            await load()
            const parts = [`Найдено: ${data.found}`, `обновлено: ${data.updated}`]
            if (data.added)  parts.push(`добавлено: ${data.added}`)
            if (data.linked) parts.push(`привязано: ${data.linked}`)
            return parts.join(', ')
          }} />
          {isAdmin && (
            <button onClick={() => { setForm({ name: '', bin: '', contact: '' }); setEditId(null) }} className="btn-primary">
              <Plus size={14} /> Добавить
            </button>
          )}
        </div>
      </div>

      {/* Поиск */}
      <div className="relative">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-brand-muted pointer-events-none" />
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Поиск по названию или БИН..."
          className="input pl-8 w-full"
        />
        {query && (
          <button onClick={() => setQuery('')} className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 text-brand-muted hover:text-brand-dark">
            <X size={13} />
          </button>
        )}
      </div>

      {isAdmin && form && (
        <div className="card p-4 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {[{ key: 'name', label: 'Название', ph: 'ТОО Поставщик' }, { key: 'bin', label: 'БИН', ph: '123456789012' }, { key: 'contact', label: 'Контакт', ph: '+7 700 000 0000' }].map(f => (
              <div key={f.key}>
                <label className="block text-xs font-medium text-brand-muted mb-1">{f.label}</label>
                <input value={(form as any)[f.key] ?? ''} onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))} placeholder={f.ph} className="input" />
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <button onClick={save} disabled={saving} className="btn-primary">{saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Сохранить</button>
            <button onClick={() => { setForm(null); setEditId(null) }} className="btn-secondary"><X size={14} /> Отмена</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-brand-muted"><Loader2 size={16} className="animate-spin" /> Загрузка...</div>
      ) : visible.length === 0 ? (
        <div className="card p-8 text-center text-brand-muted text-sm">{q ? 'Ничего не найдено' : 'Нет поставщиков'}</div>
      ) : (
        <div className="card overflow-hidden">
          {/* Mobile cards */}
          <div className="sm:hidden divide-y divide-brand-border">
            {visible.map(s => (
              <div key={s.id} className="px-4 py-3 flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-medium text-brand-dark truncate">{s.name}</div>
                  <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-0.5">
                    <span className="text-xs text-brand-muted font-mono">{s.bin}</span>
                    {s.contact && <span className="text-xs text-brand-muted">{s.contact}</span>}
                  </div>
                </div>
                {isAdmin && (
                  <div className="flex gap-1 shrink-0">
                    <button onClick={() => { setForm({ ...s }); setEditId(s.id) }} className="p-1.5 hover:bg-brand-bg rounded text-brand-muted hover:text-brand-dark transition-colors"><Edit2 size={14} /></button>
                    <button onClick={async () => { if (!confirm('Удалить?')) return; await coApi.delete(`/admin/suppliers/${s.id}`); showToast('Удалено'); load() }} className="p-1.5 hover:bg-red-50 rounded text-brand-muted hover:text-red-600 transition-colors"><Trash2 size={14} /></button>
                  </div>
                )}
              </div>
            ))}
          </div>
          {/* Desktop table */}
          <div className="hidden sm:block overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-brand-bg">
                <tr className="border-b border-brand-border text-brand-muted text-xs">
                  <th className="text-left px-4 py-2 font-medium">Название</th>
                  <th className="text-left px-4 py-2 font-medium">БИН</th>
                  <th className="text-left px-4 py-2 font-medium">Контакт</th>
                  {isAdmin && <th className="px-4 py-2"></th>}
                </tr>
              </thead>
              <tbody>
                {visible.map(s => (
                  <tr key={s.id} className="border-b border-brand-border hover:bg-brand-bg">
                    <td className="px-4 py-2 font-medium text-brand-dark">{s.name}</td>
                    <td className="px-4 py-2 text-brand-muted font-mono">{s.bin}</td>
                    <td className="px-4 py-2 text-brand-muted">{s.contact ?? '—'}</td>
                    {isAdmin && (
                      <td className="px-4 py-2">
                        <div className="flex gap-1 justify-end">
                          <button onClick={() => { setForm({ ...s }); setEditId(s.id) }} className="p-1 hover:bg-brand-bg rounded text-brand-muted hover:text-brand-dark transition-colors"><Edit2 size={13} /></button>
                          <button onClick={async () => { if (!confirm('Удалить?')) return; await coApi.delete(`/admin/suppliers/${s.id}`); showToast('Удалено'); load() }} className="p-1 hover:bg-red-50 rounded text-brand-muted hover:text-red-600 transition-colors"><Trash2 size={13} /></button>
                        </div>
                      </td>
                    )}
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

// ── USERS ─────────────────────────────────────────────────────────────────────

function UsersTab({ showToast }: { showToast: (m: string, ok?: boolean) => void }) {
  const [list, setList] = useState<CoUser[]>([])
  const [restaurants, setRestaurants] = useState<Restaurant[]>([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState<Partial<CoUser & { password: string }> | null>(null)
  const [editId, setEditId] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)


  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [users, rests] = await Promise.all([coApi.get('/admin/users'), coApi.get('/admin/restaurants')])
      setList(users.data); setRestaurants(rests.data)
    } catch (e) { showToast(errMsg(e), false) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const save = async () => {
    if (!form?.email || !form?.name) return
    setSaving(true)
    try {
      const payload = { ...form, restaurant_ids: form.restaurant_ids ?? [] }
      editId ? await coApi.patch(`/admin/users/${editId}`, payload) : await coApi.post('/admin/users', payload)
      showToast(editId ? 'Обновлено' : 'Создан'); setForm(null); setEditId(null); load()
    } catch (e) { showToast(errMsg(e), false) }
    finally { setSaving(false) }
  }

  const toggleRestaurant = (rid: number) => setForm(p => {
    if (!p) return p
    const ids = p.restaurant_ids ?? []
    return { ...p, restaurant_ids: ids.includes(rid) ? ids.filter(x => x !== rid) : [...ids, rid] }
  })

  return (
    <div className="space-y-4 max-w-3xl">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-brand-dark">Пользователи</h2>
        <button onClick={() => { setForm({ email: '', name: '', password: '', role: 'user', restaurant_ids: [] }); setEditId(null) }} className="btn-primary"><Plus size={14} /> Добавить</button>
      </div>

      {form && (
        <div className="card p-5 space-y-4 border border-brand-yellow/30">
          <h3 className="text-sm font-semibold text-brand-dark">{editId ? 'Редактировать пользователя' : 'Новый пользователь'}</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[{ key: 'email', label: 'Email', ph: 'user@example.com' }, { key: 'name', label: 'Имя', ph: 'Иван Иванов' }].map(f => (
              <div key={f.key}>
                <label className="block text-xs font-medium text-brand-muted mb-1">{f.label}</label>
                <input value={(form as any)[f.key] ?? ''} onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))} placeholder={f.ph} className="input" />
              </div>
            ))}
            <div>
              <label className="block text-xs font-medium text-brand-muted mb-1">Пароль {editId && <span className="font-normal">(пусто = не менять)</span>}</label>
              <input type="password" value={form.password ?? ''} onChange={e => setForm(p => ({ ...p, password: e.target.value }))} className="input" />
            </div>
            <div>
              <label className="block text-xs font-medium text-brand-muted mb-1">Роль</label>
              <select value={form.role ?? 'user'} onChange={e => setForm(p => ({ ...p, role: e.target.value }))} className="input">
                <option value="user">user</option>
                <option value="admin">admin</option>
              </select>
            </div>
          </div>

          {restaurants.length > 0 && (
            <div>
              <label className="block text-xs font-medium text-brand-muted mb-2">Доступ к ресторанам</label>
              <div className="flex flex-wrap gap-2">
                {restaurants.map(r => (
                  <button key={r.id} onClick={() => toggleRestaurant(r.id)}
                    className={`px-3 py-1 text-xs rounded-lg border transition-colors ${(form.restaurant_ids ?? []).includes(r.id) ? 'bg-brand-yellow/20 border-brand-yellow text-brand-dark font-semibold' : 'bg-white border-brand-border text-brand-muted hover:border-brand-dark'}`}>
                    {r.name}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <button onClick={save} disabled={saving} className="btn-primary">{saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Сохранить</button>
            <button onClick={() => { setForm(null); setEditId(null) }} className="btn-secondary"><X size={14} /> Отмена</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-brand-muted"><Loader2 size={16} className="animate-spin" /> Загрузка...</div>
      ) : list.length === 0 ? (
        <div className="card p-8 text-center text-brand-muted text-sm">Нет пользователей</div>
      ) : (
        <div className="card overflow-hidden">
          {/* Mobile cards */}
          <div className="sm:hidden divide-y divide-brand-border">
            {list.map(u => (
              <div key={u.id} className="px-4 py-3 flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="font-medium text-brand-dark truncate">{u.name}</span>
                    <span className={u.role === 'admin' ? 'badge-warn text-xs shrink-0' : 'badge-muted text-xs shrink-0'}>{u.role}</span>
                  </div>
                  <div className="text-xs text-brand-muted truncate">{u.email}</div>
                  {u.restaurant_ids.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {restaurants.filter(r => u.restaurant_ids.includes(r.id)).map(r => (
                        <span key={r.id} className="text-xs bg-brand-bg border border-brand-border rounded px-1.5 py-0.5 text-brand-dark">{r.name}</span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex gap-1 shrink-0">
                  <button onClick={() => { setForm({ ...u, password: '' }); setEditId(u.id) }} className="p-1.5 hover:bg-brand-bg rounded text-brand-muted hover:text-brand-dark transition-colors"><Edit2 size={14} /></button>
                  <button onClick={async () => { if (!confirm('Удалить?')) return; await coApi.delete(`/admin/users/${u.id}`); showToast('Удалено'); load() }} className="p-1.5 hover:bg-red-50 rounded text-brand-muted hover:text-red-600 transition-colors"><Trash2 size={14} /></button>
                </div>
              </div>
            ))}
          </div>
          {/* Desktop table */}
          <div className="hidden sm:block overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-brand-bg">
                <tr className="border-b border-brand-border text-brand-muted text-xs">
                  <th className="text-left px-4 py-2.5 font-medium">Имя</th>
                  <th className="text-left px-4 py-2.5 font-medium">Email</th>
                  <th className="text-left px-4 py-2.5 font-medium">Роль</th>
                  <th className="text-left px-4 py-2.5 font-medium">Рестораны</th>
                  <th className="px-4 py-2.5"></th>
                </tr>
              </thead>
              <tbody>
                {list.map(u => (
                  <tr key={u.id} className="border-b border-brand-border hover:bg-brand-bg">
                    <td className="px-4 py-2.5 font-medium text-brand-dark">{u.name}</td>
                    <td className="px-4 py-2.5 text-brand-muted text-xs">{u.email}</td>
                    <td className="px-4 py-2.5"><span className={u.role === 'admin' ? 'badge-warn' : 'badge-muted'}>{u.role}</span></td>
                    <td className="px-4 py-2.5">
                      {u.restaurant_ids.length === 0 ? (
                        <span className="text-xs text-brand-muted">—</span>
                      ) : (
                        <div className="flex flex-wrap gap-1">
                          {restaurants.filter(r => u.restaurant_ids.includes(r.id)).map(r => (
                            <span key={r.id} className="text-xs bg-brand-bg border border-brand-border rounded px-1.5 py-0.5 text-brand-dark">{r.name}</span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex gap-1 justify-end">
                        <button onClick={() => { setForm({ ...u, password: '' }); setEditId(u.id) }} className="p-1 hover:bg-brand-bg rounded text-brand-muted hover:text-brand-dark transition-colors"><Edit2 size={13} /></button>
                        <button onClick={async () => { if (!confirm('Удалить?')) return; await coApi.delete(`/admin/users/${u.id}`); showToast('Удалено'); load() }} className="p-1 hover:bg-red-50 rounded text-brand-muted hover:text-red-600 transition-colors"><Trash2 size={13} /></button>
                      </div>
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

// ── MAPPING ───────────────────────────────────────────────────────────────────

function MappingTab({ showToast }: { showToast: (m: string, ok?: boolean) => void }) {
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [mappings, setMappings] = useState<Mapping[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const [newSupplierId, setNewSupplierId] = useState<number | ''>('')
  const [newSupplierName, setNewSupplierName] = useState('')
  const [newSupplierCode, setNewSupplierCode] = useState('')
  const [newProductId, setNewProductId] = useState<number | ''>('')
  const [newProductLabel, setNewProductLabel] = useState('')
  const [newContainerId, setNewContainerId] = useState<number | ''>('')
  const [newContainers, setNewContainers] = useState<Container[]>([])
  const [productSearch, setProductSearch] = useState('')
  const [productResults, setProductResults] = useState<Product[]>([])
  const [showProductList, setShowProductList] = useState(false)

  const [supplierSearch, setSupplierSearch] = useState('')
  const [showSupplierList, setShowSupplierList] = useState(false)

  const [editId, setEditId] = useState<number | null>(null)
  const [editSupplierId, setEditSupplierId] = useState<number | ''>('')
  const [editSupplierCode, setEditSupplierCode] = useState('')
  const [editSupplierName, setEditSupplierName] = useState('')
  const [editSupplierSearch, setEditSupplierSearch] = useState('')
  const [showEditSupplierList, setShowEditSupplierList] = useState(false)
  const [editProductId, setEditProductId] = useState<number | ''>('')
  const [editContainerId, setEditContainerId] = useState<number | ''>('')
  const [editContainers, setEditContainers] = useState<Container[]>([])
  const [editSearch, setEditSearch] = useState('')
  const [editResults, setEditResults] = useState<Product[]>([])
  const [showEditList, setShowEditList] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)

  // sync cooldown
  const [syncCooldown, setSyncCooldown] = useState(0)
  const [syncing, setSyncing] = useState(false)
  const [restaurants, setRestaurants] = useState<Restaurant[]>([])

  // list search + pagination
  const [listSearch, setListSearch] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const PAGE_SIZE = 100

  const filteredMappings = listSearch.trim()
    ? mappings.filter(m => {
        const q = listSearch.toLowerCase()
        return (
          m.supplier_product_name.toLowerCase().includes(q) ||
          (m.supplier_name ?? '').toLowerCase().includes(q) ||
          (m.supplier_product_code ?? '').toLowerCase().includes(q) ||
          (m.product_name ?? '').toLowerCase().includes(q)
        )
      })
    : mappings
  const totalPages = Math.max(1, Math.ceil(filteredMappings.length / PAGE_SIZE))
  const safePage = Math.min(currentPage, totalPages)
  const paginated = filteredMappings.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)

  const searchProducts = useCallback(async (q: string, setter: (r: Product[]) => void) => {
    if (!q.trim()) { setter([]); return }
    try { setter((await coApi.get('/admin/products', { params: { search: q } })).data) }
    catch { setter([]) }
  }, [])

  useEffect(() => {
    Promise.all([
      coApi.get('/admin/suppliers'),
      coApi.get('/admin/mappings'),
      coApi.get('/admin/restaurants'),
    ]).then(([s, m, r]) => {
      setSuppliers(s.data)
      setMappings(m.data)
      setRestaurants(r.data)
    }).catch(e => showToast(errMsg(e), false))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    const t = setTimeout(() => searchProducts(productSearch, setProductResults), 300)
    return () => clearTimeout(t)
  }, [productSearch])

  useEffect(() => {
    const t = setTimeout(() => searchProducts(editSearch, setEditResults), 300)
    return () => clearTimeout(t)
  }, [editSearch])

  useEffect(() => {
    if (!newProductId) { setNewContainers([]); setNewContainerId(''); return }
    coApi.get('/admin/containers', { params: { product_id: newProductId } })
      .then(r => { setNewContainers(r.data); setNewContainerId('') })
      .catch(() => setNewContainers([]))
  }, [newProductId])

  useEffect(() => {
    if (!editProductId) { setEditContainers([]); return }
    coApi.get('/admin/containers', { params: { product_id: editProductId } })
      .then(r => setEditContainers(r.data))
      .catch(() => setEditContainers([]))
  }, [editProductId])

  const addMapping = async () => {
    if (!newSupplierName.trim() || !newSupplierId) return
    setSaving(true)
    try {
      const { data } = await coApi.post('/admin/mappings', {
        supplier_id: newSupplierId,
        supplier_product_name: newSupplierName.trim(),
        supplier_product_code: newSupplierCode.trim() || null,
        product_id: newProductId || null,
        container_id: newContainerId || null,
      })
      setMappings(p => [...p, data])
      setNewSupplierName(''); setNewSupplierCode('')
      setNewProductId(''); setNewProductLabel('')
      setNewContainerId(''); setNewContainers([])
      setProductSearch(''); setProductResults([])
      showToast('Добавлено')
    } catch (e) { showToast(errMsg(e), false) }
    finally { setSaving(false) }
  }

  const saveEdit = async (mid: number) => {
    if (!editSupplierName.trim()) return
    setSaving(true)
    try {
      const { data } = await coApi.patch(`/admin/mappings/${mid}`, {
        supplier_id: editSupplierId || null,
        supplier_product_name: editSupplierName.trim(),
        supplier_product_code: editSupplierCode.trim() || null,
        product_id: editProductId || null,
        container_id: editContainerId || null,
      })
      setMappings(p => p.map(m => m.id === mid ? data : m))
      setEditId(null)
      setShowEditModal(false)
      showToast('Сохранено')
    } catch (e) { showToast(errMsg(e), false) }
    finally { setSaving(false) }
  }

  const openEditModal = (m: Mapping) => {
    setEditId(m.id)
    setEditSupplierId(m.supplier_id)
    setEditSupplierSearch('')
    setEditSupplierCode(m.supplier_product_code ?? '')
    setEditSupplierName(m.supplier_product_name)
    setEditProductId(m.product_id ?? '')
    setEditSearch(m.product_name ?? '')
    setEditContainerId(m.container_id ?? '')
    setEditResults([]); setShowEditList(false); setShowEditSupplierList(false)
    setShowEditModal(true)
  }

  const syncAll = async (type: 'products' | 'suppliers' | 'warehouses') => {
    if (syncCooldown > 0 || syncing || restaurants.length === 0) return
    setSyncing(true)
    try {
      const results = await Promise.allSettled(
        restaurants.map(r => coApi.post(`/admin/restaurants/${r.id}/sync/${type}`))
      )
      const failed = results
        .map((r, i) => r.status === 'rejected' ? restaurants[i].name : null)
        .filter(Boolean)
      const labels = { products: 'Товары', suppliers: 'Поставщики', warehouses: 'Склады' }
      if (failed.length === 0) {
        showToast(`${labels[type]} синхронизированы`)
      } else {
        showToast(`${labels[type]} синхронизированы. Ошибка: ${failed.join(', ')}`, false)
      }
      if (type === 'suppliers') {
        const { data } = await coApi.get('/admin/suppliers')
        setSuppliers(data)
      }
    } catch (e) { showToast(errMsg(e), false) }
    finally {
      setSyncing(false)
      setSyncCooldown(5)
      const interval = setInterval(() => {
        setSyncCooldown(prev => { if (prev <= 1) { clearInterval(interval); return 0 } return prev - 1 })
      }, 1000)
    }
  }

  const deleteMapping = async (mid: number) => {
    if (!confirm('Удалить маппинг?')) return
    try {
      await coApi.delete(`/admin/mappings/${mid}`)
      setMappings(p => p.filter(m => m.id !== mid))
      showToast('Удалено')
    } catch (e) { showToast(errMsg(e), false) }
  }

  return (
    <div className="space-y-4 max-w-5xl">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-lg font-bold text-brand-dark">
            Маппинг товаров{' '}
            <span className="text-brand-muted font-normal text-sm">
              ({listSearch ? `${filteredMappings.length} из ${mappings.length}` : mappings.length})
            </span>
          </h2>
          <p className="text-xs text-brand-muted mt-0.5">Соответствие: <strong>как товар называется у поставщика</strong> → <strong>какой товар в iiko</strong>.</p>
        </div>
        <div className="flex gap-2 items-center flex-wrap">
          <button
            onClick={() => syncAll('products')}
            disabled={syncing || syncCooldown > 0 || restaurants.length === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-brand-yellow/20 hover:bg-brand-yellow/30 border border-brand-yellow/40 text-brand-dark text-xs rounded-lg transition-colors disabled:opacity-50 font-medium"
          >
            {syncing ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
            Синхр. товары{syncCooldown > 0 ? ` (${syncCooldown}с)` : ''}
          </button>
        </div>
      </div>

      {/* Добавить новый */}
      <div className="card p-4">
        <h3 className="text-sm font-semibold text-brand-dark mb-3">Добавить маппинг</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:flex lg:flex-wrap gap-3 items-start">
          <div className="w-full sm:w-auto lg:w-52 relative">
            <label className="block text-xs text-brand-muted mb-1">Поставщик</label>
            <input
              value={newSupplierId ? (suppliers.find(s => s.id === newSupplierId)?.name ?? supplierSearch) : supplierSearch}
              onChange={e => { setSupplierSearch(e.target.value); setNewSupplierId(''); setShowSupplierList(true) }}
              onFocus={() => setShowSupplierList(true)}
              onBlur={() => setTimeout(() => setShowSupplierList(false), 150)}
              placeholder="Поиск поставщика..."
              className="input"
            />
            {showSupplierList && (
              <div className="absolute z-20 top-full mt-1 left-0 right-0 bg-white border border-brand-border rounded-lg shadow-lg max-h-56 overflow-y-auto">
                {suppliers.filter(s => !supplierSearch || s.name.toLowerCase().includes(supplierSearch.toLowerCase())).map(s => (
                  <button key={s.id} onMouseDown={() => { setNewSupplierId(s.id); setSupplierSearch(''); setShowSupplierList(false) }}
                    className="w-full text-left px-3 py-2 text-sm text-brand-dark hover:bg-brand-bg">
                    {s.name}
                  </button>
                ))}
                {suppliers.filter(s => !supplierSearch || s.name.toLowerCase().includes(supplierSearch.toLowerCase())).length === 0 && (
                  <div className="px-3 py-2 text-sm text-brand-muted">Не найдено</div>
                )}
              </div>
            )}
          </div>
          <div className="w-full sm:w-auto lg:w-32">
            <label className="block text-xs text-brand-muted mb-1">Код</label>
            <input value={newSupplierCode} onChange={e => setNewSupplierCode(e.target.value)} placeholder="Арт. 12345" className="input" />
          </div>
          <div className="w-full sm:col-span-2 lg:flex-1 lg:min-w-[180px]">
            <label className="block text-xs text-brand-muted mb-1">Название у поставщика</label>
            <input value={newSupplierName} onChange={e => setNewSupplierName(e.target.value)} placeholder="Как написано в накладной" className="input" onKeyDown={e => e.key === 'Enter' && addMapping()} />
          </div>
          <div className="hidden lg:block text-brand-muted mt-6">→</div>
          <div className="w-full sm:col-span-2 lg:flex-1 lg:min-w-[180px] relative">
            <label className="block text-xs text-brand-muted mb-1">Товар в iiko</label>
            <input
              value={newProductId ? newProductLabel : productSearch}
              onChange={e => { setProductSearch(e.target.value); setNewProductId(''); setNewProductLabel(''); setShowProductList(true) }}
              onFocus={() => setShowProductList(true)}
              onBlur={() => setTimeout(() => setShowProductList(false), 150)}
              placeholder="Начните вводить..."
              className="input"
            />
            {showProductList && (
              <div className="absolute z-10 top-full mt-1 left-0 right-0 bg-white border border-brand-border rounded-lg shadow-lg max-h-56 overflow-y-auto">
                <button onMouseDown={() => { setNewProductId(''); setNewProductLabel(''); setProductSearch(''); setShowProductList(false) }} className="w-full text-left px-3 py-2 text-sm text-brand-muted hover:bg-brand-bg border-b border-brand-border">— не указан</button>
                {productResults.map(p => (
                  <button key={p.id} onMouseDown={() => { setNewProductId(p.id); setNewProductLabel(p.name); setProductSearch(''); setShowProductList(false) }} className="w-full text-left px-3 py-2 text-sm text-brand-dark hover:bg-brand-bg">
                    {p.name} {p.unit && <span className="text-brand-muted ml-1 text-xs">{p.unit}</span>}
                  </button>
                ))}
                {productSearch.length > 0 && productResults.length === 0 && <div className="px-3 py-2 text-sm text-brand-muted">Не найдено</div>}
                {productSearch.length === 0 && productResults.length === 0 && <div className="px-3 py-2 text-sm text-brand-muted">Начните вводить для поиска</div>}
              </div>
            )}
          </div>
          <div className="w-full sm:w-auto lg:w-40">
            <label className="block text-xs text-brand-muted mb-1">Кейсовка</label>
            <select value={newContainerId} onChange={e => setNewContainerId(e.target.value ? Number(e.target.value) : '')} disabled={!newProductId || newContainers.length === 0} className="input">
              <option value="">— нет —</option>
              {newContainers.map(c => <option key={c.id} value={c.id}>{c.name} ×{c.count}</option>)}
            </select>
          </div>
          <button onClick={addMapping} disabled={saving || !newSupplierName.trim() || !newSupplierId} className="btn-primary w-full sm:col-span-2 lg:w-auto lg:mt-5">
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />} Добавить
          </button>
        </div>
      </div>

      {/* Список */}
      {loading ? (
        <div className="flex items-center gap-2 text-brand-muted"><Loader2 size={16} className="animate-spin" /> Загрузка...</div>
      ) : mappings.length === 0 ? (
        <div className="card p-8 text-center text-brand-muted text-sm">Нет маппингов. Добавьте первый выше.</div>
      ) : (
        <div className="card overflow-hidden">
          <div className="px-4 py-3 border-b border-brand-border flex items-center gap-3">
            <div className="relative flex-1 max-w-sm">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-brand-muted" />
              <input
                value={listSearch}
                onChange={e => { setListSearch(e.target.value); setCurrentPage(1) }}
                placeholder="Поиск по поставщику, названию, коду, товару iiko..."
                className="input pl-8 text-sm"
              />
              {listSearch && (
                <button onClick={() => { setListSearch(''); setCurrentPage(1) }} className="absolute right-2 top-1/2 -translate-y-1/2 text-brand-muted hover:text-brand-dark">
                  <X size={14} />
                </button>
              )}
            </div>
            {listSearch && filteredMappings.length === 0 && (
              <span className="text-xs text-brand-muted">Ничего не найдено</span>
            )}
          </div>
          {/* Mobile cards */}
          <div className="sm:hidden divide-y divide-brand-border">
            {paginated.map(m => (
              <div key={m.id} className="px-4 py-3">
                <div className="flex items-start justify-between gap-2 mb-1">
                  <div className="min-w-0">
                    <div className="font-medium text-brand-dark truncate">{m.supplier_product_name}</div>
                    <div className="text-xs text-brand-muted mt-0.5">
                      {m.supplier_name && <span>{m.supplier_name}</span>}
                      {m.supplier_product_code && <span className="ml-2 font-mono">{m.supplier_product_code}</span>}
                    </div>
                  </div>
                  <div className="flex gap-1 shrink-0">
                    <button onClick={() => openEditModal(m)} className="p-1.5 hover:bg-brand-bg rounded text-brand-muted hover:text-brand-dark transition-colors"><Edit2 size={14} /></button>
                    <button onClick={() => deleteMapping(m.id)} className="p-1.5 hover:bg-red-50 rounded text-brand-muted hover:text-red-600 transition-colors"><Trash2 size={14} /></button>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 mt-1 text-xs">
                  <span className="text-brand-muted">→</span>
                  {m.product_name
                    ? <span className="text-green-700 font-medium">{m.product_name}</span>
                    : <span className="text-brand-muted italic">не указан</span>}
                  {m.container_name && (
                    <span className="bg-blue-50 border border-blue-200 text-blue-700 px-1.5 py-0.5 rounded-full whitespace-nowrap">{m.container_name} ×{m.container_count}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
          {/* Desktop table */}
          <div className="hidden sm:block overflow-x-auto">
            <table className="w-full text-sm min-w-[800px]">
              <thead className="bg-brand-bg">
                <tr className="border-b border-brand-border text-brand-muted text-xs">
                  <th className="text-left px-3 py-2 font-medium">Поставщик</th>
                  <th className="text-left px-3 py-2 font-medium w-28">Код</th>
                  <th className="text-left px-3 py-2 font-medium">Название у поставщика</th>
                  <th className="px-2 py-2 text-brand-muted">→</th>
                  <th className="text-left px-3 py-2 font-medium">Товар в iiko</th>
                  <th className="text-left px-3 py-2 font-medium">Кейсовка</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {paginated.map(m => (
                  <tr key={m.id} className="border-b border-brand-border hover:bg-brand-bg">
                    <td className="px-3 py-2 text-xs text-brand-muted whitespace-nowrap">{m.supplier_name ?? '—'}</td>
                    <td className="px-3 py-2 font-mono text-xs text-brand-muted">{m.supplier_product_code ?? '—'}</td>
                    <td className="px-3 py-2 text-brand-dark">{m.supplier_product_name}</td>
                    <td className="px-2 py-2 text-brand-muted text-center">→</td>
                    <td className="px-3 py-2">
                      {m.product_name
                        ? <span className="text-brand-dark">{m.product_name}</span>
                        : <span className="text-brand-muted italic text-xs">не указан</span>}
                    </td>
                    <td className="px-3 py-2">
                      {m.container_name
                        ? <span className="text-xs bg-blue-50 border border-blue-200 text-blue-700 px-2 py-0.5 rounded-full">{m.container_name} ×{m.container_count}</span>
                        : <span className="text-xs text-brand-muted">—</span>}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex gap-1 justify-end">
                        <button onClick={() => openEditModal(m)} className="p-1.5 hover:bg-brand-bg rounded text-brand-muted hover:text-brand-dark transition-colors"><Edit2 size={13} /></button>
                        <button onClick={() => deleteMapping(m.id)} className="p-1.5 hover:bg-red-50 rounded text-brand-muted hover:text-red-600 transition-colors"><Trash2 size={13} /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* Пагинация */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-brand-border bg-brand-bg/40">
              <span className="text-xs text-brand-muted">
                {(safePage - 1) * PAGE_SIZE + 1}–{Math.min(safePage * PAGE_SIZE, filteredMappings.length)} из {filteredMappings.length}
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  disabled={safePage === 1}
                  className="px-2.5 py-1.5 text-xs rounded border border-brand-border bg-white hover:bg-brand-bg disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  ←
                </button>
                {Array.from({ length: totalPages }, (_, i) => i + 1).map(p => (
                  <button
                    key={p}
                    onClick={() => setCurrentPage(p)}
                    className={`px-2.5 py-1.5 text-xs rounded border transition-colors ${p === safePage ? 'bg-brand-yellow border-brand-yellow/60 text-brand-dark font-semibold' : 'border-brand-border bg-white hover:bg-brand-bg'}`}
                  >
                    {p}
                  </button>
                ))}
                <button
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                  disabled={safePage === totalPages}
                  className="px-2.5 py-1.5 text-xs rounded border border-brand-border bg-white hover:bg-brand-bg disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  →
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Модальное окно редактирования */}
      {showEditModal && editId !== null && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 backdrop-blur-sm sm:p-4">
          <div className="bg-white rounded-t-2xl sm:rounded-2xl shadow-2xl w-full sm:max-w-lg max-h-[92vh] sm:max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between px-4 sm:px-6 py-4 border-b border-brand-border shrink-0">
              <h2 className="font-bold text-brand-dark text-base">Редактировать маппинг</h2>
              <button onClick={() => { setShowEditModal(false); setEditId(null) }} className="p-1.5 rounded-lg hover:bg-brand-bg transition-colors">
                <X size={16} className="text-brand-muted" />
              </button>
            </div>
            <div className="px-4 sm:px-6 py-5 space-y-4 overflow-y-auto">
              {/* Поставщик */}
              <div className="relative">
                <label className="block text-xs text-brand-muted mb-1">Поставщик</label>
                <input
                  value={editSupplierId ? (suppliers.find(s => s.id === editSupplierId)?.name ?? editSupplierSearch) : editSupplierSearch}
                  onChange={e => { setEditSupplierSearch(e.target.value); setEditSupplierId(''); setShowEditSupplierList(true) }}
                  onFocus={() => setShowEditSupplierList(true)}
                  onBlur={() => setTimeout(() => setShowEditSupplierList(false), 150)}
                  placeholder="Поиск поставщика..."
                  className="input w-full"
                />
                {showEditSupplierList && (
                  <div className="absolute z-20 top-full mt-1 left-0 right-0 bg-white border border-brand-border rounded-lg shadow-lg max-h-48 overflow-y-auto">
                    {suppliers.filter(s => !editSupplierSearch || s.name.toLowerCase().includes(editSupplierSearch.toLowerCase())).map(s => (
                      <button key={s.id} onMouseDown={() => { setEditSupplierId(s.id); setEditSupplierSearch(''); setShowEditSupplierList(false) }}
                        className="w-full text-left px-3 py-2 text-sm text-brand-dark hover:bg-brand-bg">
                        {s.name}
                      </button>
                    ))}
                    {suppliers.filter(s => !editSupplierSearch || s.name.toLowerCase().includes(editSupplierSearch.toLowerCase())).length === 0 && (
                      <div className="px-3 py-2 text-sm text-brand-muted">Не найдено</div>
                    )}
                  </div>
                )}
              </div>
              {/* Код */}
              <div>
                <label className="block text-xs text-brand-muted mb-1">Код поставщика</label>
                <input value={editSupplierCode} onChange={e => setEditSupplierCode(e.target.value)} placeholder="Арт. 12345" className="input w-full font-mono" />
              </div>
              {/* Название */}
              <div>
                <label className="block text-xs text-brand-muted mb-1">Название у поставщика</label>
                <input value={editSupplierName} onChange={e => setEditSupplierName(e.target.value)} className="input w-full" />
              </div>
              {/* Товар iiko */}
              <div className="relative">
                <label className="block text-xs text-brand-muted mb-1">Товар в iiko</label>
                <input
                  value={editSearch}
                  onChange={e => { setEditSearch(e.target.value); setEditProductId(''); setShowEditList(true) }}
                  onFocus={() => setShowEditList(true)}
                  onBlur={() => setTimeout(() => setShowEditList(false), 150)}
                  placeholder="Начните вводить..."
                  className="input w-full"
                />
                {showEditList && (
                  <div className="absolute z-20 top-full mt-1 left-0 right-0 bg-white border border-brand-border rounded-lg shadow-lg max-h-48 overflow-y-auto">
                    <button onMouseDown={() => { setEditProductId(''); setEditSearch(''); setShowEditList(false) }} className="w-full text-left px-3 py-2 text-sm text-brand-muted hover:bg-brand-bg border-b border-brand-border">— не указан</button>
                    {editResults.map(p => (
                      <button key={p.id} onMouseDown={() => { setEditProductId(p.id); setEditSearch(p.name); setShowEditList(false) }} className="w-full text-left px-3 py-2 text-sm text-brand-dark hover:bg-brand-bg">
                        {p.name} {p.unit && <span className="text-brand-muted ml-1 text-xs">{p.unit}</span>}
                      </button>
                    ))}
                    {editSearch.length > 0 && editResults.length === 0 && <div className="px-3 py-2 text-sm text-brand-muted">Не найдено</div>}
                  </div>
                )}
              </div>
              {/* Кейсовка */}
              <div>
                <label className="block text-xs text-brand-muted mb-1">Кейсовка</label>
                <select value={editContainerId} onChange={e => setEditContainerId(e.target.value ? Number(e.target.value) : '')} disabled={!editProductId || editContainers.length === 0} className="input w-full">
                  <option value="">— нет —</option>
                  {editContainers.map(c => <option key={c.id} value={c.id}>{c.name} ×{c.count}</option>)}
                </select>
              </div>
            </div>
            <div className="flex gap-2 justify-end px-4 sm:px-6 py-4 border-t border-brand-border shrink-0">
              <button onClick={() => { setShowEditModal(false); setEditId(null) }} className="btn-secondary">Отмена</button>
              <button onClick={() => saveEdit(editId)} disabled={saving || !editSupplierName.trim()} className="btn-primary">
                {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Сохранить
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── CONTAINERS ────────────────────────────────────────────────────────────────

function ContainersTab({ showToast }: { showToast: (m: string, ok?: boolean) => void }) {
  const [containers, setContainers] = useState<Container[]>([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState<Partial<Container> | null>(null)
  const [editId, setEditId] = useState<number | null>(null)
  const [saving, setSaving] = useState(false)
  const [productSearch, setProductSearch] = useState('')
  const [productResults, setProductResults] = useState<Product[]>([])
  const [showProductList, setShowProductList] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try { setContainers((await coApi.get('/admin/containers')).data) }
    catch (e) { showToast(errMsg(e), false) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!productSearch.trim()) { setProductResults([]); return }
    const t = setTimeout(async () => {
      const { data } = await coApi.get('/admin/products', { params: { search: productSearch } })
      setProductResults(data)
    }, 300)
    return () => clearTimeout(t)
  }, [productSearch])

  const save = async () => {
    if (!form?.product_id || !form?.iiko_container_id || !form?.name || !form?.count) return
    setSaving(true)
    try {
      editId
        ? await coApi.patch(`/admin/containers/${editId}`, form)
        : await coApi.post('/admin/containers', form)
      showToast(editId ? 'Обновлено' : 'Создано'); setForm(null); setEditId(null); load()
    } catch (e) { showToast(errMsg(e), false) }
    finally { setSaving(false) }
  }

  return (
    <div className="space-y-4 max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-brand-dark">Кейсовки</h2>
          <p className="text-xs text-brand-muted mt-0.5">UUID упаковки из iiko — для корректной отправки накладных</p>
        </div>
        <button onClick={() => { setForm({ iiko_container_id: '', name: '', count: 1, product_id: undefined }); setEditId(null) }} className="btn-primary">
          <Plus size={14} /> Добавить
        </button>
      </div>

      {form && (
        <div className="card p-4 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="sm:col-span-2 relative">
              <label className="block text-xs font-medium text-brand-muted mb-1">Товар iiko</label>
              <input
                value={form.product_id ? (form.product_name || String(form.product_id)) : productSearch}
                onChange={e => { setProductSearch(e.target.value); setForm(p => ({ ...p, product_id: undefined, product_name: undefined })); setShowProductList(true) }}
                onFocus={() => setShowProductList(true)}
                onBlur={() => setTimeout(() => setShowProductList(false), 150)}
                placeholder="Начните вводить название товара..."
                className="input"
              />
              {showProductList && (
                <div className="absolute z-10 top-full mt-1 left-0 right-0 bg-white border border-brand-border rounded-lg shadow-lg max-h-48 overflow-y-auto">
                  {productResults.map(p => (
                    <button key={p.id} onMouseDown={() => { setForm(prev => ({ ...prev, product_id: p.id, product_name: p.name })); setProductSearch(''); setShowProductList(false) }}
                      className="w-full text-left px-3 py-2 text-sm text-brand-dark hover:bg-brand-bg">
                      {p.name}
                    </button>
                  ))}
                  {productSearch && productResults.length === 0 && <div className="px-3 py-2 text-sm text-brand-muted">Не найдено</div>}
                </div>
              )}
            </div>
            <div>
              <label className="block text-xs font-medium text-brand-muted mb-1">UUID контейнера в iiko</label>
              <input value={form.iiko_container_id ?? ''} onChange={e => setForm(p => ({ ...p, iiko_container_id: e.target.value }))} placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" className="input font-mono text-xs" />
            </div>
            <div>
              <label className="block text-xs font-medium text-brand-muted mb-1">Название упаковки</label>
              <input value={form.name ?? ''} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} placeholder="Коробка 12шт" className="input" />
            </div>
            <div>
              <label className="block text-xs font-medium text-brand-muted mb-1">Единиц в упаковке</label>
              <input type="number" value={form.count ?? 1} onChange={e => setForm(p => ({ ...p, count: parseFloat(e.target.value) }))} min="1" step="0.001" className="input" />
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={save} disabled={saving} className="btn-primary">
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />} Сохранить
            </button>
            <button onClick={() => { setForm(null); setEditId(null) }} className="btn-secondary"><X size={14} /> Отмена</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-brand-muted"><Loader2 size={16} className="animate-spin" /> Загрузка...</div>
      ) : containers.length === 0 ? (
        <div className="card p-8 text-center text-brand-muted text-sm">Нет кейсовок. Добавьте первую.</div>
      ) : (
        <div className="card overflow-hidden">
          {/* Mobile cards */}
          <div className="sm:hidden divide-y divide-brand-border">
            {containers.map(c => (
              <div key={c.id} className="px-4 py-3 flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-medium text-brand-dark truncate">{c.product_name}</div>
                  <div className="text-xs text-brand-muted mt-0.5">
                    <span>{c.name}</span>
                    <span className="mx-1.5 text-brand-border">·</span>
                    <span className="font-semibold text-brand-dark">{c.count}</span> ед.
                  </div>
                </div>
                <div className="flex gap-1 shrink-0">
                  <button onClick={() => { setForm({ ...c }); setEditId(c.id) }} className="p-1.5 hover:bg-brand-bg rounded text-brand-muted hover:text-brand-dark transition-colors"><Edit2 size={14} /></button>
                  <button onClick={async () => { if (!confirm('Удалить?')) return; await coApi.delete(`/admin/containers/${c.id}`); showToast('Удалено'); load() }} className="p-1.5 hover:bg-red-50 rounded text-brand-muted hover:text-red-600 transition-colors"><Trash2 size={14} /></button>
                </div>
              </div>
            ))}
          </div>
          {/* Desktop table */}
          <div className="hidden sm:block overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-brand-bg">
                <tr className="border-b border-brand-border text-brand-muted text-xs">
                  <th className="text-left px-4 py-2 font-medium">Товар</th>
                  <th className="text-left px-4 py-2 font-medium">Упаковка</th>
                  <th className="text-right px-4 py-2 font-medium">Единиц</th>
                  <th className="text-left px-4 py-2 font-medium">iiko UUID</th>
                  <th className="px-4 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {containers.map(c => (
                  <tr key={c.id} className="border-b border-brand-border hover:bg-brand-bg">
                    <td className="px-4 py-2 text-brand-dark">{c.product_name}</td>
                    <td className="px-4 py-2 text-brand-dark">{c.name}</td>
                    <td className="px-4 py-2 text-right font-medium text-brand-dark">{c.count}</td>
                    <td className="px-4 py-2 font-mono text-xs text-brand-muted">{c.iiko_container_id.slice(0, 14)}...</td>
                    <td className="px-4 py-2">
                      <div className="flex gap-1 justify-end">
                        <button onClick={() => { setForm({ ...c }); setEditId(c.id) }} className="p-1 hover:bg-brand-bg rounded text-brand-muted hover:text-brand-dark transition-colors"><Edit2 size={13} /></button>
                        <button onClick={async () => { if (!confirm('Удалить?')) return; await coApi.delete(`/admin/containers/${c.id}`); showToast('Удалено'); load() }} className="p-1 hover:bg-red-50 rounded text-brand-muted hover:text-red-600 transition-colors"><Trash2 size={13} /></button>
                      </div>
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
