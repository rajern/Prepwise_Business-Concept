import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
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

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
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
})
