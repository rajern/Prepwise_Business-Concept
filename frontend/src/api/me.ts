import { apiUrl } from './config'

export interface CurrentUser {
  id: string
  email: string | null
  display_name: string | null
  role: 'customer' | 'admin'
}

export async function fetchCurrentUser(accessToken: string): Promise<CurrentUser> {
  const response = await fetch(apiUrl('/api/me'), {
    headers: {
      Accept: 'application/json',
      Authorization: `Bearer ${accessToken}`,
    },
  })

  if (!response.ok) {
    throw new Error(`Current-user request failed with status ${response.status}`)
  }

  return (await response.json()) as CurrentUser
}
