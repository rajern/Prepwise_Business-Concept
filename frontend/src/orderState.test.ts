import { describe, expect, it } from 'vitest'
import type { OrderSummary } from './api/orders'
import { canCancelOrder, isUpcomingOrder, osloDate } from './orderState'

const order: OrderSummary = { id: 'id', status: 'ready_for_pickup', created_at: '', total_nok: '100', pickup_start_at: '2026-10-02T14:00:00Z', pickup_end_at: '2026-10-02T16:00:00Z', pickup_location_name: 'Kitchen', pickup_location_address: 'Oslo', can_cancel: true, cancellation_deadline: '2026-10-01T22:00:00Z' }
describe('order time boundaries', () => {
  it('moves an uncollected order at the end instant, without modifying status', () => {
    const end = Date.parse(order.pickup_end_at)
    expect(isUpcomingOrder(order, end - 1)).toBe(true)
    expect(isUpcomingOrder(order, end)).toBe(false)
    expect(order.status).toBe('ready_for_pickup')
    expect(isUpcomingOrder({ ...order, status: 'completed' }, end - 1)).toBe(false)
    expect(isUpcomingOrder({ ...order, status: 'cancelled' }, end - 1)).toBe(false)
  })
  it('honors Oslo midnight exactly, including the DST transition', () => {
    expect(canCancelOrder(order, Date.parse('2026-10-01T21:59:59Z'))).toBe(true)
    expect(canCancelOrder(order, Date.parse('2026-10-01T22:00:00Z'))).toBe(false)
    expect(osloDate(Date.parse('2026-10-24T22:00:00Z'))).toBe('2026-10-25')
    expect(osloDate(Date.parse('2026-10-25T22:59:59Z'))).toBe('2026-10-25')
    expect(osloDate(Date.parse('2026-10-25T23:00:00Z'))).toBe('2026-10-26')
  })
})
