import axios from 'axios'

const coApi = axios.create({
  baseURL: '/api/co',
  headers: { 'Content-Type': 'application/json' },
})

coApi.interceptors.request.use((config) => {
  const token = localStorage.getItem('co_access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

coApi.interceptors.response.use(
  (res) => res,
  async (error) => {
    if (error.response?.status === 401 && !error.config.url?.includes('/auth/login')) {
      const refresh = localStorage.getItem('co_refresh_token')
      if (refresh) {
        try {
          const { data } = await axios.post('/api/co/auth/refresh', { refresh_token: refresh })
          localStorage.setItem('co_access_token', data.access_token)
          localStorage.setItem('co_refresh_token', data.refresh_token)
          error.config.headers.Authorization = `Bearer ${data.access_token}`
          return coApi.request(error.config)
        } catch {
          localStorage.removeItem('co_access_token')
          localStorage.removeItem('co_refresh_token')
          window.location.href = '/login'
        }
      } else {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default coApi
