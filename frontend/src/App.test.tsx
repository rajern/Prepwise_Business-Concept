import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { App } from './App'

const meal = {
  id: '41f28fb8-b533-4e32-a46c-8f902f9b28bb',
  name: 'Kylling teriyaki med ris',
  description: 'Saftig kylling med ris og grønnsaker.',
  image_url: null,
  price_nok: '129.00',
  calories: 585,
  protein_grams: '43.00',
  carbohydrate_grams: '68.00',
  fat_grams: '14.00',
  ingredients: ['Kylling', 'Jasminris', 'Brokkoli'],
  allergens: [
    { code: 'gluten', name: 'Gluten' },
    { code: 'soy', name: 'Soya' },
  ],
}

const secondMeal = {
  ...meal,
  id: 'fae7ba0b-fcf5-43c7-9798-561e92c42c59',
  name: 'Linsegryte med søtpotet',
  description: 'Linser, søtpotet og spinat.',
  calories: 520,
  protein_grams: '21.00',
  carbohydrate_grams: '76.00',
  fat_grams: '14.00',
  ingredients: ['Røde linser', 'Søtpotet', 'Spinat'],
  allergens: [],
}

const pickupLocation = {
  id: 'd8d25ca1-8892-4dc7-a12f-b12ed48fb9e1',
  name: 'Prepwise Grünerløkka',
  address_line: 'Thorvald Meyers gate 35',
  postal_code: '0555',
  city: 'Oslo',
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('App', () => {
  it('shows a loading state while the menu request is pending', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => undefined)))

    render(<App apiScope="api://prepwise/access_as_user" />)

    expect(screen.getByRole('status')).toHaveTextContent('Loading the menu')
  })

  it('renders meals returned by the API', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [meal],
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<App apiScope="api://prepwise/access_as_user" />)

    expect(
      await screen.findByRole('heading', { name: meal.name }),
    ).toBeInTheDocument()
    expect(screen.getByText(/129.*kr/)).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/meals',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
  })

  it('shows an actionable error state when the API fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: false, status: 503 }),
    )

    render(<App apiScope="api://prepwise/access_as_user" />)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'We could not load the menu',
    )
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('filters the catalogue by search text and nutrition', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [meal, secondMeal],
      }),
    )
    render(<App apiScope="api://prepwise/access_as_user" />)
    await screen.findByRole('heading', { name: meal.name })

    fireEvent.change(screen.getByRole('searchbox', { name: 'Search' }), {
      target: { value: 'linser' },
    })

    expect(screen.queryByRole('heading', { name: meal.name })).not.toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: secondMeal.name }),
    ).toBeInTheDocument()
    expect(screen.getByText('1 of 2 meals shown')).toBeInTheDocument()

    fireEvent.change(screen.getByRole('searchbox', { name: 'Search' }), {
      target: { value: '' },
    })
    fireEvent.change(screen.getByRole('combobox', { name: 'Nutrition' }), {
      target: { value: 'high-protein' },
    })

    expect(screen.getByRole('heading', { name: meal.name })).toBeInTheDocument()
    expect(
      screen.queryByRole('heading', { name: secondMeal.name }),
    ).not.toBeInTheDocument()
  })

  it('loads full meal details from the detail endpoint', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [meal] })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ...meal, available: true }),
      })
    vi.stubGlobal('fetch', fetchMock)
    render(<App apiScope="api://prepwise/access_as_user" />)
    await screen.findByRole('heading', { name: meal.name })

    fireEvent.click(screen.getByRole('button', { name: 'View details' }))

    expect(await screen.findByText('Available this week')).toBeInTheDocument()
    expect(screen.getByText('Kylling, Jasminris, Brokkoli')).toBeInTheDocument()
    expect(
      screen.getAllByRole('img', { name: `No image available for ${meal.name}` }),
    ).toHaveLength(2)
    expect(fetchMock).toHaveBeenLastCalledWith(
      `/api/meals/${meal.id}`,
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
  })

  it('shows a clear missing-meal state', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce({ ok: true, json: async () => [meal] })
        .mockResolvedValueOnce({ ok: false, status: 404 }),
    )
    render(<App apiScope="api://prepwise/access_as_user" />)
    await screen.findByRole('heading', { name: meal.name })

    fireEvent.click(screen.getByRole('button', { name: 'View details' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'This meal could not be found',
    )
  })

  it('persists cart mutations and lets the customer select a pickup location', async () => {
    let quantity = 0
    const cartResponse = () => ({
      items:
        quantity === 0
          ? []
          : [
              {
                id: 'c1c49342-a18f-4fd8-a555-e657577cc9db',
                quantity,
                line_total_nok: String(129 * quantity),
                meal: { ...meal, available: true },
              },
            ],
      total_quantity: quantity,
      total_nok: quantity === 0 ? '0.00' : String(129 * quantity),
    })
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = input.toString()
      if (path === '/api/meals') {
        return { ok: true, json: async () => [meal] }
      }
      if (path === '/api/pickup-locations') {
        return { ok: true, json: async () => [pickupLocation] }
      }
      if (path === '/api/cart' && !init?.method) {
        return { ok: true, json: async () => cartResponse() }
      }
      if (path === '/api/orders' && !init?.method) {
        return { ok: true, json: async () => [] }
      }
      if (path === '/api/cart/items' && init?.method === 'POST') {
        quantity += 1
        return { ok: true, json: async () => cartResponse() }
      }
      if (path.includes('/api/cart/items/') && init?.method === 'PATCH') {
        quantity = JSON.parse(init.body as string).quantity as number
        return { ok: true, json: async () => cartResponse() }
      }
      if (path.includes('/api/cart/items/') && init?.method === 'DELETE') {
        quantity = 0
        return { ok: true }
      }
      throw new Error(`Unexpected request: ${path}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <App
        apiScope="api://prepwise/access_as_user"
        initialAccessToken="test-access-token"
      />,
    )

    expect(await screen.findByText(/Your cart is empty/)).toBeInTheDocument()
    await screen.findByRole('heading', { name: meal.name })
    fireEvent.click(screen.getByRole('button', { name: 'Add to cart' }))

    expect(await screen.findByText('1 meal')).toBeInTheDocument()
    fireEvent.click(
      screen.getByRole('button', { name: `Increase ${meal.name}` }),
    )
    expect(await screen.findByText('2 meals')).toBeInTheDocument()

    fireEvent.change(
      screen.getByRole('combobox', { name: 'Pickup location' }),
      { target: { value: pickupLocation.id } },
    )
    expect(
      screen.getByRole('combobox', { name: 'Pickup location' }),
    ).toHaveValue(pickupLocation.id)

    fireEvent.click(screen.getByRole('button', { name: 'Remove' }))
    expect(await screen.findByText(/Your cart is empty/)).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/cart/items',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Authorization: 'Bearer test-access-token',
        }),
      }),
    )
  })

  it('requires confirmation, creates an order, and shows owned order details', async () => {
    const order = {
      id: '516835d2-bf33-4f39-803c-2e8f32c0873e',
      status: 'received',
      total_nok: '129.00',
      created_at: '2026-09-24T10:00:00Z',
      pickup_start_at: '2026-09-25T14:00:00Z',
      pickup_end_at: '2026-09-25T16:00:00Z',
      pickup_location_name: pickupLocation.name,
      pickup_location_address: `${pickupLocation.address_line}, ${pickupLocation.postal_code} ${pickupLocation.city}`,
      items: [
        {
          meal_id: meal.id,
          meal_name: meal.name,
          quantity: 1,
          unit_price_nok: meal.price_nok,
          line_total_nok: meal.price_nok,
        },
      ],
    }
    let orderCreated = false
    const cart = {
      items: [
        {
          id: 'c1c49342-a18f-4fd8-a555-e657577cc9db',
          quantity: 1,
          line_total_nok: meal.price_nok,
          meal: { ...meal, available: true },
        },
      ],
      total_quantity: 1,
      total_nok: meal.price_nok,
    }
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = input.toString()
      if (path === '/api/meals') {
        return { ok: true, json: async () => [meal] }
      }
      if (path === '/api/cart') {
        return { ok: true, json: async () => cart }
      }
      if (path === '/api/pickup-locations') {
        return { ok: true, json: async () => [pickupLocation] }
      }
      if (path === '/api/orders' && init?.method === 'POST') {
        orderCreated = true
        return { ok: true, json: async () => order }
      }
      if (path === '/api/orders' && !init?.method) {
        return {
          ok: true,
          json: async () => (orderCreated ? [{ ...order, items: undefined }] : []),
        }
      }
      if (path === `/api/orders/${order.id}`) {
        return { ok: true, json: async () => order }
      }
      throw new Error(`Unexpected request: ${path}`)
    })
    vi.stubGlobal('fetch', fetchMock)
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)

    render(
      <App
        apiScope="api://prepwise/access_as_user"
        initialAccessToken="test-access-token"
      />,
    )

    await screen.findByText('1 meal')
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Pickup location' }),
      { target: { value: pickupLocation.id } },
    )
    fireEvent.click(
      screen.getByRole('button', { name: 'Review and place order' }),
    )

    expect(confirm).toHaveBeenCalledOnce()
    expect(await screen.findByText(/Your cart is empty/)).toBeInTheDocument()
    expect(await screen.findByText(`1 × ${meal.name}`)).toBeInTheDocument()
    expect(screen.getAllByText('Received')).toHaveLength(2)

    fireEvent.click(screen.getByRole('button', { name: 'View order' }))
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        `/api/orders/${order.id}`,
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer test-access-token',
          }),
        }),
      )
    })
    expect(
      screen.getByText((_, element) =>
        Boolean(element?.classList.contains('order-detail__pickup')),
      ),
    ).toHaveTextContent(order.pickup_location_address)
  })
})
