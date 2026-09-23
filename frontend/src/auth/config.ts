import {
  BrowserCacheLocation,
  type Configuration,
} from '@azure/msal-browser'

interface AuthEnvironment {
  VITE_ENTRA_TENANT_SUBDOMAIN?: string
  VITE_ENTRA_SPA_CLIENT_ID?: string
  VITE_ENTRA_API_SCOPE?: string
}

export interface AuthSettings {
  tenantSubdomain: string
  clientId: string
  apiScope: string
}

function requireValue(name: keyof AuthEnvironment, value: string | undefined) {
  const trimmedValue = value?.trim()

  if (!trimmedValue) {
    throw new Error(`Missing required frontend environment variable: ${name}`)
  }

  return trimmedValue
}

export function loadAuthSettings(
  environment: AuthEnvironment = import.meta.env,
): AuthSettings {
  const tenantSubdomain = requireValue(
    'VITE_ENTRA_TENANT_SUBDOMAIN',
    environment.VITE_ENTRA_TENANT_SUBDOMAIN,
  ).toLowerCase()

  if (!/^[a-z0-9-]+$/.test(tenantSubdomain)) {
    throw new Error('VITE_ENTRA_TENANT_SUBDOMAIN has an invalid format')
  }

  return {
    tenantSubdomain,
    clientId: requireValue(
      'VITE_ENTRA_SPA_CLIENT_ID',
      environment.VITE_ENTRA_SPA_CLIENT_ID,
    ),
    apiScope: requireValue(
      'VITE_ENTRA_API_SCOPE',
      environment.VITE_ENTRA_API_SCOPE,
    ),
  }
}

export function createMsalConfig(
  settings: AuthSettings,
  appOrigin: string = window.location.origin,
): Configuration {
  const authorityHost = `${settings.tenantSubdomain}.ciamlogin.com`
  const applicationRootUri = new URL('/', appOrigin).toString()
  const redirectUri = new URL('/redirect.html', appOrigin).toString()

  return {
    auth: {
      clientId: settings.clientId,
      authority: `https://${authorityHost}/`,
      knownAuthorities: [authorityHost],
      redirectUri,
      postLogoutRedirectUri: applicationRootUri,
    },
    cache: {
      cacheLocation: BrowserCacheLocation.SessionStorage,
    },
  }
}
