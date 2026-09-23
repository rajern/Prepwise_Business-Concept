import { describe, expect, it, vi } from 'vitest'

const broadcastResponseToMainFrame = vi.hoisted(() =>
  vi.fn<() => Promise<void>>().mockResolvedValue(undefined),
)

vi.mock('@azure/msal-browser/redirect-bridge', () => ({
  broadcastResponseToMainFrame,
}))

describe('MSAL redirect bridge', () => {
  it('broadcasts the authorization response without rendering the app', async () => {
    await import('./redirect')

    expect(broadcastResponseToMainFrame).toHaveBeenCalledOnce()
  })
})
