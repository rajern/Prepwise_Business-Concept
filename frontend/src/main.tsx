import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { PublicClientApplication } from '@azure/msal-browser'
import { MsalProvider } from '@azure/msal-react'
import { App } from './App'
import { createMsalConfig, loadAuthSettings } from './auth/config'
import type { CurrentUser } from './api/me'
import './styles.css'

const rootElement = document.getElementById('root')

if (!rootElement) {
  throw new Error('Root element was not found')
}

async function bootstrap(container: HTMLElement) {
  const authSettings = loadAuthSettings()
  const msalInstance = new PublicClientApplication(createMsalConfig(authSettings))
  const e2eSession = getE2ESession()

  await msalInstance.initialize()

  createRoot(container).render(
    <StrictMode>
      <MsalProvider instance={msalInstance}>
        <App
          apiScope={authSettings.apiScope}
          initialAccessToken={e2eSession?.accessToken}
          initialCurrentUser={e2eSession?.currentUser}
          isE2ESession={Boolean(e2eSession)}
        />
      </MsalProvider>
    </StrictMode>,
  )
}

function getE2ESession(): {
  accessToken: string
  currentUser: CurrentUser
} | null {
  if (import.meta.env.VITE_E2E_AUTH_ENABLED !== 'true') {
    return null
  }

  const role = new URLSearchParams(window.location.search).get('__e2e_role')
  if (role !== 'customer' && role !== 'admin') {
    throw new Error('The E2E test session requires a customer or admin role')
  }

  return {
    accessToken: `prepwise-e2e-${role}`,
    currentUser: {
      id: role === 'admin' ? '00000000-0000-0000-0000-000000000002' : '00000000-0000-0000-0000-000000000001',
      email: `${role}.e2e@example.invalid`,
      display_name: role === 'admin' ? 'E2E Admin' : 'E2E Customer',
      role,
    },
  }
}

void bootstrap(rootElement)
