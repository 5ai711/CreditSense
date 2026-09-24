import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import type { TokenResponse, User } from '../lib/types'

const SESSION_KEY = 'creditsense-session'

interface AuthState {
  accessToken: string | null
  user: User | null
  setSession: (t: TokenResponse) => void
  clear: () => void
}

/**
 * Session store. The access token lives in memory only; after a reload it is restored from the HttpOnly
 * refresh cookie (see lib/api.ts). Only the signed-in user's profile is kept in localStorage, so the
 * right screens render at once; it falls back to memory when storage is blocked.
 */
export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      user: null,
      setSession: (t) => set({ accessToken: t.accessToken, user: t.user }),
      clear: () => set({ accessToken: null, user: null }),
    }),
    {
      name: SESSION_KEY,
      version: 2, // v1 stored tokens; they are dropped on upgrade
      migrate: (persisted) => ({ user: (persisted as { user?: User | null } | undefined)?.user ?? null }),
      partialize: (s) => ({ user: s.user }),
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

/**
 * Keep tabs consistent. When another tab signs out or signs in as someone else, follow it and drop this tab's
 * in-memory access token, which belongs to the previous user; the next request restores the right session
 * from the shared cookie.
 */
export function followOtherTabs(target: Pick<Window, 'addEventListener'> = window) {
  target.addEventListener('storage', (e) => {
    if (e.key !== null && e.key !== SESSION_KEY) return
    let next: User | null = null
    try {
      next = (JSON.parse(e.newValue ?? 'null') as { state?: { user?: User | null } } | null)?.state?.user ?? null
    } catch {
      next = null
    }
    if (next?.id !== useAuth.getState().user?.id) useAuth.setState({ user: next, accessToken: null })
  })
}

export const homeFor = (role: User['role'] | undefined) =>
  role === 'ADMIN' ? '/admin/portfolio' : role === 'LOAN_OFFICER' ? '/officer/queue' : '/applicant/dashboard'
