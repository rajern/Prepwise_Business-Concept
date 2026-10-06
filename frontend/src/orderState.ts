import type { OrderSummary } from './api/orders'

export function isUpcomingOrder(order: OrderSummary, now: number): boolean {
  if (order.status === 'completed' || order.status === 'cancelled') return false
  const end = Date.parse(order.pickup_end_at)
  // An invalid server timestamp must not silently hide an active order.
  return !Number.isFinite(end) || now < end
}

export function canCancelOrder(order: OrderSummary, now: number): boolean {
  if (!order.can_cancel || order.status === 'completed' || order.status === 'cancelled') return false
  return order.cancellation_deadline ? now < Date.parse(order.cancellation_deadline) : false
}

export function osloDate(now: number): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Oslo', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(now))
}
