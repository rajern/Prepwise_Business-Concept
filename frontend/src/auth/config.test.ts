import { describe, expect, it } from 'vitest'

import { createMsalConfig, loadAuthSettings } from './config'

const environment = {
  VITE_ENTRA_TENANT_ID: '1A782388-BF90-4EA8-AF8F-BCC755F5CD7E',
  VITE_ENTRA_TENANT_SUBDOMAIN: 'PrepwiseCustomers',
  VITE_ENTRA_SPA_CLIENT_ID: 'spa-client-id',
  VITE_ENTRA_API_SCOPE: 'api://prepwise/access_as_user',
}

describe('Microsoft Entra frontend configuration', () => {
  it('uses the redirect bridge for login and the app root after logout', () => {
    const settings = loadAuthSettings(environment)
    const configuration = createMsalConfig(settings, 'http://localhost:3000')

    expect(settings.tenantSubdomain).toBe('prepwisecustomers')
    expect(settings.tenantId).toBe('1a782388-bf90-4ea8-af8f-bcc755f5cd7e')
    expect(configuration.auth).toMatchObject({
      authority: 'https://prepwisecustomers.ciamlogin.com/',
      clientId: 'spa-client-id',
      knownAuthorities: [
        'prepwisecustomers.ciamlogin.com',
        '1a782388-bf90-4ea8-af8f-bcc755f5cd7e.ciamlogin.com',
      ],
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

  it('rejects a malformed External tenant ID', () => {
    expect(() =>
      loadAuthSettings({
        ...environment,
        VITE_ENTRA_TENANT_ID: 'not-a-tenant-id',
      }),
    ).toThrow('VITE_ENTRA_TENANT_ID')
  })
})
