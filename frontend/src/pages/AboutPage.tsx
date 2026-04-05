import {
  Info, BarChart2, FileText, TrendingUp, FileInput,
  TableProperties, MessageCircle, ChevronRight,
} from "lucide-react"

const modules = [
  {
    icon: BarChart2,
    title: "Дашборд",
    how: "Открывается по умолчанию. Показывает KPI по списаниям за текущий или прошлый месяц. Переключайте периоды кнопками вверху. Почасовой график показывает продажи и заказы за выбранный день.",
  },
  {
    icon: FileText,
    title: "Отчёты",
    how: "Выберите период (месяц или неделю), нажмите «Сформировать». После готовности можно просмотреть строки, скачать Excel или нажать «К списанию» для отправки акта в IIKO.",
  },
  {
    icon: TrendingUp,
    title: "Аналитика",
    how: "Выберите год и ресторан. Линейный график показывает Waste State%, Stat Lost% и Complete Waste% по месяцам. Ниже — топ групп и продуктов, которые чаще всего превышают норму.",
  },
  {
    icon: BarChart2,
    title: "Планирование",
    how: "Показывает план и факт продаж по дням месяца. Планы рассчитываются автоматически. Для установки месячной цели нажмите на поле цели вверху (только ЦО/Администратор).",
  },
  {
    icon: FileInput,
    title: "Накладные",
    how: "Загрузите Excel-файл накладной ABL кнопкой «Загрузить». После загрузки проверьте маппинг товаров (✓ — сопоставлено, ✗ — нет). Нажмите «Отправить в IIKO» для проведения.",
  },
  {
    icon: TableProperties,
    title: "Чек-лист смены",
    how: "Открывает чек-лист менеджера смены в Google Таблице. Нажмите кнопку «Открыть чек-лист» — откроется таблица в новой вкладке.",
  },
]

export default function AboutPage() {
  return (
    <div className="p-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-8">
        <div className="w-10 h-10 rounded-xl bg-brand-yellow/10 flex items-center justify-center">
          <Info size={20} className="text-brand-yellow" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-brand-dark">О системе</h1>
          <p className="text-brand-muted text-sm">Reston Analytics</p>
        </div>
      </div>

      {/* Logo + description */}
      <div className="card p-8 flex flex-col sm:flex-row items-center gap-6 mb-6">
        <img src="/forwhite.png" alt="Reston Analytics" className="h-20 w-auto flex-shrink-0" />
        <div>
          <h2 className="text-xl font-bold text-brand-dark mb-1">Reston Analytics</h2>
          <p className="text-brand-muted text-sm leading-relaxed">
            Система аналитики и контроля ресторанов. Обеспечивает полный цикл управления
            списаниями: от генерации отчётов и сверки с нормами до отправки актов в IIKO
            и мониторинга KPI по всей сети ресторанов.
          </p>
        </div>
      </div>

      {/* How to use */}
      <h3 className="text-sm font-semibold text-brand-dark/70 uppercase tracking-widest mb-3">
        Как пользоваться
      </h3>
      <div className="space-y-3 mb-8">
        {modules.map(({ icon: Icon, title, how }) => (
          <div key={title} className="card p-4 flex gap-4">
            <div className="w-9 h-9 rounded-xl bg-brand-yellow/10 flex items-center justify-center flex-shrink-0 mt-0.5">
              <Icon size={16} className="text-brand-yellow" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <p className="font-semibold text-brand-dark text-sm">{title}</p>
                <ChevronRight size={13} className="text-brand-muted" />
              </div>
              <p className="text-brand-muted text-sm leading-relaxed">{how}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Support */}
      <h3 className="text-sm font-semibold text-brand-dark/70 uppercase tracking-widest mb-3">
        Поддержка
      </h3>
      <a
        href="https://wa.me/77086041772"
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-4 card p-5 hover:shadow-md transition-shadow group"
      >
        <div className="w-12 h-12 rounded-2xl bg-green-500 flex items-center justify-center flex-shrink-0">
          <MessageCircle size={22} className="text-white" />
        </div>
        <div>
          <p className="font-semibold text-brand-dark group-hover:text-green-700 transition-colors">
            Написать поддержке
          </p>
          <p className="text-brand-muted text-sm">WhatsApp · +7 708 604 17 72</p>
        </div>
      </a>

      {/* Footer */}
      <p className="text-center text-brand-muted/50 text-xs mt-8">
        © 2026 Reston Analytics
      </p>
    </div>
  )
}
