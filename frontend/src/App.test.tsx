import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
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
})
