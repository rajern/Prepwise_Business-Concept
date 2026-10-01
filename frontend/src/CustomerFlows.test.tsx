import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'
import type { Cart, CartGroup } from './api/cart'
import type { OrderDetail } from './api/orders'

vi.mock('./auth/AuthControls', () => ({ AuthControls: ({ onAccessTokenChange }: { onAccessTokenChange: (value: string | null) => void }) => <button onClick={() => onAccessTokenChange(null)}>Test sign out</button> }))
const meal = { id: 'meal-a', name: 'Chicken', description: 'Chicken and rice', image_url: null, price_nok: '100.00', calories: 500, protein_grams: '40', carbohydrate_grams: '50', fat_grams: '10', ingredients: ['Chicken'], allergens: [], available: true }
const location = { id: 'location-a', name: 'Kitchen', address_line: 'Main 1', postal_code: '0001', city: 'Oslo' }
const options = { timezone: 'Europe/Oslo', days: ['2026-10-02', '2026-10-03'].map((date) => ({ date, slots: [{ id: '16-18', start_at: `${date}T14:00:00Z`, end_at: `${date}T16:00:00Z` }, { id: '18-20', start_at: `${date}T16:00:00Z`, end_at: `${date}T18:00:00Z` }] })) }
const makeOrder = (id: string, status: OrderDetail['status'] = 'received', cancellable = true): OrderDetail => ({ id, status, total_nok: '100.00', created_at: '2026-10-01T10:00:00Z', pickup_start_at: '2026-10-02T14:00:00Z', pickup_end_at: '2026-10-02T16:00:00Z', pickup_location_name: `Pickup ${id}`, pickup_location_address: 'Main 1', can_cancel: cancellable, cancellation_deadline: '2026-10-01T22:00:00Z', items: [{ meal_id: meal.id, meal_name: `Meal ${id}`, quantity: 1, unit_price_nok: '100.00', line_total_nok: '100.00' }] })
const emptyCart = { items: [], groups: [], total_quantity: 0, total_nok: '0' }
const json = (value: unknown) => ({ ok: true, json: async () => value })
function common(path: string) {
  if (path === '/api/meals') return json([meal])
  if (path === '/api/pickup-locations/options') return json(options)
  if (path === '/api/pickup-locations') return json([location])
  return undefined
}
function setup(fetcher: (path: string, init?: RequestInit) => unknown) {
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = input.toString().split('?')[0]
    return common(path) ?? fetcher(path, init)
  })
  vi.stubGlobal('fetch', mock)
  render(<App apiScope="scope" initialAccessToken="token" />)
  return mock
}
beforeEach(() => {
  localStorage.setItem('prepwise-language', 'en')
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: function (this: HTMLDialogElement) { this.open = true } })
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: function (this: HTMLDialogElement) { this.open = false } })
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); window.history.replaceState({}, '', '/'); sessionStorage.clear() })

