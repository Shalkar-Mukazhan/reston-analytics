import { useState, FormEvent } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "../hooks/useAuth"
import { Loader2 } from "lucide-react"

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError("")
    setLoading(true)
    try {
      await login(username, password)
      navigate("/dashboard")
    } catch {
      setError("Неверный логин или пароль")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-brand-bg flex items-center justify-center px-4">
      {/* Background decoration */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-brand-yellow/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-brand-yellow/5 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-sm">
        {/* Card */}
        <div className="card p-8 shadow-xl">
          {/* Logo */}
          <div className="flex flex-col items-center mb-8">
            <img src="/forwhite.png" alt="Reston Analytics" className="h-16 w-auto mb-4" />
            <h1 className="text-2xl font-bold text-brand-dark">Reston Analytics</h1>
            <p className="text-brand-muted text-sm mt-1">Аналитика и контроль ресторанов</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-brand-dark mb-1.5">
                Логин
              </label>
              <input
                className="input"
                placeholder="Введите логин"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-brand-dark mb-1.5">
                Пароль
              </label>
              <input
                className="input"
                type="password"
                placeholder="Введите пароль"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            {error && (
              <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50 border border-red-100">
                <span className="text-brand-red text-sm">{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full justify-center py-3 text-base mt-2"
            >
              {loading ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Вход...
                </>
              ) : (
                "Войти"
              )}
            </button>
          </form>
        </div>

        <p className="text-center text-brand-muted text-xs mt-6">
          © 2026 Reston Analytics
        </p>
      </div>
    </div>
  )
}
