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
  vi.spyOn(Date, 'now').mockReturnValue(Date.parse('2026-10-01T10:00:00Z'))
  localStorage.setItem('prepwise-language', 'en')
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: function (this: HTMLDialogElement) { this.open = true } })
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: function (this: HTMLDialogElement) { this.open = false } })
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.useRealTimers(); window.history.replaceState({}, '', '/'); sessionStorage.clear() })

describe('customer workflow regressions', () => {
  it('shows a recoverable cart error when its refresh deadline expires', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    setup((path) => {
      if (path === '/api/cart' || path === '/api/orders') return new Promise(() => undefined)
      throw new Error(path)
    })
    fireEvent.click(screen.getByRole('button', { name: 'Open cart (0)' }))
    await act(async () => { await vi.advanceTimersByTimeAsync(15001) })
    expect(screen.getByRole('alert')).toHaveTextContent('We could not load your cart.')
    expect(screen.queryByText('Loading your cart…')).not.toBeInTheDocument()
  })

  it('refreshes cancellation after a language switch during the write', async () => {
    let order = makeOrder('language')
    let finish!: (value: unknown) => void
    setup((path, init) => {
      if (path === '/api/cart') return json(emptyCart)
      if (path === '/api/orders') return json([order])
      if (path === '/api/orders/language/cancel' && init?.method === 'POST') return new Promise((resolve) => { finish = resolve })
      if (path === '/api/orders/language') return json(order)
      throw new Error(path)
    })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    fireEvent.click(await screen.findByRole('button', { name: /Upcoming orders/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'View order' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel order' }))
    fireEvent.click(screen.getByRole('button', { name: /^NO$/ }))
    await screen.findByRole('button', { name: /Kommende bestillinger \(1\)/ })
    order = makeOrder('language', 'cancelled', false)
    await act(async () => { finish(json(order)) })
    await screen.findByRole('button', { name: /Kommende bestillinger \(0\)/ })
    expect(screen.queryByRole('button', { name: 'Kanseller bestilling' })).not.toBeInTheDocument()
    expect(screen.queryByText('1 × Meal language')).not.toBeInTheDocument()
  })

  it('reclassifies elapsed orders on the clock without reloading and expires cancellation at midnight', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
    const now = vi.mocked(Date.now)
    const order = makeOrder('clock')
    now.mockReturnValue(Date.parse('2026-10-01T21:59:59Z'))
    setup((path) => path === '/api/cart' ? json(emptyCart) : path === '/api/orders' ? json([order]) : json(order))
    fireEvent.click(await screen.findByRole('button', { name: /Upcoming orders/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'View order' }))
    expect(await screen.findByRole('button', { name: 'Cancel order' })).toBeInTheDocument()
    now.mockReturnValue(Date.parse('2026-10-01T22:00:00Z'))
    await act(async () => { vi.advanceTimersByTime(30000) })
    expect(screen.queryByRole('button', { name: 'Cancel order' })).not.toBeInTheDocument()
    now.mockReturnValue(Date.parse(order.pickup_end_at))
    await act(async () => { vi.advanceTimersByTime(30000) })
    expect(screen.getByRole('button', { name: /Upcoming orders \(0\)/ })).toBeInTheDocument()
    expect(screen.queryByText('Pickup clock')).not.toBeInTheDocument()
    expect(screen.queryByText('1 × Meal clock')).not.toBeInTheDocument()
  })

  it('does not accept an older cart refresh after a newer refresh', async () => {
    let calls = 0
    let resolveOld!: (value: unknown) => void
    const next = { items: [{ id: 'one', quantity: 2, line_total_nok: '200', meal }], total_quantity: 2, total_nok: '200' }
    setup((path) => {
      if (path === '/api/cart') return ++calls === 1 ? new Promise((resolve) => { resolveOld = resolve }) : json(next)
      if (path === '/api/orders') return json([])
      throw new Error(path)
    })
    fireEvent.click(screen.getByRole('button', { name: 'Open cart (0)' }))
    await screen.findByRole('button', { name: 'Open cart (2)' })
    await act(async () => { resolveOld(json(emptyCart)) })
    expect(screen.getByRole('button', { name: 'Open cart (2)' })).toBeInTheDocument()
  })

  it('sends compare-and-set originals and refreshes after a stale quantity conflict without retry', async () => {
    let quantity = 1
    const cart = () => ({ items: [{ id: 'one', group_id: null, quantity, line_total_nok: String(quantity * 100), meal }], total_quantity: quantity, total_nok: String(quantity * 100) })
    const mock = setup((path, init) => {
      if (path === '/api/cart') return json(cart())
      if (path === '/api/orders') return json([])
      if (path === '/api/cart/items/one' && init?.method === 'PATCH') {
        expect(JSON.parse(init.body as string)).toEqual({ quantity: 2, expected_quantity: 1, expected_group_id: null })
        quantity = 3
        return { ok: false, status: 409, json: async () => ({}) }
      }
      throw new Error(path)
    })
    fireEvent.click(await screen.findByRole('button', { name: 'Open cart (1)' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Increase Chicken' }))
    await screen.findByRole('button', { name: 'Open cart (3)' })
    expect(await screen.findByRole('alert')).toHaveTextContent('Your cart changed.')
    expect(mock.mock.calls.filter(([, init]) => init?.method === 'PATCH')).toHaveLength(1)
  })

  it('confirms the server quote and retains the same purchase after an uncertain response', async () => {
    const item = { id: 'one', quantity: 1, line_total_nok: '100', meal }
    const cart = { items: [item], total_quantity: 1, total_nok: '100' }
    const quote = { ...makeOrder('quoted'), total_nok: '300.00', total_quantity: 1, items: [{ ...makeOrder('quoted').items[0], meal_name: 'Server meal', unit_price_nok: '300.00', line_total_nok: '300.00' }], review_fingerprint: 'a'.repeat(64) }
    let purchases = 0
    let placed = false
    const mock = setup((path, init) => {
      if (path === '/api/cart') return json(placed ? emptyCart : cart)
      if (path === '/api/orders/review') return json(quote)
      if (path === '/api/orders' && init?.method === 'POST') {
        placed = true
        if (++purchases === 1) throw new TypeError('Lost response')
        return json(makeOrder('placed'))
      }
      if (path === '/api/orders') return json(placed ? [makeOrder('placed')] : [])
      if (path === '/api/orders/placed') return json(makeOrder('placed'))
      throw new Error(path)
    })
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    fireEvent.click(await screen.findByRole('button', { name: 'Open cart (1)' }))
    fireEvent.change(await screen.findByRole('combobox', { name: 'Pickup location' }), { target: { value: location.id } })
    fireEvent.change(screen.getByRole('combobox', { name: 'Pickup date' }), { target: { value: '2026-10-02' } })
    fireEvent.change(screen.getByRole('combobox', { name: 'Pickup time' }), { target: { value: '16-18' } })
    fireEvent.click(screen.getByRole('button', { name: 'Review and place order' }))
    const retry = await screen.findByRole('button', { name: 'Check previous checkout' })
    expect(confirm.mock.calls[0][0]).toContain('Server meal')
    expect(confirm.mock.calls[0][0]).toMatch(/300/)
    await waitFor(() => expect(retry).toBeEnabled())
    fireEvent.click(retry)
    await screen.findByText('1 × Meal placed')
    const payloads = mock.mock.calls.filter(([url, init]) => url.toString().split('?')[0] === '/api/orders' && init?.method === 'POST').map(([, init]) => JSON.parse(init!.body as string))
    expect(payloads).toHaveLength(2)
    expect(payloads[0]).toEqual(payloads[1])
    expect(mock.mock.calls.filter(([url]) => url.toString().includes('/api/orders/review'))).toHaveLength(1)
    expect(mock.mock.calls.some(([url]) => url.toString().includes('/api/cart/groups'))).toBe(false)
  })

  it('starts a new review/key only after the server proves an uncertain checkout was not created', async () => {
    const cart = { items: [{ id: 'one', quantity: 1, line_total_nok: '100', meal }], total_quantity: 1, total_nok: '100' }
    let writes = 0
    let reviews = 0
    let placed = false
    const mock = setup((path, init) => {
      if (path === '/api/cart') return json(placed ? emptyCart : cart)
      if (path === '/api/orders/review') { reviews += 1; return json({ ...makeOrder('quote'), total_quantity: 1, review_fingerprint: (reviews === 1 ? 'a' : 'b').repeat(64) }) }
      if (path === '/api/orders' && init?.method === 'POST') {
        writes += 1
        if (writes === 1) throw new TypeError('Lost response')
        if (writes === 2) return { ok: false, status: 409, json: async () => ({ code: 'checkout_not_created', detail: 'Review changed; no order with this key exists.' }) }
        placed = true
        return json(makeOrder('placed'))
      }
      if (path === '/api/orders') return json(placed ? [makeOrder('placed')] : [])
      if (path === '/api/orders/placed') return json(makeOrder('placed'))
      throw new Error(path)
    })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    fireEvent.click(await screen.findByRole('button', { name: 'Open cart (1)' }))
    fireEvent.change(await screen.findByRole('combobox', { name: 'Pickup location' }), { target: { value: location.id } })
    fireEvent.change(screen.getByRole('combobox', { name: 'Pickup date' }), { target: { value: '2026-10-02' } })
    fireEvent.change(screen.getByRole('combobox', { name: 'Pickup time' }), { target: { value: '16-18' } })
    fireEvent.click(screen.getByRole('button', { name: 'Review and place order' }))
    const retry = await screen.findByRole('button', { name: 'Check previous checkout' })
    await waitFor(() => expect(retry).toBeEnabled())
    fireEvent.click(retry)
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Check previous checkout' })).not.toBeInTheDocument())
    const review = screen.getByRole('button', { name: 'Review and place order' })
    await waitFor(() => expect(review).toBeEnabled())
    fireEvent.click(review)
    await screen.findByText('1 × Meal placed')
    const payloads = mock.mock.calls.filter(([url, init]) => url.toString().split('?')[0] === '/api/orders' && init?.method === 'POST').map(([, init]) => JSON.parse(init!.body as string))
    expect(payloads).toHaveLength(3)
    expect(payloads[0]).toEqual(payloads[1])
    expect(payloads[2].idempotency_key).not.toBe(payloads[0].idempotency_key)
    expect(payloads[2].review_fingerprint).toBe('b'.repeat(64))
    expect(reviews).toBe(2)
  })

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

  it('shows elapsed uncollected orders in history without changing their fulfilment status', async () => {
    window.history.replaceState({}, '', '/orders')
    const active = { ...makeOrder('overdue'), pickup_start_at: '2020-01-01T14:00:00Z', pickup_end_at: '2020-01-01T16:00:00Z' }
    setup((path) => path === '/api/cart' ? json(emptyCart) : path === '/api/orders' ? json([active, makeOrder('done', 'completed'), makeOrder('cancelled', 'cancelled')]) : json(makeOrder('done', 'completed')))
    await screen.findByText('Pickup done')
    expect(screen.getByText('Pickup cancelled')).toBeInTheDocument()
    expect(screen.getByText('Pickup overdue')).toBeInTheDocument()
    expect(screen.getByText('Pickup time has passed — collection is not confirmed.')).toBeInTheDocument()
    expect(screen.getByText('Received')).toBeInTheDocument()
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
      return { id, version: 'v1', pickup_location_id: location.id, pickup_date: date, pickup_slot: '16-18', items: [item], total_quantity: 1, total_nok: '100' }
    }
    const groups = [makeGroup('first', '2026-10-02'), makeGroup('second', '2026-10-03')]
    let cart: Cart = { groups, items: groups.flatMap((group) => group.items), total_quantity: 2, total_nok: '200' }
    const mock = setup((path, init) => {
      if (path === '/api/cart') return json(cart)
      if (path === '/api/orders/review') return json({ ...makeOrder('quoted'), review_fingerprint: 'a'.repeat(64), total_quantity: 1 })
      if (path === '/api/cart/groups/first' && init?.method === 'PATCH') return json(cart)
      if (path === '/api/orders' && init?.method === 'POST') {
        expect(JSON.parse(init.body as string)).toMatchObject({ group_id: 'first', pickup_date: '2026-10-02', review_fingerprint: 'a'.repeat(64), idempotency_key: expect.any(String) })
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
        group = { id: 'new-group', version: 'v1', pickup_location_id: null, pickup_date: null, pickup_slot: null, items: [], total_quantity: 0, total_nok: '0' }
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
