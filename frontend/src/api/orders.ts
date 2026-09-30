import { apiUrl } from './config'
import { apiRequestError } from './errors'
import type { Language } from '../i18n'

export type OrderStatus =
  | 'received'
  | 'preparing'
  | 'ready_for_pickup'
  | 'completed'

export interface OrderSummary {
  id: string
  status: OrderStatus
  total_nok: string
  created_at: string
  pickup_start_at: string
  pickup_end_at: string
  pickup_location_name: string
  pickup_location_address: string
}

export interface OrderItem {
  meal_id: string
  meal_name: string
  quantity: number
  unit_price_nok: string
  line_total_nok: string
}

export interface OrderDetail extends OrderSummary {
  items: OrderItem[]
}

export async function fetchOrders(
  accessToken: string,
  signal?: AbortSignal,
  language: Language = 'no',
): Promise<OrderSummary[]> {
  return orderRequest(`/api/orders?lang=${language}`, accessToken, { signal })
}

export async function fetchOrder(
  accessToken: string,
  orderId: string,
  signal?: AbortSignal,
  language: Language = 'no',
): Promise<OrderDetail> {
  return orderRequest(`/api/orders/${orderId}?lang=${language}`, accessToken, { signal })
}

export async function createOrder(
  accessToken: string,
  pickupLocationId: string,
  pickupDate: string,
  pickupSlot: string,
  language: Language = 'no',
): Promise<OrderDetail> {
  return orderRequest(`/api/orders?lang=${language}`, accessToken, {
    method: 'POST',
    body: JSON.stringify({ pickup_location_id: pickupLocationId, pickup_date: pickupDate, pickup_slot: pickupSlot }),
  })
}

async function orderRequest<T>(
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
