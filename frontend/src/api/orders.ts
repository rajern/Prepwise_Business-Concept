import { apiUrl } from './config'
import { apiRequestError } from './errors'
import type { Language } from '../i18n'
import { authenticatedFetch } from '../auth/authenticatedFetch'

export type OrderStatus =
  | 'received'
  | 'preparing'
  | 'ready_for_pickup'
  | 'completed'
  | 'cancelled'

export interface OrderSummary {
  id: string
  status: OrderStatus
  total_nok: string
  created_at: string
  pickup_start_at: string
  pickup_end_at: string
  pickup_location_name: string
  pickup_location_address: string
  can_cancel?: boolean
  cancellation_deadline?: string
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

export interface OrderSelection {
  pickup_location_id: string
  pickup_date: string
  pickup_slot: string
  group_id: string | null
}
export interface OrderReview {
  review_fingerprint: string
  items: OrderItem[]
  total_quantity: number
  total_nok: string
  pickup_location_name: string
  pickup_location_address: string
  pickup_start_at: string
  pickup_end_at: string
}
export interface OrderPurchase extends OrderSelection {
  review_fingerprint: string
  idempotency_key: string
}

export async function reviewOrder(accessToken: string, selection: OrderSelection, language: Language): Promise<OrderReview> {
  return orderRequest(`/api/orders/review?lang=${language}`, accessToken, { method: 'POST', body: JSON.stringify(selection) })
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
  purchase: OrderPurchase,
  language: Language = 'no',
): Promise<OrderDetail> {
  return orderRequest(`/api/orders?lang=${language}`, accessToken, {
    method: 'POST',
    body: JSON.stringify(purchase),
  })
}

export async function cancelOrder(accessToken: string, orderId: string, language: Language): Promise<OrderDetail> {
  return orderRequest(`/api/orders/${orderId}/cancel?lang=${language}`, accessToken, { method: 'POST' })
}

async function orderRequest<T>(
  path: string,
  accessToken: string,
  init: RequestInit,
): Promise<T> {
  const response = await authenticatedFetch(apiUrl(path), accessToken, {
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
