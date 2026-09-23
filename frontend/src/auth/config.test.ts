import { describe, expect, it } from 'vitest'

import { createMsalConfig, loadAuthSettings } from './config'

const environment = {
  VITE_ENTRA_TENANT_SUBDOMAIN: 'PrepwiseCustomers',
  VITE_ENTRA_SPA_CLIENT_ID: 'spa-client-id',
  VITE_ENTRA_API_SCOPE: 'api://prepwise/access_as_user',
}

describe('Microsoft Entra frontend configuration', () => {
  it('uses the redirect bridge for login and the app root after logout', () => {
    const settings = loadAuthSettings(environment)
    const configuration = createMsalConfig(settings, 'http://localhost:3000')

    expect(settings.tenantSubdomain).toBe('prepwisecustomers')
    expect(configuration.auth).toMatchObject({
      authority: 'https://prepwisecustomers.ciamlogin.com/',
      clientId: 'spa-client-id',
      knownAuthorities: ['prepwisecustomers.ciamlogin.com'],
      redirectUri: 'http://localhost:3000/redirect.html',
      postLogoutRedirectUri: 'http://localhost:3000/',
    })
  })

  it('fails fast when required public configuration is missing', () => {
    expect(() =>
      loadAuthSettings({
        ...environment,
        VITE_ENTRA_API_SCOPE: '',
      }),
    ).toThrow('VITE_ENTRA_API_SCOPE')
  })
})
