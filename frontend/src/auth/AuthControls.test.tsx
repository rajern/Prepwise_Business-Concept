import '@testing-library/jest-dom/vitest'
import {
  type AccountInfo,
  type IPublicClientApplication,
  InteractionStatus,
  Logger,
} from '@azure/msal-browser'
import { useIsAuthenticated, useMsal } from '@azure/msal-react'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AuthControls } from './AuthControls'

const fetchCurrentUser = vi.hoisted(() =>
  vi.fn().mockResolvedValue({
    id: 'local-user-id',
    email: 'customer@example.com',
    display_name: 'Prepwise Customer',
    role: 'customer',
  }),
)

vi.mock('../api/me', () => ({ fetchCurrentUser }))

vi.mock('@azure/msal-react', () => ({
  useIsAuthenticated: vi.fn(),
  useMsal: vi.fn(),
}))

const apiScope = 'api://prepwise/access_as_user'
const account = {
  homeAccountId: 'home-account-id',
  environment: 'prepwisecustomers.ciamlogin.com',
  tenantId: 'tenant-id',
  username: 'customer@example.com',
  localAccountId: 'local-account-id',
  name: 'Prepwise Customer',
} as AccountInfo

const useIsAuthenticatedMock = vi.mocked(useIsAuthenticated)
const useMsalMock = vi.mocked(useMsal)

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  fetchCurrentUser.mockResolvedValue({
    id: 'local-user-id',
    email: 'customer@example.com',
    display_name: 'Prepwise Customer',
    role: 'customer',
  })
})

function configureMsalContext(isAuthenticated: boolean) {
  const loginRedirect = vi.fn().mockResolvedValue(undefined)
  const logoutRedirect = vi.fn().mockResolvedValue(undefined)
  const acquireTokenRedirect = vi.fn().mockResolvedValue(undefined)
  const acquireTokenSilent = vi.fn().mockResolvedValue({
    accessToken: 'not-a-real-token',
  })
  const instance = {
    acquireTokenRedirect,
    acquireTokenSilent,
    getActiveAccount: vi.fn(() => (isAuthenticated ? account : null)),
    loginRedirect,
    logoutRedirect,
  } as unknown as IPublicClientApplication

  useIsAuthenticatedMock.mockReturnValue(isAuthenticated)
  useMsalMock.mockReturnValue({
    accounts: isAuthenticated ? [account] : [],
    inProgress: InteractionStatus.None,
    instance,
    logger: new Logger({}),
  })

  return {
    acquireTokenSilent,
    loginRedirect,
    logoutRedirect,
  }
}

describe('AuthControls', () => {
  it('starts the combined sign-in and sign-up flow with the API scope', () => {
    const { loginRedirect } = configureMsalContext(false)

    render(<AuthControls apiScope={apiScope} />)
    fireEvent.click(
      screen.getByRole('button', { name: 'Sign in or create account' }),
    )

    expect(loginRedirect).toHaveBeenCalledWith({ scopes: [apiScope] })
  })

  it('acquires API access silently and signs the current account out', async () => {
    const { acquireTokenSilent, logoutRedirect } = configureMsalContext(true)

    render(<AuthControls apiScope={apiScope} />)

    expect(
      await screen.findByText('Signed in · API access ready'),
    ).toBeInTheDocument()
    expect(acquireTokenSilent).toHaveBeenCalledWith({
      account,
      scopes: [apiScope],
    })
    expect(fetchCurrentUser).toHaveBeenCalledWith('not-a-real-token')

    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }))

    await waitFor(() => {
      expect(logoutRedirect).toHaveBeenCalledWith({
        account,
        postLogoutRedirectUri: 'http://localhost:3000/',
      })
    })
  })
})
