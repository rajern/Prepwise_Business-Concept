import { apiUrl } from './config'
import { apiRequestError } from './errors'

export interface AdminPickupLocation {
  id: string
  name: string
  address_line: string
  postal_code: string
  city: string
  active: boolean
}

export interface AdminPickupLocationWrite {
  name: string
  address_line: string
  postal_code: string
  city: string
  active: boolean
}

export function fetchAdminPickupLocations(
  accessToken: string,
  signal?: AbortSignal,
): Promise<AdminPickupLocation[]> {
  return adminPickupRequest('/api/admin/pickup-locations', accessToken, {
    signal,
  })
}

export function createAdminPickupLocation(
  accessToken: string,
  payload: AdminPickupLocationWrite,
): Promise<AdminPickupLocation> {
  return adminPickupRequest('/api/admin/pickup-locations', accessToken, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateAdminPickupLocation(
  accessToken: string,
  locationId: string,
  payload: AdminPickupLocationWrite,
): Promise<AdminPickupLocation> {
  return adminPickupRequest(
    `/api/admin/pickup-locations/${locationId}`,
    accessToken,
    {
      method: 'PATCH',
      body: JSON.stringify(payload),
    },
  )
}

async function adminPickupRequest<T>(
  path: string,
  accessToken: string,
  init: RequestInit,
): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: {
      Accept: 'application/json',
      Authorization: `Bearer ${accessToken}`,
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
    },
  })
  if (!response.ok) {
    throw await apiRequestError(response)
  }
  return (await response.json()) as T
}
