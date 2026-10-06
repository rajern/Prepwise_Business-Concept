import { apiUrl } from './config'
import { apiRequestError } from './errors'
import { authenticatedFetch } from '../auth/authenticatedFetch'

export interface CurrentUser {
  id: string
  email: string | null
  display_name: string | null
  role: 'customer' | 'admin'
}

export async function fetchCurrentUser(accessToken: string): Promise<CurrentUser> {
  const response = await authenticatedFetch(apiUrl('/api/me'), accessToken, {
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
