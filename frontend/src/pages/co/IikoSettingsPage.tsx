import { useState } from "react"
import axios from "axios"

const api = axios.create({ baseURL: "/" })
api.interceptors.request.use(cfg => {
  const token = localStorage.getItem("co_access_token")
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

export default function IikoSettingsPage() {
  const [baseUrl, setBaseUrl] = useState("")
  const [login, setLogin] = useState("")
  const [password, setPassword] = useState("")
  const [testResult, setTestResult] = useState<null|boolean>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [saved, setSaved] = useState(false)

  const inputStyle = {
    width: "100%", padding: "10px 14px",
    border: "1px solid #d1d9e0", borderRadius: "8px",
    fontSize: "14px", background: "#F4F6F8",
    color: "#0F2D3D", outline: "none",
    fontFamily: "Inter, sans-serif",
    boxSizing: "border-box" as const
  }

  const testIiko = async () => {
    if (!baseUrl || !login || !password) {
      setError("Заполните все поля"); return
    }
    setLoading(true); setError(""); setTestResult(null)
    try {
      const r = await api.post("/api/onboarding/iiko/test", {
        name: "Основной сервер",
        base_url: baseUrl, login, password
      })
      setTestResult(r.data.ok)
      if (!r.data.ok) setError(r.data.message)
    } catch { setError("Ошибка проверки") }
    finally { setLoading(false) }
  }

  const saveIiko = async () => {
    setLoading(true); setError("")
    try {
      await api.post("/api/onboarding/iiko/save", {
        name: "Основной сервер",
        base_url: baseUrl, login, password
      })
      setSaved(true)
      window.location.reload()
    } catch { setError("Ошибка сохранения") }
    finally { setLoading(false) }
  }

  if (saved) return (
    <div style={{ padding: "2rem", textAlign: "center" }}>
      <div style={{ fontSize: "48px" }}>✅</div>
      <h2 style={{ color: "#0F2D3D", marginTop: "1rem" }}>
        iiko подключён!</h2>
    </div>
  )

  return (
    <div style={{ padding: "2rem", maxWidth: "480px" }}>
      <h1 style={{
        fontSize: "20px", fontWeight: 600,
        color: "#0F2D3D", marginBottom: "8px"
      }}>Подключение iiko</h1>
      <p style={{
        fontSize: "14px", color: "#6B7C8D", marginBottom: "2rem"
      }}>
        Создайте отдельного пользователя в iiko с правами
        бухгалтера и введите данные ниже.
      </p>

      <div style={{ marginBottom: "1rem" }}>
        <label style={{
          display: "block", fontSize: "13px",
          fontWeight: 500, color: "#0F2D3D", marginBottom: "6px"
        }}>Адрес сервера iiko</label>
        <input style={inputStyle}
          placeholder="https://xxx.iiko.it"
          value={baseUrl}
          onChange={e => { setBaseUrl(e.target.value); setTestResult(null) }} />
      </div>

      <div style={{ marginBottom: "1rem" }}>
        <label style={{
          display: "block", fontSize: "13px",
          fontWeight: 500, color: "#0F2D3D", marginBottom: "6px"
        }}>Логин</label>
        <input style={inputStyle} placeholder="бухгалтер"
          value={login}
          onChange={e => { setLogin(e.target.value); setTestResult(null) }} />
      </div>

      <div style={{ marginBottom: "1.5rem" }}>
        <label style={{
          display: "block", fontSize: "13px",
          fontWeight: 500, color: "#0F2D3D", marginBottom: "6px"
        }}>Пароль</label>
        <input style={inputStyle} type="password"
          placeholder="••••••••"
          value={password}
          onChange={e => { setPassword(e.target.value); setTestResult(null) }} />
      </div>

      {testResult === true && (
        <div style={{
          background: "#E0F5EE", color: "#0D9373",
          padding: "10px 14px", borderRadius: "8px",
          fontSize: "13px", marginBottom: "1rem"
        }}>✓ Подключение успешно!</div>
      )}

      {error && (
        <div style={{
          background: "#FCEBEB", color: "#E24B4A",
          padding: "10px 14px", borderRadius: "8px",
          fontSize: "13px", marginBottom: "1rem"
        }}>{error}</div>
      )}

      <div style={{ display: "flex", gap: "8px" }}>
        <button onClick={testIiko} disabled={loading} style={{
          flex: 1, padding: "12px",
          background: "#fff", color: "#0F2D3D",
          border: "1px solid #d1d9e0", borderRadius: "8px",
          fontSize: "14px", fontWeight: 500, cursor: "pointer",
          fontFamily: "Inter, sans-serif"
        }}>
          {loading ? "Проверяем..." : "Проверить"}
        </button>
        <button
          onClick={saveIiko}
          disabled={loading || testResult !== true}
          style={{
            flex: 1, padding: "12px",
            background: "#0D9373", color: "#fff",
            border: "none", borderRadius: "8px",
            fontSize: "14px", fontWeight: 500,
            cursor: (loading || testResult !== true)
              ? "not-allowed" : "pointer",
            opacity: (loading || testResult !== true) ? 0.5 : 1,
            fontFamily: "Inter, sans-serif"
          }}>
          {loading ? "Сохраняем..." : "Подключить"}
        </button>
      </div>
    </div>
  )
}
