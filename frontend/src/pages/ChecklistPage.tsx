import { useState, useEffect } from "react"
import { ExternalLink, TableProperties, Info, FileDown, PlayCircle, CheckCircle2, Clock, Trash2 } from "lucide-react"
import { useAuth } from "../hooks/useAuth"
import api from "../api/client"

function extractSheetId(url: string): string | null {
  if (!url) return null
  if (!url.includes("/")) return url.trim()
  const parts = url.split("/d/")
  if (parts.length < 2) return null
  return parts[1].split("/")[0].trim()
}

function pdfUrl(sheetUrl: string): string {
  const id = extractSheetId(sheetUrl)
  if (!id) return "#"
  return `https://docs.google.com/spreadsheets/d/${id}/export?format=pdf&portrait=false&fitw=true&gridlines=false`
}

interface DayStatus {
  restaurant_id: number
  restaurant_name: string
  started_today: boolean
  last_reset_date: string | null
  checklist_start_hour: number
}

export default function ChecklistPage() {
  const { user } = useAuth()
  const [statuses, setStatuses] = useState<DayStatus[]>([])
  const [starting, setStarting] = useState(false)
  const [startingRestaurant, setStartingRestaurant] = useState<number | null>(null)
  const [clearingRestaurant, setClearingRestaurant] = useState<number | null>(null)
  const [msg, setMsg] = useState<string | null>(null)

  const restaurants = user?.restaurants ?? []

  useEffect(() => {
    api.get("/checklist/status").then(r => setStatuses(r.data)).catch(() => {})
  }, [])

  const getStatus = (restaurantId: number) =>
    statuses.find(s => s.restaurant_id === restaurantId)

  const handleStartDay = async () => {
    setStarting(true)
    setMsg(null)
    try {
      await api.post("/checklist/start-day")
      // Обновляем статусы
      const r = await api.get("/checklist/status")
      setStatuses(r.data)
      setMsg("Новый день начат! Данные загружаются в Google Sheets (~2 мин)")
    } catch {
      setMsg("Ошибка при запуске синхронизации")
    } finally {
      setStarting(false)
    }
  }

  const handleStartDayForRestaurant = async (restaurantId: number, name: string) => {
    setStartingRestaurant(restaurantId)
    setMsg(null)
    try {
      const res = await api.post(`/checklist/start-day/${restaurantId}`)
      const r = await api.get("/checklist/status")
      setStatuses(r.data)
      setMsg(`${name}: ${res.data.message}`)
    } catch (e: any) {
      setMsg(`${name}: ${e.response?.data?.detail || "Ошибка при запуске"}`)
    } finally {
      setStartingRestaurant(null)
    }
  }

  const handleClearSheets = async (restaurantId: number, name: string) => {
    if (!confirm(`Очистить Google Sheets для "${name}"?\n\nЧекбоксы → сняты, обеденные ячейки → пусто.`)) return
    setClearingRestaurant(restaurantId)
    setMsg(null)
    try {
      const res = await api.post(`/checklist/clear/${restaurantId}`)
      setMsg(`${name}: ${res.data.message}`)
    } catch (e: any) {
      setMsg(`${name}: ${e.response?.data?.detail || "Ошибка при очистке"}`)
    } finally {
      setClearingRestaurant(null)
    }
  }

  if (user?.role === "store") {
    const rest = restaurants[0]
    const url = rest?.google_sheet_url
    const status = getStatus(rest?.id)

    return (
      <div className="p-4 sm:p-6 max-w-2xl mx-auto">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl bg-brand-yellow/10 flex items-center justify-center">
            <TableProperties size={20} className="text-brand-yellow" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-brand-dark">Чек-лист смены</h1>
            <p className="text-brand-muted text-sm">{rest?.name}</p>
          </div>
        </div>

        {url ? (
          <div className="space-y-4">
            {/* Статус дня */}
            <div className={`card p-4 flex items-center justify-between ${status?.started_today ? "border-green-200 bg-green-50/50" : "border-brand-yellow/30 bg-brand-yellow/5"}`}>
              <div className="flex items-center gap-3">
                {status?.started_today ? (
                  <CheckCircle2 size={20} className="text-green-600" />
                ) : (
                  <Clock size={20} className="text-brand-yellow" />
                )}
                <div>
                  <p className="font-medium text-brand-dark text-sm">
                    {status?.started_today ? "День начат — синхронизация активна" : "День ещё не начат"}
                  </p>
                  <p className="text-xs text-brand-muted">
                    {status?.started_today
                      ? "Данные обновляются каждый час из IIKO"
                      : `Нажмите кнопку ниже когда придёте на смену (с ${status?.checklist_start_hour ?? 7}:00)`}
                  </p>
                </div>
              </div>
            </div>

            {/* Кнопка начать день */}
            {!status?.started_today && (
              <button
                onClick={handleStartDay}
                disabled={starting}
                className="btn-primary w-full gap-2 py-3 text-base justify-center"
              >
                <PlayCircle size={18} />
                {starting ? "Запускаем..." : "Начать новый день"}
              </button>
            )}

            {msg && (
              <div className={`p-3 rounded-xl text-sm text-center ${msg.includes("Ошибка") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
                {msg}
              </div>
            )}

            {/* Кнопки таблицы */}
            <div className="card p-6 flex flex-col items-center gap-4 text-center">
              <div className="w-14 h-14 rounded-2xl bg-green-50 flex items-center justify-center">
                <TableProperties size={28} className="text-green-600" />
              </div>
              <div>
                <p className="text-brand-dark font-semibold">Google Таблица чек-листа</p>
                <p className="text-brand-muted text-sm mt-1">Данные обновляются автоматически</p>
              </div>
              <div className="flex gap-3 flex-wrap justify-center">
                <a
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-primary gap-2 px-6 py-2.5"
                >
                  Открыть чек-лист
                  <ExternalLink size={15} />
                </a>
                <a
                  href={pdfUrl(url)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-secondary gap-2 px-6 py-2.5"
                >
                  Скачать PDF
                  <FileDown size={15} />
                </a>
                <button
                  onClick={() => handleClearSheets(rest.id, rest.name)}
                  disabled={clearingRestaurant === rest.id}
                  className="btn-secondary gap-2 px-6 py-2.5 text-red-600 border-red-200 hover:bg-red-50"
                >
                  <Trash2 size={15} />
                  {clearingRestaurant === rest.id ? "Очищаем..." : "Очистить"}
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="card p-8 flex flex-col items-center gap-4 text-center">
            <div className="w-14 h-14 rounded-2xl bg-brand-yellow/10 flex items-center justify-center">
              <Info size={28} className="text-brand-muted" />
            </div>
            <p className="text-brand-dark font-semibold">Ссылка не настроена</p>
            <p className="text-brand-muted text-sm">
              Обратитесь к администратору для настройки ссылки на Google Таблицу
            </p>
          </div>
        )}
      </div>
    )
  }

  // CO / Admin — список всех ресторанов
  const withLinks = restaurants.filter(r => r.google_sheet_url)
  const withoutLinks = restaurants.filter(r => !r.google_sheet_url)

  return (
    <div className="p-4 sm:p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-brand-yellow/10 flex items-center justify-center">
            <TableProperties size={20} className="text-brand-yellow" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-brand-dark">Чек-листы смен</h1>
            <p className="text-brand-muted text-sm">Google Таблицы по ресторанам</p>
          </div>
        </div>
        <button
          onClick={handleStartDay}
          disabled={starting}
          className="btn-primary gap-2"
        >
          <PlayCircle size={15} />
          {starting ? "Запускаем..." : "Начать день (все)"}
        </button>
      </div>

      {msg && (
        <div className={`mb-4 p-3 rounded-xl text-sm ${msg.includes("Ошибка") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
          {msg}
        </div>
      )}

      {withLinks.length > 0 && (
        <div className="space-y-3 mb-6">
          {withLinks.map(r => {
            const status = getStatus(r.id)
            return (
              <div key={r.id} className="card p-4 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  {status?.started_today ? (
                    <CheckCircle2 size={16} className="text-green-500 flex-shrink-0" />
                  ) : (
                    <Clock size={16} className="text-brand-muted flex-shrink-0" />
                  )}
                  <div>
                    <p className="font-medium text-brand-dark">{r.name}</p>
                    <p className="text-xs text-brand-muted">
                      {status?.started_today ? "Активен сегодня" : "Не начат"}
                    </p>
                  </div>
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  <button
                    onClick={() => handleStartDayForRestaurant(r.id, r.name)}
                    disabled={startingRestaurant === r.id}
                    className="btn-primary gap-1.5 text-sm py-1.5"
                    title="Начать новый день для этого ресторана"
                  >
                    <PlayCircle size={13} />
                    {startingRestaurant === r.id ? "..." : "Новый день"}
                  </button>
                  <button
                    onClick={() => handleClearSheets(r.id, r.name)}
                    disabled={clearingRestaurant === r.id}
                    className="btn-secondary gap-1.5 text-sm py-1.5 text-red-600 border-red-200 hover:bg-red-50"
                    title="Очистить чекбоксы и обеденные ячейки"
                  >
                    <Trash2 size={13} />
                    {clearingRestaurant === r.id ? "..." : "Очистить"}
                  </button>
                  <a
                    href={r.google_sheet_url!}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn-secondary gap-1.5 text-sm py-1.5"
                  >
                    Открыть
                    <ExternalLink size={13} />
                  </a>
                  <a
                    href={pdfUrl(r.google_sheet_url!)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn-secondary gap-1.5 text-sm py-1.5"
                  >
                    PDF
                    <FileDown size={13} />
                  </a>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {withoutLinks.length > 0 && (
        <div>
          <p className="text-brand-muted text-xs uppercase tracking-widest font-semibold mb-3">
            Не настроены
          </p>
          <div className="space-y-2">
            {withoutLinks.map(r => (
              <div key={r.id} className="card p-3 flex items-center gap-3 opacity-50">
                <div className="w-7 h-7 rounded-lg bg-brand-bg flex items-center justify-center">
                  <TableProperties size={13} className="text-brand-muted" />
                </div>
                <p className="text-sm text-brand-muted">{r.name}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-6 p-4 rounded-xl bg-brand-bg border border-brand-border/50 flex gap-3">
        <Info size={16} className="text-brand-muted mt-0.5 flex-shrink-0" />
        <p className="text-sm text-brand-muted">
          Ссылки и час начала дня настраиваются в разделе{" "}
          <span className="font-medium text-brand-dark">Администрирование → Рестораны</span>
        </p>
      </div>
    </div>
  )
}
