import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { OrdersPanel } from './OrdersPanel'

const order = {
  id: 'bed7f246-f80d-4df9-83e2-18fea73e50aa',
  status: 'received' as const,
  total_nok: '258.00',
  created_at: '2026-09-24T08:00:00Z',
  pickup_start_at: '2026-09-25T14:00:00Z',
  pickup_end_at: '2026-09-25T16:00:00Z',
  pickup_location_name: 'Oslo S',
  pickup_location_address: 'Jernbanetorget 1, 0154 Oslo',
  customer_email: 'customer@example.com',
  customer_display_name: 'Test Customer',
}

const detail = {
  ...order,
  items: [
    {
      meal_id: '3e6b0927-51c6-4d72-94e8-3b701bda74b4',
      meal_name: 'Test meal',
      quantity: 2,
      unit_price_nok: '129.00',
      line_total_nok: '258.00',
    },
  ],
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('OrdersPanel', () => {
  it('keeps order B selected when the older order A detail resolves last', async () => {
    let first!: (value: unknown) => void
    const other = { ...detail, id: 'order-b', customer_display_name: 'Second customer', items: [{ ...detail.items[0], meal_name: 'Second meal' }] }
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const path = input.toString()
      if (path === '/api/admin/orders') return { ok: true, json: async () => [order, other] }
      if (path.endsWith('/order-b')) return { ok: true, json: async () => other }
      return new Promise((resolve) => { first = resolve })
    }))
    render(<OrdersPanel accessToken="admin-token" />)
    await screen.findByRole('heading', { name: 'Second customer' })
    fireEvent.click(screen.getAllByRole('button', { name: 'Inspect' })[0])
    fireEvent.click(screen.getAllByRole('button', { name: 'Inspect' })[1])
    await screen.findByText('2 × Second meal')
    await act(async () => { first({ ok: true, json: async () => detail }) })
    expect(screen.queryByText('2 × Test meal')).not.toBeInTheDocument()
    expect(screen.getByText('2 × Second meal')).toBeInTheDocument()
  })
  it('inspects an order and advances it by one valid status', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = input.toString()
      if (path === '/api/admin/orders' && !init?.method) {
        return { ok: true, json: async () => [order] }
      }
      if (path === `/api/admin/orders/${order.id}` && !init?.method) {
        return { ok: true, json: async () => detail }
      }
      if (path === `/api/admin/orders/${order.id}/status` && init?.method === 'PATCH') {
        return {
          ok: true,
          json: async () => ({ ...detail, status: 'preparing' }),
        }
      }
      throw new Error(`Unexpected request: ${path}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<OrdersPanel accessToken="admin-token" />)

    await screen.findByRole('heading', { name: 'Test Customer' })
    fireEvent.click(screen.getByRole('button', { name: 'Inspect' }))
    await screen.findByText(/Test meal/)
    fireEvent.click(screen.getByRole('button', { name: 'Move to Preparing' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        `/api/admin/orders/${order.id}/status`,
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ status: 'preparing' }),
        }),
      )
    })
    expect(screen.getByRole('button', { name: 'Move to Ready For Pickup' })).toBeInTheDocument()
  })
})
