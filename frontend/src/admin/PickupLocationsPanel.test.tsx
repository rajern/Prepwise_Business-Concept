import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { PickupLocationsPanel } from './PickupLocationsPanel'

const location = {
  id: '3fbc772f-ec48-4386-bd8d-77594c60b974',
  name: 'Nydalen test pickup',
  address_line: 'Nydalsveien 1',
  postal_code: '0484',
  city: 'Oslo',
  active: true,
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('PickupLocationsPanel', () => {
  it('edits and deactivates a pickup location', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = input.toString()
      if (path === '/api/admin/pickup-locations' && !init?.method) {
        return { ok: true, json: async () => [location] }
      }
      if (
        path === `/api/admin/pickup-locations/${location.id}` &&
        init?.method === 'PATCH'
      ) {
        const payload = JSON.parse(init.body as string)
        return { ok: true, json: async () => ({ ...location, ...payload }) }
      }
      throw new Error(`Unexpected request: ${path}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<PickupLocationsPanel accessToken="admin-token" />)

    await screen.findByRole('heading', { name: location.name })
    fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
    fireEvent.click(
      screen.getByRole('checkbox', {
        name: 'Active and selectable during checkout',
      }),
    )
    fireEvent.click(screen.getByRole('button', { name: 'Save location' }))

    expect(await screen.findByText('Pickup location saved.')).toBeInTheDocument()
    expect(screen.getByText('Inactive')).toBeInTheDocument()
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        `/api/admin/pickup-locations/${location.id}`,
        expect.objectContaining({
          method: 'PATCH',
          body: expect.stringContaining('"active":false'),
        }),
      )
    })
  })

  it('creates a pickup location', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = input.toString()
      if (path === '/api/admin/pickup-locations' && !init?.method) {
        return { ok: true, json: async () => [] }
      }
      if (path === '/api/admin/pickup-locations' && init?.method === 'POST') {
        const payload = JSON.parse(init.body as string)
        return {
          ok: true,
          json: async () => ({ ...payload, id: location.id }),
        }
      }
      throw new Error(`Unexpected request: ${path}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<PickupLocationsPanel accessToken="admin-token" />)
    await screen.findByRole('heading', { name: 'Create a pickup location' })
    fireEvent.change(screen.getByRole('textbox', { name: 'Name' }), {
      target: { value: location.name },
    })
    fireEvent.change(screen.getByRole('textbox', { name: 'Address' }), {
      target: { value: location.address_line },
    })
    fireEvent.change(screen.getByRole('textbox', { name: 'Postal code' }), {
      target: { value: location.postal_code },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Create location' }))

    expect(await screen.findByText('Pickup location created.')).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { name: location.name })).toHaveLength(2)
  })
})
