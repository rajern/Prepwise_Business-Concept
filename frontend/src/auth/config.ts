import {
  BrowserCacheLocation,
  type Configuration,
} from '@azure/msal-browser'

interface AuthEnvironment {
  VITE_ENTRA_TENANT_ID?: string
  VITE_ENTRA_TENANT_SUBDOMAIN?: string
  VITE_ENTRA_SPA_CLIENT_ID?: string
  VITE_ENTRA_API_SCOPE?: string
}

export interface AuthSettings {
  tenantId: string
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
  const tenantId = requireValue(
    'VITE_ENTRA_TENANT_ID',
    environment.VITE_ENTRA_TENANT_ID,
  ).toLowerCase()
  const tenantSubdomain = requireValue(
    'VITE_ENTRA_TENANT_SUBDOMAIN',
    environment.VITE_ENTRA_TENANT_SUBDOMAIN,
  ).toLowerCase()

  if (!/^[a-z0-9-]+$/.test(tenantSubdomain)) {
    throw new Error('VITE_ENTRA_TENANT_SUBDOMAIN has an invalid format')
  }

  if (
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(
      tenantId,
    )
  ) {
    throw new Error('VITE_ENTRA_TENANT_ID has an invalid format')
  }

  return {
    tenantId,
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
  const issuerHost = `${settings.tenantId}.ciamlogin.com`
  const applicationRootUri = new URL('/', appOrigin).toString()
  const redirectUri = new URL('/redirect.html', appOrigin).toString()

  return {
    auth: {
      clientId: settings.clientId,
      authority: `https://${authorityHost}/`,
      knownAuthorities: [authorityHost, issuerHost],
      redirectUri,
      postLogoutRedirectUri: applicationRootUri,
    },
    cache: {
      cacheLocation: BrowserCacheLocation.SessionStorage,
    },
  }
}
