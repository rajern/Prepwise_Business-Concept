import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { PublicClientApplication } from '@azure/msal-browser'
import { MsalProvider } from '@azure/msal-react'
import { App } from './App'
import { createMsalConfig, loadAuthSettings } from './auth/config'
import './styles.css'

const rootElement = document.getElementById('root')

if (!rootElement) {
  throw new Error('Root element was not found')
}

async function bootstrap(container: HTMLElement) {
  const authSettings = loadAuthSettings()
  const msalInstance = new PublicClientApplication(createMsalConfig(authSettings))

  await msalInstance.initialize()

  createRoot(container).render(
    <StrictMode>
      <MsalProvider instance={msalInstance}>
        <App apiScope={authSettings.apiScope} />
      </MsalProvider>
    </StrictMode>,
  )
}

void bootstrap(rootElement)
