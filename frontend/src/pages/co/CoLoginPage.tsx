import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import coApi from '../../api/coClient'
import { Loader2, Coffee } from 'lucide-react'

export default function CoLoginPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

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
      navigate(data.role === 'admin' ? '/admin' : '/invoices')
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Ошибка входа')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-brand-bg flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="card p-8 shadow-xl">
          <div className="flex flex-col items-center mb-8">
            <div className="w-12 h-12 bg-brand-yellow/20 rounded-xl flex items-center justify-center mb-3">
              <Coffee size={24} className="text-brand-dark" />
            </div>
            <h1 className="text-xl font-bold text-brand-dark">Coffee Original</h1>
            <p className="text-brand-muted text-sm mt-1">Управление складом</p>
          </div>

          <form onSubmit={submit} className="space-y-4">
            {error && (
              <div className="p-3 rounded-lg bg-red-50 border border-red-100 text-red-600 text-sm">
                {error}
              </div>
            )}
            <div>
              <label className="block text-sm font-medium text-brand-dark mb-1.5">Логин</label>
              <input
                type="text"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                className="input"
                placeholder="karina или karina@coffee.kz"
                autoComplete="username"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-brand-dark mb-1.5">Пароль</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                className="input"
              />
            </div>
            <button type="submit" disabled={loading} className="btn-primary w-full justify-center py-3">
              {loading && <Loader2 size={16} className="animate-spin" />}
              Войти
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
