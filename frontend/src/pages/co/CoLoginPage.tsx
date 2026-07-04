import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import coApi from '../../api/coClient'
import { Loader2, Eye, EyeOff, ShieldCheck, FileText, Check, ArrowRight } from 'lucide-react'

export default function CoLoginPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showPass, setShowPass] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const form = new URLSearchParams()
      form.append('username', email.trim().toLowerCase())
      form.append('password', password)
      const { data } = await coApi.post('/auth/login', form.toString(), {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      localStorage.setItem('co_access_token', data.access_token)
      localStorage.setItem('co_refresh_token', data.refresh_token)
      navigate(data.role === 'admin' ? '/dashboard' : '/invoices')
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Неверный логин или пароль')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex bg-brand-bg">

      {/* ── Left panel: form ── */}
      <div className="flex flex-col w-full lg:w-[480px] xl:w-[540px] shrink-0 px-6 sm:px-12 xl:px-16 py-10">

        {/* Logo */}
        <div className="flex items-center gap-2.5">
          <img src="/brand/icon-light.svg" alt="RestOn" className="w-10 h-10" />
          <span className="text-xl font-bold tracking-tight text-brand-dark">
            Rest<span className="text-brand-green">On</span>
          </span>
        </div>

        {/* Form block, vertically centered */}
        <div className="flex-1 flex flex-col justify-center py-12">
          <div className="w-full max-w-[360px]">

            <h1 className="text-[28px] leading-tight font-bold text-brand-dark mb-2">
              Вход в RestOn
            </h1>
            <p className="text-sm text-brand-muted leading-relaxed mb-9">
              Платформа для накладных, складов, списаний и iiko-интеграции
            </p>

            <form onSubmit={submit} className="space-y-5">
              {error && (
                <div className="px-4 py-3 rounded-lg bg-red-50 text-red-700 text-sm">
                  {error}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-brand-dark mb-2">
                  Логин или email
                </label>
                <input
                  type="text"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                  placeholder="логин"
                  autoComplete="username"
                  autoFocus
                  className="w-full px-4 py-3 rounded-xl border border-brand-border bg-white text-sm text-brand-dark
                             placeholder-brand-muted/60 outline-none transition-all duration-150
                             focus:border-brand-green focus:ring-[3px] focus:ring-brand-green/15"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium text-brand-dark">Пароль</label>
                  <a
                    href="mailto:support@reston.kz?subject=Забыл пароль от RestOn"
                    className="text-xs font-medium text-brand-green hover:underline underline-offset-2"
                  >
                    Забыли пароль?
                  </a>
                </div>
                <div className="relative">
                  <input
                    type={showPass ? 'text' : 'password'}
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    required
                    placeholder="••••••••"
                    autoComplete="current-password"
                    className="w-full px-4 py-3 pr-11 rounded-xl border border-brand-border bg-white text-sm text-brand-dark
                               placeholder-brand-muted/60 outline-none transition-all duration-150
                               focus:border-brand-green focus:ring-[3px] focus:ring-brand-green/15"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPass(v => !v)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-brand-muted hover:text-brand-dark transition-colors"
                    tabIndex={-1}
                  >
                    {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-brand-green text-white
                           font-semibold text-[15px] transition-colors duration-150
                           hover:bg-[#0B7C61] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading && <Loader2 size={16} className="animate-spin" />}
                Войти
              </button>

              {/* Divider */}
              <div className="flex items-center gap-3 pt-1">
                <div className="flex-1 h-px bg-brand-border" />
                <span className="text-xs text-brand-muted">или</span>
                <div className="flex-1 h-px bg-brand-border" />
              </div>

              {/* Google */}
              <a
                href="/api/auth/google/login"
                className="flex items-center justify-center gap-2.5 w-full py-3 rounded-xl border border-brand-border
                           bg-white text-sm font-medium text-brand-dark transition-colors duration-150
                           hover:bg-white hover:border-brand-muted/40"
              >
                <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
                  <path fill="#4285F4" d="M16.51 8H8.98v3h4.3c-.18 1-.74 1.48-1.6 2.04v2.01h2.6a7.8 7.8 0 002.38-5.88c0-.57-.05-.66-.15-1.18z"/>
                  <path fill="#34A853" d="M8.98 17c2.16 0 3.97-.72 5.3-1.94l-2.6-2a4.8 4.8 0 01-7.18-2.54H1.83v2.07A8 8 0 008.98 17z"/>
                  <path fill="#FBBC05" d="M4.5 10.52a4.8 4.8 0 010-3.04V5.41H1.83a8 8 0 000 7.18l2.67-2.07z"/>
                  <path fill="#EA4335" d="M8.98 4.18c1.17 0 2.23.4 3.06 1.2l2.3-2.3A8 8 0 001.83 5.4L4.5 7.49a4.77 4.77 0 014.48-3.31z"/>
                </svg>
                Войти через Google
              </a>
            </form>

            <p className="mt-8 text-sm text-brand-muted text-center">
              Нет аккаунта?{' '}
              <a
                href="mailto:support@reston.kz?subject=Запрос доступа к RestOn"
                className="font-medium text-brand-green hover:underline underline-offset-2"
              >
                Запросить доступ
              </a>
            </p>
          </div>
        </div>

        {/* Bottom note */}
        <div className="flex items-center gap-2 text-xs text-brand-muted">
          <ShieldCheck size={14} className="shrink-0" />
          <span>Для ресторанных сетей, складов и бухгалтерии</span>
        </div>
      </div>

      {/* ── Right panel: product preview on deep navy ── */}
      <div className="hidden lg:flex flex-1 flex-col relative overflow-hidden bg-[#0F2D3D] p-12 xl:p-14">

        {/* Depth: soft green glow + darker bottom */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(13,147,115,0.12),transparent_55%)] pointer-events-none" />
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-black/25 pointer-events-none" />

        {/* Watermark R */}
        <img
          src="/brand/icon-dark.svg"
          alt=""
          aria-hidden="true"
          className="absolute -bottom-40 -right-40 w-[640px] h-[640px] opacity-[0.05] pointer-events-none select-none"
        />

        {/* Top row: logo + iiko pill */}
        <div className="relative z-10 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <img src="/brand/icon-dark.svg" alt="RestOn" className="w-10 h-10" />
            <span className="text-xl font-bold tracking-tight text-white">
              Rest<span className="text-brand-green brightness-125">On</span>
            </span>
          </div>
          <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-brand-green/10 border border-brand-green/25">
            <span className="w-1.5 h-1.5 rounded-full bg-brand-green" />
            <span className="text-xs font-medium text-brand-green brightness-125">iiko подключен</span>
          </div>
        </div>

        {/* Headline */}
        <div className="relative z-10 flex-1 flex flex-col justify-center max-w-xl">
          <p className="text-xs font-semibold tracking-[0.2em] uppercase text-brand-green brightness-125 mb-5">
            Operations Control Hub
          </p>
          <h2 className="text-[40px] xl:text-[44px] font-bold leading-[1.15] text-white mb-5 text-balance">
            Операционный контроль ресторанной сети
          </h2>
          <p className="text-base text-white/55 leading-relaxed max-w-md">
            Накладные, склады, списания и синхронизация с iiko —
            в одном защищённом рабочем пространстве.
          </p>
        </div>

        {/* Product preview: invoice card + stats */}
        <div className="relative z-10 max-w-2xl space-y-3">

          {/* Invoice card */}
          <div className="rounded-2xl bg-white/[0.05] border border-white/10 backdrop-blur-sm p-5">
            <div className="flex items-center justify-between gap-4 mb-4">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-9 h-9 rounded-lg bg-white/90 flex items-center justify-center shrink-0">
                  <FileText size={16} className="text-brand-navy" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-white truncate">Накладная №INV-0612</p>
                  <p className="text-xs text-white/45 truncate">МЕТРО Кэш энд Керри</p>
                </div>
              </div>
              <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-brand-green/15 shrink-0">
                <Check size={12} className="text-brand-green brightness-125" />
                <span className="text-xs font-medium text-brand-green brightness-125">Распознано · 99%</span>
              </div>
            </div>
            <div className="flex items-center gap-1.5 flex-wrap">
              {['Фото / PDF', 'Распознавание', 'Проверка'].map(step => (
                <span key={step} className="flex items-center gap-1.5">
                  <span className="px-2.5 py-1 rounded-md bg-white/[0.07] text-xs text-white/60">{step}</span>
                  <ArrowRight size={11} className="text-white/25" />
                </span>
              ))}
              <span className="px-2.5 py-1 rounded-md bg-brand-green text-xs font-semibold text-white">iiko</span>
            </div>
          </div>

          {/* Stat tiles */}
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-xl bg-white/[0.05] border border-white/10 backdrop-blur-sm px-5 py-4">
              <p className="text-2xl font-bold text-white tabular-nums">24</p>
              <p className="text-xs text-white/45 mt-0.5">накладных сегодня</p>
            </div>
            <div className="rounded-xl bg-white/[0.05] border border-white/10 backdrop-blur-sm px-5 py-4">
              <p className="text-2xl font-bold text-white tabular-nums">
                18 <span className="text-sm font-semibold text-brand-green brightness-125">в iiko</span>
              </p>
              <p className="text-xs text-white/45 mt-0.5">синхронизировано 2 мин назад</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
