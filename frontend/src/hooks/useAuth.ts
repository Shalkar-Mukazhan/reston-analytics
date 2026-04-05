import { useState, useEffect, useContext, createContext, createElement } from 'react'
import type { ReactNode } from 'react'
import api from '../api/client'
import type { User } from '../types'

interface AuthContextType {
  user: User | null
  loading: boolean
  login: (username: string, password: string) => Promise<User>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) { setLoading(false); return }

    api.get('/auth/me')
      .then((res) => setUser(res.data))
      .catch(() => { localStorage.clear(); setUser(null) })
      .finally(() => setLoading(false))
  }, [])

  const login = async (username: string, password: string): Promise<User> => {
    const form = new URLSearchParams()
    form.append('username', username)
    form.append('password', password)
    const { data } = await api.post('/auth/login', form.toString(), {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    const me = await api.get('/auth/me')
    setUser(me.data)
    return me.data as User
  }

  const logout = () => {
    localStorage.clear()
    setUser(null)
  }

  return createElement(AuthContext.Provider, { value: { user, loading, login, logout } }, children)
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be inside AuthProvider')
  return ctx
}
