export interface User {
  id: number
  username: string
  role: 'store' | 'co' | 'admin'
  restaurants: Restaurant[]
}

export interface Restaurant {
  id: number
  code: string
  name: string
  is_active?: boolean
  feat_invoices?: boolean
  feat_analytics?: boolean
  google_sheet_url?: string | null
}

export interface Report {
  id: number
  restaurant_id: number
  period: string
  period_type: string
  status: 'pending' | 'in_progress' | 'ready' | 'error'
  created_at: string
}

export interface WasteMetric {
  restaurant_id: number
  period: string
  waste_pct: number
  shortage_sum: number
  revenue_sum: number
  complete_waste_sum: number
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  role: string
  username: string
}
