import { apiUrl } from './config'
import { apiRequestError } from './errors'

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
    throw await apiRequestError(response)
  }

  return (await response.json()) as CurrentUser
}
