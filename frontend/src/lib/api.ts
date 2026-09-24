import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { useAuth } from '../store/auth'
import type { TokenResponse } from './types'

export const api = axios.create({ baseURL: '/api', timeout: 30_000 })

api.interceptors.request.use((config) => {
  const token = useAuth.getState().accessToken
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// One refresh at a time: concurrent 401s wait for the same rotation.
let refreshing: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  const { refreshToken, setSession, clear } = useAuth.getState()
  if (!refreshToken) return null
  try {
    const { data } = await axios.post<TokenResponse>('/api/auth/refresh', { refreshToken })
    setSession(data)
    return data.accessToken
  } catch {
    clear()
    return null
  }
}

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined
    const isAuthCall = original?.url?.startsWith('/auth/')
    if (error.response?.status === 401 && original && !original._retried && !isAuthCall) {
      original._retried = true
      refreshing ??= refreshAccessToken().finally(() => (refreshing = null))
      const token = await refreshing
      if (token) {
        original.headers.Authorization = `Bearer ${token}`
        return api(original)
      }
    }
    return Promise.reject(error)
  },
)

export interface ApiError {
  status?: number
  message: string
  fieldErrors?: { field: string; message: string }[]
}

export function toApiError(e: unknown): ApiError {
  if (axios.isAxiosError(e)) {
    const body = e.response?.data as { message?: string; fieldErrors?: ApiError['fieldErrors'] } | undefined
    return {
      status: e.response?.status,
      message: body?.message ?? (e.response ? `Request failed (${e.response.status})` : 'The server could not be reached'),
      fieldErrors: body?.fieldErrors,
    }
  }
  return { message: e instanceof Error ? e.message : 'Unexpected error' }
}
