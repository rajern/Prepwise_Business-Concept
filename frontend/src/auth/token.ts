import type {
  AccountInfo,
  IPublicClientApplication,
  RedirectRequest,
} from '@azure/msal-browser'

export function createLoginRequest(apiScope: string): RedirectRequest {
  return {
    scopes: [apiScope],
  }
}

export async function acquireApiAccessToken(
  instance: IPublicClientApplication,
  account: AccountInfo,
  apiScope: string,
): Promise<string> {
  const result = await instance.acquireTokenSilent({
    account,
    scopes: [apiScope],
  })

  if (!result.accessToken) {
    throw new Error('Microsoft Entra returned an empty API access token')
  }

  return result.accessToken
}
