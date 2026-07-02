import { useState } from "react"
import { useNavigate } from "react-router-dom"
import axios from "axios"

const STEPS = ["Компания", "iiko", "Готово"]

const api = axios.create({ baseURL: "/" })
api.interceptors.request.use(cfg => {
  const token = localStorage.getItem("co_access_token")
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

export default function Onboarding() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  // Шаг 1
  const [companyName, setCompanyName] = useState("")
  const [phone, setPhone] = useState("")
  const [tenantType, setTenantType] = useState("freelancer")

  // Шаг 2
  const [serverName, setServerName] = useState("Основной сервер")
  const [baseUrl, setBaseUrl] = useState("")
  const [iikoLogin, setIikoLogin] = useState("")
  const [iikoPassword, setIikoPassword] = useState("")
  const [testResult, setTestResult] = useState<null|boolean>(null)

  const saveCompany = async () => {
    if (!companyName || !phone) {
      setError("Заполните все поля"); return
    }
    setLoading(true); setError("")
    try {
      await api.post("/api/onboarding/company", {
        company_name: companyName,
        phone,
        tenant_type: tenantType
      })
      setStep(1)
    } catch { setError("Ошибка сохранения") }
    finally { setLoading(false) }
  }

  const testIiko = async () => {
    if (!baseUrl || !iikoLogin || !iikoPassword) {
      setError("Заполните все поля iiko"); return
    }
    setLoading(true); setError("")
    try {
      const r = await api.post("/api/onboarding/iiko/test", {
        name: serverName, base_url: baseUrl,
        login: iikoLogin, password: iikoPassword
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
        name: serverName, base_url: baseUrl,
        login: iikoLogin, password: iikoPassword
      })
      await api.post("/api/onboarding/complete")
      setStep(2)
    } catch { setError("Ошибка сохранения") }
    finally { setLoading(false) }
  }

  const skipIiko = async () => {
    setLoading(true)
    try {
      await api.post("/api/onboarding/complete")
      setStep(2)
    } catch { setError("Ошибка") }
    finally { setLoading(false) }
  }

  const inputStyle: React.CSSProperties = {
    width: "100%", padding: "10px 14px",
    border: "1px solid #d1d9e0", borderRadius: "8px",
    fontSize: "14px", fontFamily: "Inter, sans-serif",
    outline: "none", background: "#F4F6F8", color: "#0F2D3D",
    boxSizing: "border-box"
  }
  const labelStyle: React.CSSProperties = {
    display: "block", fontSize: "13px", fontWeight: 500,
    color: "#0F2D3D", marginBottom: "6px"
  }
  const btnStyle: React.CSSProperties = {
    width: "100%", padding: "12px",
    background: "#0D9373", color: "#fff",
    border: "none", borderRadius: "8px",
    fontSize: "15px", fontWeight: 500,
    cursor: loading ? "not-allowed" : "pointer",
    opacity: loading ? 0.7 : 1,
    fontFamily: "Inter, sans-serif"
  }

  return (
    <div style={{
      minHeight: "100vh", background: "#F4F6F8",
      display: "flex", alignItems: "center",
      justifyContent: "center", padding: "2rem",
      fontFamily: "Inter, sans-serif"
    }}>
      <div style={{
        background: "#fff", borderRadius: "16px",
        border: "1px solid #e2e6ea",
        padding: "2rem", width: "100%", maxWidth: "460px"
      }}>
        {/* Лого */}
        <div style={{ textAlign: "center", marginBottom: "1.5rem" }}>
          <div style={{
            fontSize: "22px", fontWeight: 700, color: "#0F2D3D"
          }}>
            Rest<span style={{ color: "#0D9373" }}>On</span>
          </div>
        </div>

        {/* Прогресс */}
        <div style={{
          display: "flex", gap: "8px", marginBottom: "2rem"
        }}>
          {STEPS.map((s, i) => (
            <div key={i} style={{ flex: 1, textAlign: "center" }}>
              <div style={{
                height: "4px", borderRadius: "2px", marginBottom: "6px",
                background: i <= step ? "#0D9373" : "#e2e6ea"
              }} />
              <span style={{
                fontSize: "12px",
                color: i <= step ? "#0D9373" : "#6B7C8D",
                fontWeight: i === step ? 600 : 400
              }}>{s}</span>
            </div>
          ))}
        </div>

        {/* Шаг 1 — Компания */}
        {step === 0 && (
          <div>
            <h2 style={{
              fontSize: "18px", fontWeight: 600,
              color: "#0F2D3D", marginBottom: "4px"
            }}>Данные компании</h2>
            <p style={{
              fontSize: "13px", color: "#6B7C8D", marginBottom: "1.5rem"
            }}>Расскажите о вашем бизнесе</p>

            <div style={{ marginBottom: "1rem" }}>
              <label style={labelStyle}>Название компании</label>
              <input style={inputStyle} placeholder="ТОО Ромашка"
                value={companyName}
                onChange={e => setCompanyName(e.target.value)} />
            </div>

            <div style={{ marginBottom: "1rem" }}>
              <label style={labelStyle}>WhatsApp / телефон</label>
              <input style={inputStyle} placeholder="+7 700 000 0000"
                value={phone}
                onChange={e => setPhone(e.target.value)} />
            </div>

            <div style={{ marginBottom: "1.5rem" }}>
              <label style={labelStyle}>Тип бизнеса</label>
              <div style={{ display: "flex", gap: "8px" }}>
                {[
                  { v: "freelancer", l: "Фрилансер-бухгалтер" },
                  { v: "chain", l: "Ресторанная сеть" }
                ].map(opt => (
                  <button key={opt.v}
                    onClick={() => setTenantType(opt.v)}
                    style={{
                      flex: 1, padding: "10px 8px",
                      borderRadius: "8px", fontSize: "13px",
                      cursor: "pointer", fontFamily: "Inter, sans-serif",
                      border: tenantType === opt.v
                        ? "2px solid #0D9373" : "1px solid #d1d9e0",
                      background: tenantType === opt.v
                        ? "#E0F5EE" : "#fff",
                      color: tenantType === opt.v
                        ? "#0D9373" : "#0F2D3D",
                      fontWeight: tenantType === opt.v ? 600 : 400
                    }}>{opt.l}</button>
                ))}
              </div>
            </div>

            {error && <p style={{
              color: "#E24B4A", fontSize: "13px", marginBottom: "1rem"
            }}>{error}</p>}
            <button style={btnStyle} onClick={saveCompany}
              disabled={loading}>
              {loading ? "Сохраняем..." : "Далее →"}
            </button>
          </div>
        )}

        {/* Шаг 2 — iiko */}
        {step === 1 && (
          <div>
            <h2 style={{
              fontSize: "18px", fontWeight: 600,
              color: "#0F2D3D", marginBottom: "4px"
            }}>Подключение iiko</h2>
            <p style={{
              fontSize: "13px", color: "#6B7C8D", marginBottom: "1.5rem"
            }}>Создайте отдельного пользователя в iiko с правами
              бухгалтера и введите его данные</p>

            <div style={{ marginBottom: "1rem" }}>
              <label style={labelStyle}>Адрес сервера iiko</label>
              <input style={inputStyle}
                placeholder="https://xxx.iiko.it"
                value={baseUrl}
                onChange={e => {
                  setBaseUrl(e.target.value)
                  setTestResult(null)
                }} />
            </div>

            <div style={{ marginBottom: "1rem" }}>
              <label style={labelStyle}>Логин</label>
              <input style={inputStyle} placeholder="бухгалтер"
                value={iikoLogin}
                onChange={e => {
                  setIikoLogin(e.target.value)
                  setTestResult(null)
                }} />
            </div>

            <div style={{ marginBottom: "1.5rem" }}>
              <label style={labelStyle}>Пароль</label>
              <input style={inputStyle} type="password"
                placeholder="••••••••"
                value={iikoPassword}
                onChange={e => {
                  setIikoPassword(e.target.value)
                  setTestResult(null)
                }} />
            </div>

            {testResult === true && (
              <div style={{
                background: "#E0F5EE", color: "#0D9373",
                padding: "10px 14px", borderRadius: "8px",
                fontSize: "13px", marginBottom: "1rem"
              }}>✓ Подключение успешно!</div>
            )}
            {testResult === false && (
              <div style={{
                background: "#FCEBEB", color: "#E24B4A",
                padding: "10px 14px", borderRadius: "8px",
                fontSize: "13px", marginBottom: "1rem"
              }}>{error || "Ошибка подключения"}</div>
            )}

            {error && testResult === null && (
              <p style={{
                color: "#E24B4A", fontSize: "13px",
                marginBottom: "1rem"
              }}>{error}</p>
            )}

            <div style={{ display: "flex", gap: "8px" }}>
              <button
                onClick={testIiko}
                disabled={loading}
                style={{
                  flex: 1, padding: "12px",
                  background: "#fff", color: "#0F2D3D",
                  border: "1px solid #d1d9e0", borderRadius: "8px",
                  fontSize: "14px", fontWeight: 500,
                  cursor: loading ? "not-allowed" : "pointer",
                  fontFamily: "Inter, sans-serif"
                }}>
                {loading ? "Проверяем..." : "Проверить"}
              </button>
              <button
                onClick={saveIiko}
                disabled={loading || testResult !== true}
                style={{
                  ...btnStyle,
                  flex: 1, width: "auto",
                  opacity: (loading || testResult !== true) ? 0.5 : 1,
                  cursor: (loading || testResult !== true)
                    ? "not-allowed" : "pointer"
                }}>
                {loading ? "Сохраняем..." : "Сохранить →"}
              </button>
            </div>

            <button
              onClick={skipIiko}
              style={{
                width: "100%", marginTop: "8px",
                padding: "8px", background: "none",
                border: "none", color: "#6B7C8D",
                fontSize: "13px", cursor: "pointer",
                fontFamily: "Inter, sans-serif"
              }}>
              Пропустить, подключу позже
            </button>
          </div>
        )}

        {/* Шаг 3 — Готово */}
        {step === 2 && (
          <div style={{ textAlign: "center" }}>
            <div style={{
              fontSize: "48px", marginBottom: "1rem"
            }}>🎉</div>
            <h2 style={{
              fontSize: "20px", fontWeight: 600,
              color: "#0F2D3D", marginBottom: "8px"
            }}>Всё готово!</h2>
            <p style={{
              fontSize: "14px", color: "#6B7C8D",
              marginBottom: "1.5rem", lineHeight: 1.6
            }}>
              Ваш аккаунт настроен.<br />
              Пробный период: <strong style={{ color: "#0D9373" }}>
                14 дней</strong> бесплатно.
            </p>
            <div style={{
              background: "#E0F5EE", borderRadius: "10px",
              padding: "1rem", marginBottom: "1.5rem",
              textAlign: "left"
            }}>
              <p style={{
                fontSize: "13px", color: "#0D9373",
                fontWeight: 600, marginBottom: "4px"
              }}>Что дальше?</p>
              <p style={{
                fontSize: "13px", color: "#0F2D3D", lineHeight: 1.6
              }}>
                Загрузите первую накладную и убедитесь что всё
                работает. После триала мы свяжемся с вами.
              </p>
            </div>
            <button style={btnStyle}
              onClick={() => navigate("/invoices", { replace: true })}>
              Начать работу →
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
