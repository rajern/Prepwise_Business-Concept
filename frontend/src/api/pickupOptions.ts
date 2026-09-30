import { apiUrl } from './config'
import { apiRequestError } from './errors'

export interface PickupSlot { id: '16-18' | '18-20'; start_at: string; end_at: string }
export interface PickupDay { date: string; slots: PickupSlot[] }
export interface PickupOptions { timezone: string; days: PickupDay[] }

export async function fetchPickupOptions(signal?: AbortSignal): Promise<PickupOptions> {
  const response = await fetch(apiUrl('/api/pickup-locations/options'), { headers: { Accept: 'application/json' }, signal })
  if (!response.ok) throw await apiRequestError(response)
  return await response.json() as PickupOptions
}