describe('customer workflow regressions', () => {
  it('toggles meal details during loading and ignores a late response', async () => {
    let resolve: (value: unknown) => void = () => undefined
    setup((path) => {
      if (path === '/api/cart') return json(emptyCart)
      if (path === '/api/orders') return json([])
      if (path === '/api/meals/meal-a') return new Promise((done) => { resolve = done })
      throw new Error(path)
    })
    await screen.findByRole('heading', { name: 'Chicken' })
    const button = screen.getByRole('button', { name: 'View details' })
    fireEvent.click(button)
    expect(screen.getByRole('dialog', { name: 'Meal details' })).toBeInTheDocument()
    fireEvent.click(button)
    expect(screen.queryByText('Loading meal details…')).not.toBeInTheDocument()
    await act(async () => { resolve(json(meal)) })
    expect(screen.queryByRole('dialog', { name: 'Meal details' })).not.toBeInTheDocument()
  })

  it('switches and closes order details without accepting older responses', async () => {
    const first = makeOrder('first')
    const second = makeOrder('second')
    let resolveFirst: (value: unknown) => void = () => undefined
    setup((path) => {
      if (path === '/api/cart') return json(emptyCart)
      if (path === '/api/orders') return json([first, second])
      if (path === '/api/orders/first') return new Promise((resolve) => { resolveFirst = resolve })
      if (path === '/api/orders/second') return json(second)
      throw new Error(path)
    })
    fireEvent.click(await screen.findByRole('button', { name: /Upcoming orders/ }))
    await screen.findByText('Pickup first')
    fireEvent.click(screen.getAllByRole('button', { name: 'View order' })[0])
    fireEvent.click(screen.getByRole('button', { name: 'View order' }))
    await screen.findByText('1 × Meal second')
    await act(async () => { resolveFirst(json(first)) })
    expect(screen.queryByText('1 × Meal first')).not.toBeInTheDocument()
    fireEvent.click(screen.getAllByRole('button', { name: 'Close order' })[0])
    expect(screen.queryByText('1 × Meal second')).not.toBeInTheDocument()
  })

  it('does not restore a pending order after sign-out', async () => {
    const order = makeOrder('first')
    let resolve: (value: unknown) => void = () => undefined
    setup((path) => {
      if (path === '/api/cart') return json(emptyCart)
      if (path === '/api/orders') return json([order])
      if (path === '/api/orders/first') return new Promise((done) => { resolve = done })
      throw new Error(path)
    })
    fireEvent.click(await screen.findByRole('button', { name: /Upcoming orders/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'View order' }))
    fireEvent.click(screen.getByRole('button', { name: 'Test sign out' }))
    await act(async () => { resolve(json(order)) })
    expect(screen.queryByText('1 × Meal first')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Order history' })).not.toBeInTheDocument()
  })

  it('keeps overdue uncollected orders upcoming and puts only terminal orders in history', async () => {
    window.history.replaceState({}, '', '/orders')
    const active = { ...makeOrder('overdue'), pickup_start_at: '2020-01-01T14:00:00Z' }
    setup((path) => path === '/api/cart' ? json(emptyCart) : path === '/api/orders' ? json([active, makeOrder('done', 'completed'), makeOrder('cancelled', 'cancelled')]) : json(makeOrder('done', 'completed')))
    await screen.findByText('Pickup done')
    expect(screen.getByText('Pickup cancelled')).toBeInTheDocument()
    expect(screen.queryByText('Pickup overdue')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Choose your meals' })).not.toBeInTheDocument()
  })

  it('requires cancellation confirmation and hides the action for ineligible orders', async () => {
    const orders = [makeOrder('eligible'), makeOrder('today', 'received', false)]
    const fetcher = setup((path, init) => {
      if (path === '/api/cart') return json(emptyCart)
      if (path === '/api/orders') return json(orders)
      if (path === '/api/orders/eligible/cancel' && init?.method === 'POST') return json(makeOrder('eligible', 'cancelled', false))
      if (path === '/api/orders/eligible') return json(orders[0])
      if (path === '/api/orders/today') return json(orders[1])
      throw new Error(path)
    })
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    fireEvent.click(await screen.findByRole('button', { name: /Upcoming orders/ }))
    fireEvent.click((await screen.findAllByRole('button', { name: 'View order' }))[0])
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel order' }))
    expect(fetcher.mock.calls.some(([path]) => path.toString().includes('/cancel'))).toBe(false)
    confirm.mockReturnValue(true)
    fireEvent.click(screen.getByRole('button', { name: 'Cancel order' }))
    await waitFor(() => expect(screen.queryByText('Pickup eligible')).not.toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'View order' }))
    await screen.findByText('1 × Meal today')
    expect(screen.queryByRole('button', { name: 'Cancel order' })).not.toBeInTheDocument()
  })

  it('checks out one persisted group and preserves the other group with its pickup selection', async () => {
    const makeGroup = (id: string, date: string): CartGroup => {
      const item = { id: `item-${id}`, group_id: id, quantity: 1, line_total_nok: '100', meal }
      return { id, pickup_location_id: location.id, pickup_date: date, pickup_slot: '16-18', items: [item], total_quantity: 1, total_nok: '100' }
    }
    const groups = [makeGroup('first', '2026-10-02'), makeGroup('second', '2026-10-03')]
    let cart: Cart = { groups, items: groups.flatMap((group) => group.items), total_quantity: 2, total_nok: '200' }
    const mock = setup((path, init) => {
      if (path === '/api/cart') return json(cart)
      if (path === '/api/cart/groups/first' && init?.method === 'PATCH') return json(cart)
      if (path === '/api/orders' && init?.method === 'POST') {
        expect(JSON.parse(init.body as string)).toMatchObject({ group_id: 'first', pickup_date: '2026-10-02' })
        cart = { groups: [{ ...groups[0], items: [], total_quantity: 0, total_nok: '0' }, groups[1]], items: groups[1].items, total_quantity: 1, total_nok: '100' }
        return json(makeOrder('created'))
      }
      if (path === '/api/orders') return json([])
      if (path === '/api/orders/created') return json(makeOrder('created'))
      throw new Error(path)
    })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    await screen.findByRole('button', { name: 'Open cart (2)' })
    fireEvent.click(screen.getByRole('button', { name: 'Open cart (2)' }))
    const first = await screen.findByRole('region', { name: 'Pickup group 1' })
    fireEvent.click(within(first).getByRole('button', { name: 'Review and place order' }))
    await screen.findByRole('button', { name: 'Open cart (1)' })
    fireEvent.click(screen.getByRole('button', { name: 'Open cart (1)' }))
    await waitFor(() => expect(within(screen.getByRole('region', { name: 'Pickup group 2' })).getByRole('combobox', { name: 'Pickup date' })).toHaveValue('2026-10-03'))
    expect(within(screen.getByRole('region', { name: 'Pickup group 1' })).getByRole('button', { name: 'Remove empty group' })).toBeInTheDocument()
    expect(mock.mock.calls.some(([url, init]) => url.toString().includes('/api/cart/items/') && init?.method === 'DELETE')).toBe(false)
  })

  it('creates a group, targets new additions and moves an existing line independently', async () => {
    let group: CartGroup | null = null
    let assigned: string | null = null
    const item = () => ({ id: 'item-one', group_id: assigned, quantity: 1, line_total_nok: '100', meal })
    const cart = (): Cart => ({ groups: group ? [{ ...group, items: assigned ? [item()] : [] }] : [], items: [item()], total_quantity: 1, total_nok: '100' })
    const mock = setup((path, init) => {
      if (path === '/api/cart') return json(cart())
      if (path === '/api/orders') return json([])
      if (path === '/api/cart/groups' && init?.method === 'POST') {
        group = { id: 'new-group', pickup_location_id: null, pickup_date: null, pickup_slot: null, items: [], total_quantity: 0, total_nok: '0' }
        return json(cart())
      }
      if (path === '/api/cart/items/item-one' && init?.method === 'PATCH') { assigned = JSON.parse(init.body as string).group_id; return json(cart()) }
      if (path === '/api/cart/items' && init?.method === 'POST') return json(cart())
      throw new Error(path)
    })
    fireEvent.click(await screen.findByRole('button', { name: 'Open cart (1)' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Add pickup group' }))
    await screen.findByRole('region', { name: 'Pickup group 1' })
    fireEvent.change(screen.getByRole('combobox', { name: 'Pickup group · Chicken' }), { target: { value: 'new-group' } })
    await waitFor(() => expect(within(screen.getByRole('region', { name: 'Pickup group 1' })).getByRole('heading', { name: 'Chicken' })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Close cart' }))
    expect(screen.getByRole('combobox', { name: 'Add meals to' })).toHaveValue('new-group')
    fireEvent.click(screen.getByRole('button', { name: 'Add to cart' }))
    await waitFor(() => expect(mock).toHaveBeenCalledWith('/api/cart/items?lang=en', expect.objectContaining({ body: JSON.stringify({ meal_id: 'meal-a', quantity: 1, group_id: 'new-group' }) })))
  })
})
