import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AdminPage } from './AdminPage'

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
  allergens: [{ code: 'soy', name: 'Soya' }],
  available: true,
}

const allergens = [
  { code: 'milk', name: 'Melk' },
  { code: 'soy', name: 'Soya' },
]

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('AdminPage', () => {
  it('loads the protected catalogue and saves validated meal changes', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = input.toString()
      if (path === '/api/admin/meals' && !init?.method) {
        return { ok: true, json: async () => [meal] }
      }
      if (path === '/api/admin/meals/allergens') {
        return { ok: true, json: async () => allergens }
      }
      if (path === `/api/admin/meals/${meal.id}` && init?.method === 'PATCH') {
        const payload = JSON.parse(init.body as string) as {
          price_nok: number
          available: boolean
        }
        return {
          ok: true,
          json: async () => ({
            ...meal,
            price_nok: payload.price_nok.toFixed(2),
            available: payload.available,
          }),
        }
      }
      throw new Error(`Unexpected request: ${path}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<AdminPage accessToken="admin-access-token" />)

    await screen.findByRole('heading', { name: meal.name })
    fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Price NOK' }), {
      target: { value: '145.00' },
    })
    fireEvent.click(
      screen.getByRole('checkbox', {
        name: 'Available in the customer catalogue',
      }),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByText('Meal changes saved.')).toBeInTheDocument()
    expect(screen.getByText('Unavailable')).toBeInTheDocument()
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        `/api/admin/meals/${meal.id}`,
        expect.objectContaining({
          method: 'PATCH',
          headers: expect.objectContaining({
            Authorization: 'Bearer admin-access-token',
          }),
          body: expect.stringContaining('"available":false'),
        }),
      )
    })
  })

  it('creates a new meal from the admin form', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = input.toString()
      if (path === '/api/admin/meals' && !init?.method) {
        return { ok: true, json: async () => [] }
      }
      if (path === '/api/admin/meals/allergens') {
        return { ok: true, json: async () => allergens }
      }
      if (path === '/api/admin/meals' && init?.method === 'POST') {
        const payload = JSON.parse(init.body as string)
        return {
          ok: true,
          json: async () => ({
            id: '0afcd05f-10a1-4c52-a1aa-e4eb66399587',
            ...payload,
            price_nok: payload.price_nok.toFixed(2),
            protein_grams: payload.protein_grams.toFixed(2),
            carbohydrate_grams: payload.carbohydrate_grams.toFixed(2),
            fat_grams: payload.fat_grams.toFixed(2),
            allergens: [],
          }),
        }
      }
      throw new Error(`Unexpected request: ${path}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<AdminPage accessToken="admin-access-token" />)
    await screen.findByText('Create a meal')

    fireEvent.change(screen.getByRole('textbox', { name: 'Name' }), {
      target: { value: 'New admin meal' },
    })
    fireEvent.change(screen.getByRole('textbox', { name: 'Description' }), {
      target: { value: 'Created in the admin interface.' },
    })
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Price NOK' }), {
      target: { value: '120' },
    })
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Calories' }), {
      target: { value: '500' },
    })
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Protein grams' }), {
      target: { value: '30' },
    })
    fireEvent.change(
      screen.getByRole('spinbutton', { name: 'Carbohydrate grams' }),
      { target: { value: '50' } },
    )
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Fat grams' }), {
      target: { value: '15' },
    })
    fireEvent.change(screen.getByRole('textbox', { name: /Ingredients/ }), {
      target: { value: 'Rice, beans' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Create meal' }))

    expect(await screen.findByText('Meal created.')).toBeInTheDocument()
    expect(
      screen.getAllByRole('heading', { name: 'New admin meal' }),
    ).toHaveLength(2)
  })
})
