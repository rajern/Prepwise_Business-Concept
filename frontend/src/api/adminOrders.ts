import { apiUrl } from './config'
import { apiRequestError } from './errors'
import type { OrderDetail, OrderStatus, OrderSummary } from './orders'

export interface AdminOrderSummary extends OrderSummary {
  customer_email: string | null
  customer_display_name: string | null
}

export interface AdminOrderDetail extends OrderDetail {
  customer_email: string | null
  customer_display_name: string | null
}

export function fetchAdminOrders(
  accessToken: string,
  signal?: AbortSignal,
): Promise<AdminOrderSummary[]> {
  return adminOrderRequest('/api/admin/orders', accessToken, { signal })
}

export function fetchAdminOrder(
  accessToken: string,
  orderId: string,
  signal?: AbortSignal,
): Promise<AdminOrderDetail> {
  return adminOrderRequest(`/api/admin/orders/${orderId}`, accessToken, {
    signal,
  })
}

export function updateAdminOrderStatus(
  accessToken: string,
  orderId: string,
  status: OrderStatus,
): Promise<AdminOrderDetail> {
  return adminOrderRequest(`/api/admin/orders/${orderId}/status`, accessToken, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  })
}

async function adminOrderRequest<T>(
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
