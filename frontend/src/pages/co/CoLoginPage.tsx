import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import coApi from '../../api/coClient'
import { Loader2, Eye, EyeOff, CheckCircle2 } from 'lucide-react'

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
    <div className="min-h-screen flex flex-col lg:flex-row">

      {/* ── Left panel: Login form ── */}
      <div className="flex flex-col justify-center px-6 py-12 bg-white lg:w-[460px] xl:w-[500px] lg:min-h-screen">
        <div className="mx-auto w-full max-w-[340px]">

          {/* Logo */}
          <div className="mb-10">
            <img src="/brand/logo-light.svg" alt="RestOn" className="h-20 w-20" />
          </div>

          <h1 className="text-2xl font-bold text-brand-dark mb-1.5">Добро пожаловать</h1>
          <p className="text-brand-muted text-sm mb-8">Войдите в свой аккаунт для продолжения</p>

          <form onSubmit={submit} className="space-y-4">
            {error && (
              <div className="px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
                {error}
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-brand-dark mb-1.5">
                Email или логин
              </label>
              <input
                type="text"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                className="input"
                placeholder="user@coffee.kz"
                autoComplete="username"
                autoFocus
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-brand-dark mb-1.5">
                Пароль
              </label>
              <div className="relative">
                <input
                  type={showPass ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  className="input pr-10"
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPass(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-brand-muted hover:text-brand-dark transition-colors"
                  tabIndex={-1}
                >
                  {showPass ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-brand-green text-white font-semibold text-sm
                         hover:brightness-95 active:scale-[0.99] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading && <Loader2 size={16} className="animate-spin" />}
              Войти
            </button>

            {/* Разделитель */}
            <div style={{
              display: "flex", alignItems: "center",
              gap: "0.75rem", margin: "1rem 0"
            }}>
              <div style={{ flex: 1, height: 1, background: "#e2e6ea" }} />
              <span style={{ fontSize: 12, color: "#6B7C8D" }}>или</span>
              <div style={{ flex: 1, height: 1, background: "#e2e6ea" }} />
            </div>

            {/* Кнопка Google */}
            <a
              href="/api/auth/google/login"
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "0.625rem",
                width: "100%",
                padding: "10px",
                border: "0.5px solid #d1d9e0",
                borderRadius: 8,
                background: "#fff",
                color: "#0F2D3D",
                fontSize: 14,
                fontWeight: 500,
                textDecoration: "none",
                cursor: "pointer",
                fontFamily: "Inter, sans-serif"
              }}
            >
              <svg width="18" height="18" viewBox="0 0 18 18">
                <path fill="#4285F4" d="M16.51 8H8.98v3h4.3c-.18 1-.74 1.48-1.6 2.04v2.01h2.6a7.8 7.8 0 002.38-5.88c0-.57-.05-.66-.15-1.18z"/>
                <path fill="#34A853" d="M8.98 17c2.16 0 3.97-.72 5.3-1.94l-2.6-2a4.8 4.8 0 01-7.18-2.54H1.83v2.07A8 8 0 008.98 17z"/>
                <path fill="#FBBC05" d="M4.5 10.52a4.8 4.8 0 010-3.04V5.41H1.83a8 8 0 000 7.18l2.67-2.07z"/>
                <path fill="#EA4335" d="M8.98 4.18c1.17 0 2.23.4 3.06 1.2l2.3-2.3A8 8 0 001.83 5.4L4.5 7.49a4.77 4.77 0 014.48-3.31z"/>
              </svg>
              Войти через Google
            </a>
          </form>

          <div className="mt-6 text-center">
            <a
              href="mailto:support@reston.kz"
              className="text-sm text-brand-muted hover:text-brand-dark underline-offset-4 hover:underline transition-colors"
            >
              Запросить доступ
            </a>
          </div>
        </div>

        <div className="mt-auto pt-8 mx-auto w-full max-w-[340px]">
          <p className="text-xs text-brand-muted">© 2024 RestOn. Все права защищены.</p>
        </div>
      </div>

      {/* ── Right panel: Dark navy, operational preview ── */}
      <div className="hidden lg:flex flex-1 flex-col bg-[#0F2D3D] text-white p-12 relative overflow-hidden">
        {/* Decorative circles */}
        <div className="absolute -top-40 -right-40 w-96 h-96 rounded-full bg-white/[0.04] pointer-events-none" />
        <div className="absolute -bottom-32 -left-32 w-80 h-80 rounded-full bg-brand-green/[0.08] pointer-events-none" />
        <div className="absolute top-1/2 right-8 w-px h-64 bg-white/10 pointer-events-none -translate-y-1/2" />

        {/* Logo */}
        <div className="relative z-10">
          <img src="/brand/logo-dark.svg" alt="RestOn" className="h-16 w-16" />
        </div>

        {/* Main content */}
        <div className="relative z-10 flex-1 flex flex-col justify-center max-w-lg">
          <div className="mb-8">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-brand-green/20 border border-brand-green/30 mb-6">
              <div className="w-1.5 h-1.5 rounded-full bg-brand-green animate-pulse" />
              <span className="text-xs text-brand-green font-medium">Система работает в штатном режиме</span>
            </div>

            <h2 className="text-4xl font-bold leading-tight mb-4">
              Операционный контроль<br />
              <span className="text-brand-green">в реальном времени</span>
            </h2>
            <p className="text-white/55 text-base leading-relaxed">
              Автоматизированная система управления поставками для ресторанного бизнеса.
              OCR-распознавание накладных, синхронизация с iiko, полная прозрачность операций.
            </p>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-3 mb-8">
            {[
              { value: '17', label: 'ресторанов' },
              { value: '98.5%', label: 'точность OCR' },
              { value: '₸150М', label: 'обработано' },
            ].map(stat => (
              <div key={stat.label} className="bg-white/[0.06] rounded-xl p-4 border border-white/10">
                <div className="text-2xl font-bold text-white mb-0.5">{stat.value}</div>
                <div className="text-xs text-white/45">{stat.label}</div>
              </div>
            ))}
          </div>

          {/* Feature list */}
          <div className="space-y-2.5">
            {[
              'OCR-распознавание накладных с фото и PDF',
              'Автоматическая отправка в iiko',
              'Контроль по 17 ресторанам в реальном времени',
            ].map(f => (
              <div key={f} className="flex items-center gap-3">
                <CheckCircle2 size={15} className="text-brand-green shrink-0" />
                <span className="text-sm text-white/60">{f}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom workspace tag */}
        <div className="relative z-10">
          <div className="flex items-center gap-2 text-xs text-white/30">
            <span>Текущий workspace:</span>
            <span className="text-white/50 font-medium">Coffee Original</span>
          </div>
        </div>
      </div>
    </div>
  )
}
