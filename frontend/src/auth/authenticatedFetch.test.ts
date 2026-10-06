import { afterEach, describe, expect, it, vi } from 'vitest'
import { authenticatedFetch, bindApiToken } from './authenticatedFetch'

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })
describe('silent API token renewal', () => {
  it('uses a freshly acquired token, without retrying a failed mutation', async () => {
    const resolve = vi.fn().mockResolvedValue('fresh-token')
    const release = bindApiToken('expired-anchor', resolve)
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 401 }))
    vi.stubGlobal('fetch', fetchMock)
    try {
      const response = await authenticatedFetch('/api/cart/items', 'expired-anchor', { method: 'POST', body: '{}' })
      expect(response.status).toBe(401)
      expect(fetchMock).toHaveBeenCalledOnce()
      expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe('Bearer fresh-token')
      expect(resolve).toHaveBeenCalledOnce()
    } finally { release() }
  })
  it('does not issue a write after logout during silent acquisition', async () => {
    let resolve!: (value: string) => void
    const release = bindApiToken('old-account', () => new Promise((done) => { resolve = done }))
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const pending = authenticatedFetch('/api/orders', 'old-account', { method: 'POST' })
    release()
    resolve('old-account-refreshed')
    await expect(pending).rejects.toMatchObject({ status: 401 })
    expect(fetchMock).not.toHaveBeenCalled()
  })
  it('an aborted caller can stop a hung token refresh before the network write', async () => {
    const release = bindApiToken('hung-account', () => new Promise(() => undefined))
    const controller = new AbortController()
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const pending = authenticatedFetch('/api/orders', 'hung-account', { method: 'POST', signal: controller.signal })
    controller.abort()
    await expect(pending).rejects.toMatchObject({ name: 'AbortError' })
    expect(fetchMock).not.toHaveBeenCalled()
    release()
  })
})
