import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  initialize: vi.fn<() => Promise<void>>(),
  render: vi.fn(),
}))

vi.mock('@azure/msal-browser', () => ({
  PublicClientApplication: vi.fn(function PublicClientApplication() {
    return { initialize: mocks.initialize }
  }),
}))

vi.mock('@azure/msal-react', () => ({
  MsalProvider: ({ children }: { children: React.ReactNode }) => children,
}))

vi.mock('react-dom/client', () => ({
  createRoot: vi.fn(() => ({ render: mocks.render })),
}))

vi.mock('./auth/config', () => ({
  createMsalConfig: vi.fn(() => ({ auth: { clientId: 'spa-client-id' } })),
  loadAuthSettings: vi.fn(() => ({
    apiScope: 'api://prepwise/access_as_user',
    clientId: 'spa-client-id',
    tenantSubdomain: 'prepwisecustomers',
  })),
}))

describe('frontend bootstrap', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    document.body.innerHTML = '<div id="root"></div>'
  })

  it('waits for MSAL initialization before rendering the app', async () => {
    let finishInitialization: (() => void) | undefined
    mocks.initialize.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          finishInitialization = resolve
        }),
    )

    await import('./main')

    expect(mocks.initialize).toHaveBeenCalledOnce()
    expect(mocks.render).not.toHaveBeenCalled()

    finishInitialization?.()

    await vi.waitFor(() => {
      expect(mocks.render).toHaveBeenCalledOnce()
    })
  })
})
