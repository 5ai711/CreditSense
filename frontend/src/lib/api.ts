import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { useAuth } from '../store/auth'
import type { TokenResponse } from './types'

export const api = axios.create({ baseURL: '/api', timeout: 30_000 })

// One refresh at a time: concurrent 401s in this tab wait for the same rotation, and the Web Locks API
// serialises refreshes across tabs. Without it, two tabs rotating the same cookie at once would look
// like a stolen token to the server, which then ends every session of the user.
let refreshing: Promise<string | null> | null = null

function withRefreshLock<T>(fn: () => Promise<T>): Promise<T> {
  const locks = typeof navigator !== 'undefined' ? navigator.locks : undefined
  return locks ? locks.request('creditsense-refresh', fn) : fn()
}

async function refreshAccessToken(): Promise<string | null> {
  if (!useAuth.getState().user) return null
  try {
    // the HttpOnly refresh cookie is sent automatically (same origin, path /api/auth)
    const { data } = await withRefreshLock(() => axios.post<TokenResponse>('/api/auth/refresh'))
    useAuth.getState().setSession(data)
    return data.accessToken
  } catch {
    useAuth.getState().clear()
    return null
  }
}

function refreshOnce(): Promise<string | null> {
  refreshing ??= refreshAccessToken().finally(() => (refreshing = null))
  return refreshing
}

api.interceptors.request.use(async (config) => {
  let token = useAuth.getState().accessToken
  // after a reload the profile is known but the access token is not: restore it before the first call
  if (!token && useAuth.getState().user && !config.url?.startsWith('/auth/')) token = await refreshOnce()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined
    const isAuthCall = original?.url?.startsWith('/auth/')
    if (error.response?.status === 401 && original && !original._retried && !isAuthCall) {
      original._retried = true
      const token = await refreshOnce()
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
