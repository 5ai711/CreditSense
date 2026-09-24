import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import type { TokenResponse, User } from '../lib/types'

interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  user: User | null
  setSession: (t: TokenResponse) => void
  clear: () => void
}

/** Session store. Survives reloads via localStorage; falls back to memory when storage is blocked. */
export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      setSession: (t) => set({ accessToken: t.accessToken, refreshToken: t.refreshToken, user: t.user }),
      clear: () => set({ accessToken: null, refreshToken: null, user: null }),
    }),
    {
      name: 'creditsense-session',
      storage: createJSONStorage(() => {
        try {
          const probe = '__cs_probe__'
          window.localStorage.setItem(probe, probe)
          window.localStorage.removeItem(probe)
          return window.localStorage
        } catch {
          const mem = new Map<string, string>()
          return {
            getItem: (k: string) => mem.get(k) ?? null,
            setItem: (k: string, v: string) => void mem.set(k, v),
            removeItem: (k: string) => void mem.delete(k),
          }
        }
      }),
    },
  ),
)

export const homeFor = (role: User['role'] | undefined) =>
  role === 'ADMIN' ? '/admin/portfolio' : role === 'LOAN_OFFICER' ? '/officer/queue' : '/applicant/dashboard'
