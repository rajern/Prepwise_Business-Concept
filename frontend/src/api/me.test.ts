import { afterEach, describe, expect, it, vi } from 'vitest'

import { fetchCurrentUser } from './me'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('fetchCurrentUser', () => {
  it('sends the Entra access token as a bearer token', async () => {
    const user = {
      id: 'local-user-id',
      email: 'customer@example.com',
      display_name: 'Prepwise Customer',
      role: 'customer',
    }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => user,
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchCurrentUser('access-token')).resolves.toEqual(user)
    expect(fetchMock).toHaveBeenCalledWith('/api/me', {
      headers: {
        Accept: 'application/json',
        Authorization: 'Bearer access-token',
      },
    })
  })
})
