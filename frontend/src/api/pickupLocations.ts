import { apiUrl } from './config'
import { apiRequestError } from './errors'

export interface PickupLocation {
  id: string
  name: string
  address_line: string
  postal_code: string
  city: string
}

export async function fetchPickupLocations(
  signal?: AbortSignal,
): Promise<PickupLocation[]> {
  const response = await fetch(apiUrl('/api/pickup-locations'), {
    signal,
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    throw await apiRequestError(response)
  }
  return (await response.json()) as PickupLocation[]
}
