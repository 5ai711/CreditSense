import axios, { type AxiosAdapter, type InternalAxiosRequestConfig } from 'axios'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { useAuth } from '../store/auth'
import { api } from './api'

const user = { id: 1, email: 'a@b.in', fullName: 'A', role: 'APPLICANT' as const }
const originalGlobal = axios.defaults.adapter
const originalApi = api.defaults.adapter

function reply(config: InternalAxiosRequestConfig, status: number, data: unknown) {
  const response = { data, status, statusText: String(status), headers: {}, config }
  if (status >= 400) {
    return Promise.reject(new axios.AxiosError('failed', String(status), config, null, response))
  }
  return Promise.resolve(response)
}

describe('session restore through the refresh cookie', () => {
  let refreshCalls = 0
  let refreshStatus = 200
  let seenBodies: unknown[] = []

  beforeEach(() => {
    refreshCalls = 0
    refreshStatus = 200
    seenBodies = []
    // a reload: the profile survived in storage, the access token did not
    useAuth.setState({ user, accessToken: null })
    axios.defaults.adapter = ((config) => {
      refreshCalls++
      seenBodies.push(config.data)
      return refreshStatus === 200
        ? reply(config, 200, { accessToken: 'fresh', tokenType: 'Bearer', expiresIn: 900, user })
        : reply(config, 401, { message: 'no session' })
    }) as AxiosAdapter
    api.defaults.adapter = ((config) =>
      config.headers.Authorization === 'Bearer fresh' ? reply(config, 200, { ok: true }) : reply(config, 401, {})
    ) as AxiosAdapter
  })

  afterEach(() => {
    axios.defaults.adapter = originalGlobal
    api.defaults.adapter = originalApi
  })

  it('restores the access token once for parallel requests, sending no token in the body', async () => {
    const results = await Promise.all([api.get('/a'), api.get('/b'), api.get('/c')])
    expect(results.map((r) => r.status)).toEqual([200, 200, 200])
    expect(refreshCalls).toBe(1)
    expect(seenBodies[0]).toBeUndefined() // the refresh token travels only as an HttpOnly cookie
    expect(useAuth.getState().accessToken).toBe('fresh')
  })

  it('signs the user out when the cookie is no longer valid', async () => {
    refreshStatus = 401
    await expect(api.get('/a')).rejects.toMatchObject({ response: { status: 401 } })
    expect(useAuth.getState().user).toBeNull()
  })

  it('never persists a token', () => {
    useAuth.getState().setSession({ accessToken: 'secret', tokenType: 'Bearer', expiresIn: 900, user })
    expect(window.localStorage.getItem('creditsense-session') ?? '').not.toContain('secret')
  })
})
